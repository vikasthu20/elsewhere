"""Provider connectivity probes and persisted notification circuit breakers."""
import os
import socket
import smtplib
from datetime import datetime, timedelta
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from base64 import b64encode
from sqlalchemy.exc import IntegrityError
from app.db import SessionLocal
from app.models import SecurityNotificationProviderHealth, SecurityAlert, SecurityNotificationPreference, SecurityNotificationDelivery, User

FAILURE_THRESHOLD = max(1, int(os.getenv("SECURITY_PROVIDER_FAILURE_THRESHOLD", "3")))
COOLDOWN_SECONDS = max(30, int(os.getenv("SECURITY_PROVIDER_COOLDOWN_SECONDS", "300")))
TIMEOUT_SECONDS = max(2, int(os.getenv("SECURITY_PROVIDER_PROBE_TIMEOUT_SECONDS", "8")))

def provider_for_channel(channel: str) -> str:
    return {"email": "smtp", "sms": "twilio", "webhook": "webhook"}.get(channel, channel)

def circuit_state(provider: str) -> dict:
    db=SessionLocal()
    try:
        row=db.query(SecurityNotificationProviderHealth).filter_by(provider=provider).first()
        now=datetime.utcnow()
        if row and row.circuit_open_until and row.circuit_open_until > now:
            return {"open": True, "open_until": row.circuit_open_until}
        return {"open": False, "open_until": row.circuit_open_until if row else None}
    finally:
        db.close()

def _queue_provider_recovery_alert(db, provider: str, now):
    """Create one recovery alert and route it to admins over healthy configured channels."""
    alert=SecurityAlert(
        event_type="notification_provider_recovered", severity="medium",
        title=f"{provider.upper()} notification provider recovered",
        summary=f"The {provider} provider passed a health check and its circuit breaker was reset.",
        event_count=1, window_started_at=now, status="open")
    db.add(alert)
    db.flush()
    for pref in db.query(SecurityNotificationPreference).all():
        if not pref.severity_medium:
            continue
        user=db.get(User,pref.admin_id)
        available={
            "email": pref.email_enabled and pref.email_verified and bool(pref.email_address or (user and user.email)) and provider!="smtp",
            "sms": pref.sms_enabled and pref.phone_verified and bool(pref.phone_number or (user and user.phone)) and provider!="twilio",
            "webhook": pref.webhook_enabled and bool(os.getenv("SECURITY_ALERT_WEBHOOK_URL","").strip()) and provider!="webhook",
        }
        order=[c.strip() for c in (pref.channel_priority or "email,sms,webhook").split(",")]
        channels=[c for c in order if c in available and available[c]]
        if pref.delivery_mode=="priority":
            channels=channels[:1]
        for channel in channels:
            db.add(SecurityNotificationDelivery(
                alert_id=alert.id, admin_id=pref.admin_id, channel=channel,
                status="pending", next_attempt_at=now,
                recipient_email=(pref.email_address or (user.email if user else None)) if channel=="email" else None,
                recipient_phone=(pref.phone_number or (user.phone if user else None)) if channel=="sms" else None))
    try:
        from app.core.security_events import publish_security_alert
        db.flush()
        db.info.setdefault("recovered_alert_ids", []).append(alert.id)
    except Exception:
        pass


def record_provider_result(provider: str, success: bool, error: str | None = None):
    db=SessionLocal()
    try:
        row=db.query(SecurityNotificationProviderHealth).filter_by(provider=provider).with_for_update().first()
        if row is None:
            row=SecurityNotificationProviderHealth(provider=provider)
            db.add(row)
            db.flush()
        now=datetime.utcnow()
        was_unhealthy = row.status in {"degraded", "open"} or bool(row.circuit_open_until)
        row.last_checked_at=now
        if success:
            row.status="healthy"; row.consecutive_failures=0
            row.last_success_at=now; row.last_error=None; row.circuit_open_until=None
            if was_unhealthy:
                _queue_provider_recovery_alert(db, provider, now)
        else:
            row.consecutive_failures += 1
            row.last_failure_at=now; row.last_error=(error or "Provider request failed")[:1000]
            if row.consecutive_failures >= FAILURE_THRESHOLD:
                row.status="open"
                row.circuit_open_until=now+timedelta(seconds=COOLDOWN_SECONDS)
            else:
                row.status="degraded"
        recovery_ids=list(db.info.pop("recovered_alert_ids", []))
        db.commit()
        for alert_id in recovery_ids:
            try:
                from app.core.security_events import publish_security_alert
                publish_security_alert(alert_id)
            except Exception:
                pass
    except IntegrityError:
        db.rollback()
    finally:
        db.close()

