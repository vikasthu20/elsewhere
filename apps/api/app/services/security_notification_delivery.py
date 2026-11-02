"""Leased, multi-worker webhook delivery with terminal-failure escalation."""
import json
import hashlib
import secrets
import os
import socket
import smtplib
from email.message import EmailMessage
from urllib.parse import urlencode
from base64 import b64encode
import uuid
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from sqlalchemy import or_
from app.db import SessionLocal
from app.models import SecurityNotificationDelivery, SecurityAlert, SecurityNotificationTemplate
from app.services.notification_provider_resilience import circuit_state, provider_for_channel, record_provider_result, queue_channel_failover


def _post_json(url: str, payload: dict, timeout: int = 8) -> int:
    request = Request(url, data=json.dumps(payload).encode("utf-8"),
                      headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(request, timeout=timeout) as response:
        return int(response.status)



def send_verification_code(channel: str, destination: str, code: str) -> int:
    if channel == "email":
        host=os.getenv("SECURITY_SMTP_HOST","").strip()
        sender=os.getenv("SECURITY_EMAIL_FROM","").strip()
        if not host or not sender:
            raise RuntimeError("SMTP host and SECURITY_EMAIL_FROM are required")
        message=EmailMessage()
        message["Subject"]="Elsewhere security notification verification"
        message["From"]=sender; message["To"]=destination
        message.set_content(f"Your Elsewhere verification code is {code}. It expires in 10 minutes.")
        with smtplib.SMTP(host,int(os.getenv("SECURITY_SMTP_PORT","587")),timeout=8) as smtp:
            if os.getenv("SECURITY_SMTP_STARTTLS","true").lower()=="true": smtp.starttls()
            user=os.getenv("SECURITY_SMTP_USERNAME","")
            if user: smtp.login(user,os.getenv("SECURITY_SMTP_PASSWORD",""))
            smtp.send_message(message)
        return 250
    if channel == "sms":
        account=os.getenv("SECURITY_TWILIO_ACCOUNT_SID","").strip()
        auth=os.getenv("SECURITY_TWILIO_AUTH_TOKEN","").strip()
        sender=os.getenv("SECURITY_TWILIO_FROM","").strip()
        if not all((account,auth,sender)): raise RuntimeError("Twilio credentials and sender are required")
        url=f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json"
        body=urlencode({"From":sender,"To":destination,"Body":f"Elsewhere verification code: {code}. Expires in 10 minutes."}).encode()
        header=b64encode(f"{account}:{auth}".encode()).decode()
        req=Request(url,data=body,headers={"Authorization":f"Basic {header}","Content-Type":"application/x-www-form-urlencoded"},method="POST")
        with urlopen(req,timeout=8) as response: return int(response.status)
    raise ValueError("Unsupported verification channel")

def _send_channel(channel: str, alert, webhook: str, recipient_email: str | None = None, recipient_phone: str | None = None) -> int:
    if channel == "webhook":
        return _post_json(webhook, {"type": "security_alert", "alert": {
            "id": alert.id, "event_type": alert.event_type, "severity": alert.severity,
            "title": alert.title, "summary": alert.summary,
            "event_count": alert.event_count, "created_at": alert.created_at.isoformat()}})
    template_db = SessionLocal()
    try:
        template = template_db.query(SecurityNotificationTemplate).filter_by(channel=channel).first()
        template_values = {"severity": alert.severity.upper(), "title": alert.title,
            "summary": alert.summary, "event_type": alert.event_type, "alert_id": alert.id}
        custom_subject = template.subject_template.format_map(template_values) if template and template.subject_template else ""
        custom_body = template.body_template.format_map(template_values) if template else ""
    finally:
        template_db.close()
    if channel == "email":
        host=os.getenv("SECURITY_SMTP_HOST","").strip()
        sender=os.getenv("SECURITY_EMAIL_FROM","").strip()
        recipient=(recipient_email or os.getenv("SECURITY_ALERT_EMAIL_TO","")).strip()
        if not host or not sender or not recipient:
            raise RuntimeError("SMTP host, sender and SECURITY_ALERT_EMAIL_TO are required")
        message=EmailMessage()
        message["Subject"]=custom_subject or f"[Elsewhere {alert.severity.upper()}] {alert.title}"
        message["From"]=sender; message["To"]=recipient
        message.set_content(custom_body or f"{alert.summary}\\nEvent type: {alert.event_type}\\nAlert ID: {alert.id}")
        port=int(os.getenv("SECURITY_SMTP_PORT","587"))
        with smtplib.SMTP(host,port,timeout=8) as smtp:
            if os.getenv("SECURITY_SMTP_STARTTLS","true").lower()=="true": smtp.starttls()
            user=os.getenv("SECURITY_SMTP_USERNAME","")
            if user: smtp.login(user,os.getenv("SECURITY_SMTP_PASSWORD",""))
            smtp.send_message(message)
        return 250
    if channel == "sms":
        account=os.getenv("SECURITY_TWILIO_ACCOUNT_SID","").strip()
        auth=os.getenv("SECURITY_TWILIO_AUTH_TOKEN","").strip()
        sender=os.getenv("SECURITY_TWILIO_FROM","").strip()
        recipient=(recipient_phone or os.getenv("SECURITY_ALERT_SMS_TO","")).strip()
        if not all((account,auth,sender,recipient)):
            raise RuntimeError("Twilio credentials, sender and SECURITY_ALERT_SMS_TO are required")
        url=f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json"
        body=urlencode({"From":sender,"To":recipient,
            "Body":(custom_body or f"[Elsewhere {alert.severity.upper()}] {alert.title}: {alert.summary[:500]}")[:1500]}).encode()
        auth_header=b64encode(f"{account}:{auth}".encode()).decode()
        req=Request(url,data=body,headers={"Authorization":f"Basic {auth_header}",
            "Content-Type":"application/x-www-form-urlencoded"},method="POST")
        with urlopen(req,timeout=8) as response:return int(response.status)
    raise RuntimeError(f"Unsupported notification channel: {channel}")


def _claim_jobs(batch_size: int, worker_id: str, lease_seconds: int):
    now = datetime.utcnow()
    expired_lease = now - timedelta(seconds=lease_seconds)
    db = SessionLocal()
    try:
        query = (db.query(SecurityNotificationDelivery)
            .filter(or_(
                SecurityNotificationDelivery.status.in_(["pending", "retry"]),
                (SecurityNotificationDelivery.status == "processing") &
                (SecurityNotificationDelivery.locked_at < expired_lease)))
            .filter(SecurityNotificationDelivery.next_attempt_at <= now)
            .order_by(SecurityNotificationDelivery.next_attempt_at)
            .limit(batch_size)
            .with_for_update(skip_locked=True))
        jobs = query.all()
        claimed = []
        for job in jobs:
            job.status = "processing"
            job.locked_at = now
            job.locked_by = worker_id
            claimed.append(job.id)
        db.commit()
        return claimed
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _deliver_one(job_id: str, max_attempts: int):
    db = SessionLocal()
    result = "skipped"
    try:
        job = db.get(SecurityNotificationDelivery, job_id)
        if not job or job.status != "processing":
            return result
        alert = db.get(SecurityAlert, job.alert_id)
        if alert is None:
            job.status = "failed"
            job.last_error = "Associated security alert no longer exists"
            job.escalation_status = "pending"
            db.commit()
            return "failed"
        webhook = os.getenv("SECURITY_ALERT_WEBHOOK_URL", "").strip()
        provider = provider_for_channel(job.channel)
        circuit = circuit_state(provider)
        if circuit["open"]:
            fallback = queue_channel_failover(db, job, alert)
            job.status = "failed"
            job.last_error = f"{provider} circuit is open until {circuit['open_until'].isoformat() if circuit['open_until'] else 'manual recovery'}"
            job.escalation_status = "pending" if not fallback else "not_required"
            job.locked_at = None; job.locked_by = None
            db.commit()
            return "failed"
        job.attempts += 1
        job.last_attempt_at = datetime.utcnow()
        try:
            code = _send_channel(job.channel, alert, webhook, job.recipient_email, job.recipient_phone)
            job.response_status = code
            if not 200 <= code < 300:
                raise RuntimeError(f"Notification provider returned HTTP {code}")
            job.status = "delivered"
            job.delivered_at = datetime.utcnow()
            job.last_error = None
            record_provider_result(provider, True)
            result = "delivered"
        except (URLError, HTTPError, TimeoutError, RuntimeError, OSError, smtplib.SMTPException) as exc:
            record_provider_result(provider, False, str(exc))
            fallback = queue_channel_failover(db, job, alert)
            job.last_error = str(exc)[:1000]
            if fallback:
                job.status = "failed"
                job.escalation_status = "not_required"
                result = "failed"
            elif job.attempts >= max_attempts:
                job.status = "failed"
                job.escalation_status = "pending"
                result = "failed"
            else:
                job.status = "retry"
                job.next_attempt_at = datetime.utcnow() + timedelta(
                    seconds=min(3600, 30 * (2 ** (job.attempts - 1))))
                result = "retry_scheduled"
        finally:
            job.locked_at = None
            job.locked_by = None
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _recover_stale_escalations(lease_seconds: int) -> int:
    """Return jobs stuck in escalation_status=sending after a worker crash to a retryable state."""
    expired = datetime.utcnow() - timedelta(seconds=max(30, lease_seconds))
    db = SessionLocal()
    recovered = 0
    try:
        jobs = (db.query(SecurityNotificationDelivery)
            .filter(SecurityNotificationDelivery.escalation_status == "sending",
                    SecurityNotificationDelivery.updated_at <= expired)
            .with_for_update(skip_locked=True).all())
        for job in jobs:
            if job.status == "failed":
                job.escalation_status = "pending"
            elif job.status in {"pending", "processing", "retry"}:
                job.escalation_status = "not_required"
            else:
                job.escalation_status = "pending"
            recovered += 1
        db.commit()
        return recovered
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def _escalate_failed(batch_size: int = 25) -> dict:
    webhook = os.getenv("SECURITY_ALERT_FAILURE_WEBHOOK_URL", "").strip()
    if not webhook:
        return {"escalated": 0, "pending": 0, "configured": False}
    db = SessionLocal()
    sent = failed = 0
    try:
        jobs = (db.query(SecurityNotificationDelivery)
            .filter(SecurityNotificationDelivery.status == "failed",
                    SecurityNotificationDelivery.escalation_status == "pending")
            .order_by(SecurityNotificationDelivery.updated_at)
            .limit(max(1, min(batch_size, 100))).with_for_update(skip_locked=True).all())
        for job in jobs:
            job.escalation_status = "sending"
            db.commit()
            try:
                payload = {"type": "security_alert_delivery_failed",
                           "delivery_id": job.id, "alert_id": job.alert_id,
                           "attempts": job.attempts, "last_error": job.last_error}
                _post_json(webhook, payload)
                job.escalation_status = "sent"
                job.escalation_sent_at = datetime.utcnow()
                sent += 1
            except (URLError, HTTPError, TimeoutError, OSError, RuntimeError) as exc:
                job.escalation_attempts += 1
                job.escalation_status = "pending" if job.escalation_attempts < 5 else "failed"
                job.last_error = ((job.last_error or "") + f"; escalation: {str(exc)[:300]}")[:1000]
                failed += 1
            db.commit()
        return {"escalated": sent, "escalation_failed": failed, "configured": True}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()



def _escalate_sla_breaches(batch_size: int = 25) -> dict:
    """Notify operations when a notification remains undelivered beyond the SLA."""
    webhook = os.getenv("SECURITY_ALERT_FAILURE_WEBHOOK_URL", "").strip()
    sla_seconds = max(60, int(os.getenv("SECURITY_NOTIFICATION_SLA_SECONDS", "900")))
    if not webhook:
        return {"breached": 0, "escalated": 0, "configured": False,
                "sla_seconds": sla_seconds}
    cutoff = datetime.utcnow() - timedelta(seconds=sla_seconds)
    db = SessionLocal()
    breached = sent = failed = 0
    try:
        jobs = (db.query(SecurityNotificationDelivery)
            .filter(SecurityNotificationDelivery.status.in_(["pending", "processing", "retry"]),
                    SecurityNotificationDelivery.created_at <= cutoff,
                    SecurityNotificationDelivery.escalation_status.notin_(["sent", "sending", "failed"]),
                    SecurityNotificationDelivery.escalation_attempts < 5)
            .order_by(SecurityNotificationDelivery.created_at)
            .limit(max(1, min(batch_size, 100))).with_for_update(skip_locked=True).all())
        for job in jobs:
            breached += 1
            job.escalation_status = "sending"
            db.commit()
            try:
                _post_json(webhook, {
                    "type": "security_notification_sla_breached",
                    "delivery_id": job.id, "alert_id": job.alert_id,
                    "channel": job.channel, "status": job.status,
                    "age_seconds": int((datetime.utcnow() - job.created_at).total_seconds()),
                    "sla_seconds": sla_seconds, "attempts": job.attempts,
                    "last_error": job.last_error})
                job.escalation_status = "sent"
                job.escalation_sent_at = datetime.utcnow()
                sent += 1
            except (URLError, HTTPError, TimeoutError, OSError, RuntimeError) as exc:
                job.escalation_attempts += 1
                job.escalation_status = "pending" if job.escalation_attempts < 5 else "failed"
                job.last_error = ((job.last_error or "") + f"; SLA escalation: {str(exc)[:250]}")[:1000]
                failed += 1
            db.commit()
        return {"breached": breached, "escalated": sent,
                "escalation_failed": failed, "configured": True,
                "sla_seconds": sla_seconds}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def process_batch(batch_size: int = 25, max_attempts: int = 8,
                  lease_seconds: int = 300) -> dict:
    batch_size = max(1, min(batch_size, 200))
    max_attempts = max(1, min(max_attempts, 20))
    lease_seconds = max(30, min(lease_seconds, 3600))
    worker_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:8]}"
    recovered = _recover_stale_escalations(lease_seconds)
    ids = _claim_jobs(batch_size, worker_id, lease_seconds)
    counts = {"delivered": 0, "retry_scheduled": 0, "failed": 0, "skipped": 0}
    for job_id in ids:
        outcome = _deliver_one(job_id, max_attempts)
        counts[outcome] = counts.get(outcome, 0) + 1
    escalation = _escalate_failed(batch_size)
    sla = _escalate_sla_breaches(batch_size)
    return {"claimed": len(ids), **counts, "escalation": escalation,
            "sla_monitoring": sla, "escalation_recovered": recovered}