def _probe_smtp():
    host=os.getenv("SECURITY_SMTP_HOST","").strip()
    if not host: raise RuntimeError("SECURITY_SMTP_HOST is not configured")
    port=int(os.getenv("SECURITY_SMTP_PORT","587"))
    with smtplib.SMTP(host,port,timeout=TIMEOUT_SECONDS) as client:
        client.ehlo()
        if os.getenv("SECURITY_SMTP_STARTTLS","true").lower()=="true":
            client.starttls(); client.ehlo()
        user=os.getenv("SECURITY_SMTP_USERNAME","")
        if user: client.login(user,os.getenv("SECURITY_SMTP_PASSWORD",""))

def _probe_twilio():
    account=os.getenv("SECURITY_TWILIO_ACCOUNT_SID","").strip()
    token=os.getenv("SECURITY_TWILIO_AUTH_TOKEN","").strip()
    if not account or not token: raise RuntimeError("Twilio credentials are not configured")
    url=f"https://api.twilio.com/2010-04-01/Accounts/{account}.json"
    req=Request(url,headers={"Authorization":"Basic "+b64encode(f"{account}:{token}".encode()).decode()})
    with urlopen(req,timeout=TIMEOUT_SECONDS) as response:
        if not 200 <= response.status < 300: raise RuntimeError(f"Twilio returned HTTP {response.status}")

def _probe_webhook():
    from urllib.parse import urlparse
    url=os.getenv("SECURITY_ALERT_WEBHOOK_URL","").strip()
    parsed=urlparse(url)
    if parsed.scheme not in {"https","http"} or not parsed.hostname:
        raise RuntimeError("SECURITY_ALERT_WEBHOOK_URL is not configured with a valid HTTP(S) URL")
    port=parsed.port or (443 if parsed.scheme=="https" else 80)
    with socket.create_connection((parsed.hostname,port),timeout=TIMEOUT_SECONDS):
        pass

def run_provider_health_checks() -> dict:
    probes={"smtp":_probe_smtp,"twilio":_probe_twilio,"webhook":_probe_webhook}
    results={}
    for provider,probe in probes.items():
        try:
            probe(); record_provider_result(provider,True)
            results[provider]={"status":"healthy"}
        except Exception as exc:
            record_provider_result(provider,False,str(exc))
            results[provider]={"status":"degraded","error":str(exc)[:300]}
    return results


def queue_channel_failover(db, job, alert) -> str | None:
    """Queue the next eligible channel according to this admin's routing policy."""
    from app.models import SecurityNotificationPreference, SecurityNotificationDelivery
    if not job.admin_id:
        return None
    pref=db.query(SecurityNotificationPreference).filter_by(admin_id=job.admin_id).first()
    if not pref or not pref.failover_enabled:
        return None
    enabled = {
        "email": pref.email_enabled and pref.email_verified and bool(pref.email_address),
        "sms": pref.sms_enabled and pref.phone_verified and bool(pref.phone_number),
        "webhook": pref.webhook_enabled and bool(os.getenv("SECURITY_ALERT_WEBHOOK_URL","").strip()),
    }
    priority=[c.strip() for c in (pref.channel_priority or "email,sms,webhook").split(",")]
    try: current=priority.index(job.channel)
    except ValueError: current=-1
    for channel in priority[current+1:]:
        if channel not in enabled or not enabled[channel]:
            continue
        exists=db.query(SecurityNotificationDelivery).filter_by(
            alert_id=job.alert_id, admin_id=job.admin_id, channel=channel).first()
        if exists:
            continue
        db.add(SecurityNotificationDelivery(
            alert_id=job.alert_id, admin_id=job.admin_id, channel=channel,
            status="pending", next_attempt_at=datetime.utcnow(),
            recipient_email=pref.email_address if channel=="email" else None,
            recipient_phone=pref.phone_number if channel=="sms" else None))
        return channel
    return None
