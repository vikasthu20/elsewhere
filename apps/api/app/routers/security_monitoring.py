"""Admin security event monitoring and alert rule management."""
from datetime import datetime, timedelta
import os
import json
import hashlib
import secrets
import hmac
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.db import get_db
from app.models import User, SecurityEvent, SecurityAlert, SecurityAlertRule, SecurityAlertDelivery, SecurityNotificationDelivery, SecurityNotificationPreference, SecurityNotificationVerification, SecurityNotificationTemplate, SecurityNotificationProviderHealth
from app.security import require_roles
from app.core.redis_security import get_redis_client
from app.services.security_notification_delivery import send_verification_code, _send_channel
from app.services.notification_provider_resilience import run_provider_health_checks

router = APIRouter()

class AlertRuleIn(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    event_type: str = Field(min_length=3, max_length=60)
    threshold: int = Field(ge=1, le=10000)
    window_minutes: int = Field(ge=1, le=1440)
    severity: str = Field(pattern="^(low|medium|high|critical)$")
    enabled: bool = True

@router.get("/admin/security/events", tags=["security"])
def security_events(limit: int = 100, db: Session = Depends(get_db),
                    _admin: User = Depends(require_roles("admin"))):
    limit = max(1, min(limit, 500))
    rows = db.query(SecurityEvent).order_by(SecurityEvent.created_at.desc()).limit(limit).all()
    return [{"id": x.id, "event_type": x.event_type, "severity": x.severity,
             "source_hash": x.source_hash[:12], "request_path": x.request_path,
             "request_method": x.request_method, "response_status": x.response_status,
             "details": json.loads(x.details_json or "{}"), "created_at": x.created_at.isoformat()}
            for x in rows]

@router.get("/admin/security/alerts", tags=["security"])
def security_alerts(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    rows = db.query(SecurityAlert).order_by(SecurityAlert.created_at.desc()).limit(200).all()
    return [{"id": x.id, "event_type": x.event_type, "severity": x.severity,
             "title": x.title, "summary": x.summary, "event_count": x.event_count,
             "status": x.status, "created_at": x.created_at.isoformat()} for x in rows]

@router.post("/admin/security/alerts/{alert_id}/acknowledge", tags=["security"])
def acknowledge_security_alert(alert_id: str, db: Session = Depends(get_db),
                                admin: User = Depends(require_roles("admin"))):
    alert = db.get(SecurityAlert, alert_id)
    if not alert: raise HTTPException(404, "Security alert not found")
    now = datetime.utcnow()
    alert.status = "acknowledged"
    alert.acknowledged_by = admin.id
    alert.acknowledged_at = now
    delivery = db.query(SecurityAlertDelivery).filter(
        SecurityAlertDelivery.alert_id == alert.id,
        SecurityAlertDelivery.admin_id == admin.id).first()
    if delivery is None:
        delivery = SecurityAlertDelivery(alert_id=alert.id, admin_id=admin.id,
                                         delivered_at=alert.created_at or now)
        db.add(delivery)
    delivery.acknowledged_at = now
    db.commit()
    return {"message": "Alert acknowledged"}

@router.get("/admin/security/alerts/{alert_id}/delivery", tags=["security"])
def security_alert_delivery(alert_id: str, db: Session = Depends(get_db),
                             admin: User = Depends(require_roles("admin"))):
    alert = db.get(SecurityAlert, alert_id)
    if not alert:
        raise HTTPException(404, "Security alert not found")
    row = db.query(SecurityAlertDelivery).filter(
        SecurityAlertDelivery.alert_id == alert_id,
        SecurityAlertDelivery.admin_id == admin.id).first()
    return {"alert_id": alert_id, "admin_id": admin.id,
            "delivered_at": row.delivered_at.isoformat() if row else None,
            "acknowledged_at": row.acknowledged_at.isoformat() if row and row.acknowledged_at else None}

@router.get("/admin/security/alert-rules", tags=["security"])
def list_security_alert_rules(db: Session = Depends(get_db),
                              _admin: User = Depends(require_roles("admin"))):
    rows = db.query(SecurityAlertRule).order_by(SecurityAlertRule.name).all()
    return [{"id": x.id, "name": x.name, "event_type": x.event_type,
             "threshold": x.threshold, "window_minutes": x.window_minutes,
             "severity": x.severity, "enabled": x.enabled} for x in rows]

@router.post("/admin/security/alert-rules", status_code=201, tags=["security"])
def create_security_alert_rule(data: AlertRuleIn, db: Session = Depends(get_db),
                               _admin: User = Depends(require_roles("admin"))):
    if db.query(SecurityAlertRule).filter(SecurityAlertRule.name == data.name).first():
        raise HTTPException(409, "A rule with this name already exists")
    rule = SecurityAlertRule(**data.model_dump())
    db.add(rule); db.commit(); db.refresh(rule)
    return {"id": rule.id, "name": rule.name}

@router.get("/admin/security/summary", tags=["security"])
def security_summary(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    since = datetime.utcnow() - timedelta(hours=24)
    events = db.query(SecurityEvent).filter(SecurityEvent.created_at >= since).count()
    open_alerts = db.query(SecurityAlert).filter(SecurityAlert.status == "open").count()
    critical = db.query(SecurityEvent).filter(SecurityEvent.created_at >= since,
        SecurityEvent.severity == "critical").count()
    by_type = db.query(SecurityEvent.event_type, func.count(SecurityEvent.id)).filter(
        SecurityEvent.created_at >= since).group_by(SecurityEvent.event_type).all()
    return {"events_24h": events, "open_alerts": open_alerts, "critical_events_24h": critical,
            "by_type": [{"event_type": k, "count": v} for k, v in by_type]}


DLQ_STREAM = "elsewhere:security:alert-stream:dead-letter:v1"
ALERT_STREAM = "elsewhere:security:alert-stream:v1"

@router.get("/admin/security/dead-letter", tags=["security"])
def list_security_dead_letters(limit: int = 100,
                               _admin: User = Depends(require_roles("admin"))):
    """List retained dead-letter events; payloads are intentionally returned as compact envelopes."""
    client = get_redis_client()
    if client is None:
        raise HTTPException(503, "Redis is unavailable")
    limit = max(1, min(limit, 500))
    rows = client.xrevrange(DLQ_STREAM, count=limit)
    return [{"id": event_id, "source_id": fields.get("source_id"),
             "error": fields.get("error"), "payload": fields.get("payload")}
            for event_id, fields in rows]

class DeadLetterReplayIn(BaseModel):
    dead_letter_id: str = Field(min_length=3, max_length=80)

@router.post("/admin/security/dead-letter/replay", tags=["security"])
def replay_security_dead_letter(data: DeadLetterReplayIn,
                                admin: User = Depends(require_roles("admin"))):
    client = get_redis_client()
    if client is None:
        raise HTTPException(503, "Redis is unavailable")
    entry = client.xrange(DLQ_STREAM, min=data.dead_letter_id, max=data.dead_letter_id, count=1)
    if not entry:
        raise HTTPException(404, "Dead-letter event not found")
    _event_id, fields = entry[0]
    try:
        envelope = json.loads(fields.get("payload") or "{}")
    except (TypeError, ValueError):
        raise HTTPException(422, "Dead-letter payload is not valid JSON")
    if envelope.get("type") != "alert_changed" or not envelope.get("alert_id"):
        raise HTTPException(422, "Dead-letter payload is not a supported alert event")
    replay_id = client.xadd(ALERT_STREAM, envelope)
    # Keep the original DLQ record for traceability; replay is non-destructive.
    return {"message": "Alert event queued for replay", "replay_event_id": replay_id,
            "dead_letter_id": data.dead_letter_id, "requested_by": admin.id}

@router.get("/admin/security/notifications/webhook-status", tags=["security"])
def security_notification_webhook_status(_admin: User = Depends(require_roles("admin"))):
    configured = bool(os.getenv("SECURITY_ALERT_WEBHOOK_URL", "").strip())
    return {"configured": configured, "delivery_mode": "manual_test_only"}


@router.post("/admin/security/notifications/test-webhook", tags=["security"])
def test_security_notification_webhook(admin: User = Depends(require_roles("admin"))):
    """Send a minimal test message to an explicitly configured operations webhook."""
    webhook = os.getenv("SECURITY_ALERT_WEBHOOK_URL", "").strip()
    if not webhook:
        raise HTTPException(503, "SECURITY_ALERT_WEBHOOK_URL is not configured")
    from urllib.request import Request, urlopen
    from urllib.error import URLError, HTTPError
    body = json.dumps({"type": "security_notification_test",
                       "message": "Elsewhere security notification test",
                       "requested_by": admin.id}).encode("utf-8")
    request = Request(webhook, data=body, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urlopen(request, timeout=5) as response:
            status = response.status
    except (URLError, HTTPError, TimeoutError) as exc:
        raise HTTPException(502, f"Notification webhook delivery failed: {str(exc)[:200]}")
    if status < 200 or status >= 300:
        raise HTTPException(502, f"Notification webhook returned HTTP {status}")
    return {"message": "Test notification delivered", "status_code": status}


@router.get("/admin/security/notifications/deliveries", tags=["security"])
def security_notification_deliveries(limit: int = 100, status: str = "all",
                                    db: Session = Depends(get_db),
                                    _admin: User = Depends(require_roles("admin"))):
    limit = max(1, min(limit, 500))
    query = db.query(SecurityNotificationDelivery).order_by(SecurityNotificationDelivery.created_at.desc())
    if status in {"pending", "retry", "delivered", "failed"}:
        query = query.filter(SecurityNotificationDelivery.status == status)
    elif status != "all":
        raise HTTPException(422, "Unsupported delivery status")
    rows = query.limit(limit).all()
    return [{"id": x.id, "alert_id": x.alert_id, "channel": x.channel,
             "status": x.status, "attempts": x.attempts, "recipient": (x.recipient_email or x.recipient_phone or "server-configured"),
             "next_attempt_at": x.next_attempt_at.isoformat() if x.next_attempt_at else None,
             "last_attempt_at": x.last_attempt_at.isoformat() if x.last_attempt_at else None,
             "delivered_at": x.delivered_at.isoformat() if x.delivered_at else None,
             "last_error": x.last_error, "response_status": x.response_status,
             "locked_at": x.locked_at.isoformat() if x.locked_at else None,
             "escalation_status": x.escalation_status,
             "escalation_attempts": x.escalation_attempts,
             "escalation_sent_at": x.escalation_sent_at.isoformat() if x.escalation_sent_at else None,
             "created_at": x.created_at.isoformat()} for x in rows]


class SecurityNotificationPreferenceIn(BaseModel):
    email_enabled: bool = False
    sms_enabled: bool = False
    webhook_enabled: bool = True
    delivery_mode: str = Field(default="parallel", pattern="^(parallel|priority)$")
    channel_priority: str = Field(default="email,sms,webhook", max_length=60)
    failover_enabled: bool = True
    email_address: str | None = Field(default=None, max_length=255)
    phone_number: str | None = Field(default=None, max_length=30)
    severity_low: bool = False
    severity_medium: bool = True
    severity_high: bool = True
    severity_critical: bool = True

@router.get("/admin/security/notifications/preferences", tags=["security"])
def get_security_notification_preferences(db: Session = Depends(get_db),
                                          admin: User = Depends(require_roles("admin"))):
    row = db.query(SecurityNotificationPreference).filter(
        SecurityNotificationPreference.admin_id == admin.id).first()
    if row is None:
        return {"email_enabled": False, "sms_enabled": False, "webhook_enabled": True,
                "email_address": admin.email, "phone_number": admin.phone, "delivery_mode": "parallel", "channel_priority": "email,sms,webhook", "failover_enabled": True,
                "severity_low": False, "severity_medium": True, "severity_high": True, "severity_critical": True, "email_verified": False, "phone_verified": False}
    return {"email_enabled": row.email_enabled, "sms_enabled": row.sms_enabled,
            "webhook_enabled": row.webhook_enabled, "delivery_mode": row.delivery_mode, "channel_priority": row.channel_priority, "failover_enabled": row.failover_enabled, "email_address": row.email_address or admin.email,
            "phone_number": row.phone_number or admin.phone, "severity_low": row.severity_low,
            "severity_medium": row.severity_medium, "severity_high": row.severity_high,
            "severity_critical": row.severity_critical, "email_verified": row.email_verified, "phone_verified": row.phone_verified}

@router.put("/admin/security/notifications/preferences", tags=["security"])
def update_security_notification_preferences(data: SecurityNotificationPreferenceIn,
                                              db: Session = Depends(get_db),
                                              admin: User = Depends(require_roles("admin"))):
    row = db.query(SecurityNotificationPreference).filter(
        SecurityNotificationPreference.admin_id == admin.id).first()
    if row is None:
        row = SecurityNotificationPreference(admin_id=admin.id)
        db.add(row)
    row.email_enabled = data.email_enabled
    row.sms_enabled = data.sms_enabled
    row.webhook_enabled = data.webhook_enabled
    row.delivery_mode = data.delivery_mode
    priorities = [x.strip() for x in data.channel_priority.split(",") if x.strip()]
    if len(priorities) != 3 or set(priorities) != {"email", "sms", "webhook"}:
        raise HTTPException(422, "Channel priority must contain email,sms,webhook exactly once")
    row.channel_priority = ",".join(priorities)
    row.failover_enabled = data.failover_enabled
    new_email = data.email_address.strip() if data.email_address else None
    new_phone = data.phone_number.strip() if data.phone_number else None
    if new_email != row.email_address:
        row.email_verified = False
    if new_phone != row.phone_number:
        row.phone_verified = False
    row.email_address = new_email
    row.phone_number = new_phone
    row.severity_low = data.severity_low
    row.severity_medium = data.severity_medium
    row.severity_high = data.severity_high
    row.severity_critical = data.severity_critical
    db.commit()
    return {"email_enabled": row.email_enabled, "sms_enabled": row.sms_enabled,
            "webhook_enabled": row.webhook_enabled, "delivery_mode": row.delivery_mode, "channel_priority": row.channel_priority, "failover_enabled": row.failover_enabled, "email_address": row.email_address or admin.email,
            "phone_number": row.phone_number or admin.phone, "severity_low": row.severity_low,
            "severity_medium": row.severity_medium, "severity_high": row.severity_high,
            "severity_critical": row.severity_critical, "email_verified": row.email_verified, "phone_verified": row.phone_verified}


class NotificationVerificationRequest(BaseModel):
    channel: str = Field(pattern="^(email|sms)$")

class NotificationVerificationConfirm(BaseModel):
    channel: str = Field(pattern="^(email|sms)$")
    code: str = Field(min_length=6, max_length=6)

class NotificationTemplateIn(BaseModel):
    channel: str = Field(pattern="^(email|sms)$")
    subject_template: str = Field(default="", max_length=200)
    body_template: str = Field(min_length=1, max_length=4000)

@router.post("/admin/security/notifications/verify/send", tags=["security"])
def send_notification_verification(data: NotificationVerificationRequest,
                                   db: Session = Depends(get_db),
                                   admin: User = Depends(require_roles("admin"))):
    pref = db.query(SecurityNotificationPreference).filter_by(admin_id=admin.id).first()
    destination = ((pref.email_address if pref and pref.email_address else admin.email)
                   if data.channel == "email" else
                   (pref.phone_number if pref and pref.phone_number else admin.phone))
    if not destination:
        raise HTTPException(400, "Add a contact destination before requesting verification")
    if pref is None:
        pref = SecurityNotificationPreference(admin_id=admin.id)
        db.add(pref)
        db.flush()
    verified = pref.email_verified if data.channel == "email" else pref.phone_verified
    if verified:
        raise HTTPException(409, "This contact is already verified")
    recent = db.query(SecurityNotificationVerification).filter_by(
        admin_id=admin.id, channel=data.channel).order_by(
        SecurityNotificationVerification.created_at.desc()).first()
    now = datetime.utcnow()
    if recent and (now - recent.created_at).total_seconds() < 60:
        raise HTTPException(429, "Wait 60 seconds before requesting another code")
    code = f"{secrets.randbelow(1000000):06d}"
    digest = hashlib.sha256(f"{admin.id}:{data.channel}:{destination}:{code}".encode()).hexdigest()
    row = SecurityNotificationVerification(admin_id=admin.id, channel=data.channel,
        destination=destination, code_hash=digest, expires_at=now + timedelta(minutes=10))
    db.add(row)
    try:
        send_verification_code(data.channel, destination, code)
        db.commit()
    except Exception as exc:
        db.rollback()
        raise HTTPException(502, f"Unable to send verification code: {str(exc)[:180]}")
    return {"sent": True, "channel": data.channel, "destination": destination,
            "expires_in_seconds": 600}

@router.post("/admin/security/notifications/verify/confirm", tags=["security"])
def confirm_notification_verification(data: NotificationVerificationConfirm,
                                      db: Session = Depends(get_db),
                                      admin: User = Depends(require_roles("admin"))):
    row = db.query(SecurityNotificationVerification).filter_by(
        admin_id=admin.id, channel=data.channel, verified_at=None).order_by(
        SecurityNotificationVerification.created_at.desc()).first()
    if row is None or row.expires_at < datetime.utcnow():
        raise HTTPException(400, "Verification code is missing or expired")
    if row.attempts >= 5:
        raise HTTPException(429, "Too many incorrect codes; request a new code later")
    digest = hashlib.sha256(f"{admin.id}:{data.channel}:{row.destination}:{data.code}".encode()).hexdigest()
    if not hmac.compare_digest(digest, row.code_hash):
        row.attempts += 1
        db.commit()
        raise HTTPException(400, "Invalid verification code")
    pref = db.query(SecurityNotificationPreference).filter_by(admin_id=admin.id).first()
    if pref is None:
        raise HTTPException(400, "Notification preferences not found")
    if data.channel == "email":
        pref.email_address = row.destination
        pref.email_verified = True
    else:
        pref.phone_number = row.destination
        pref.phone_verified = True
    row.verified_at = datetime.utcnow()
    db.commit()
    return {"verified": True, "channel": data.channel}

@router.get("/admin/security/notifications/templates", tags=["security"])
def list_notification_templates(db: Session = Depends(get_db),
                                _admin: User = Depends(require_roles("admin"))):
    return [{"channel": x.channel, "subject_template": x.subject_template,
             "body_template": x.body_template, "updated_at": x.updated_at.isoformat()}
            for x in db.query(SecurityNotificationTemplate).all()]

@router.put("/admin/security/notifications/templates", tags=["security"])
def save_notification_template(data: NotificationTemplateIn, db: Session = Depends(get_db),
                               admin: User = Depends(require_roles("admin"))):
    allowed = {"severity", "title", "summary", "event_type", "alert_id"}
    try:
        fields = {name for _, name, _, _ in string.Formatter().parse(data.body_template) if name}
        if data.subject_template:
            fields |= {name for _, name, _, _ in string.Formatter().parse(data.subject_template) if name}
    except ValueError:
        raise HTTPException(422, "Template contains invalid formatting syntax")
    if fields - allowed:
        raise HTTPException(422, f"Unsupported template placeholders: {', '.join(sorted(fields - allowed))}")
    row = db.query(SecurityNotificationTemplate).filter_by(channel=data.channel).first()
    if row is None:
        row = SecurityNotificationTemplate(channel=data.channel)
        db.add(row)
    row.subject_template = data.subject_template
    row.body_template = data.body_template
    row.updated_by = admin.id
    db.commit()
    return {"channel": row.channel, "subject_template": row.subject_template,
            "body_template": row.body_template}

@router.post("/admin/security/notifications/test", tags=["security"])
def test_notification_delivery(channel: str, db: Session = Depends(get_db),
                               admin: User = Depends(require_roles("admin"))):
    if channel not in {"email", "sms"}:
        raise HTTPException(422, "Test channel must be email or sms")
    pref = db.query(SecurityNotificationPreference).filter_by(admin_id=admin.id).first()
    if not pref:
        raise HTTPException(400, "Save notification preferences first")
    if channel == "email":
        if not pref.email_verified or not pref.email_enabled:
            raise HTTPException(400, "Enable email and verify the email address first")
        destination = pref.email_address or admin.email
    else:
        if not pref.phone_verified or not pref.sms_enabled:
            raise HTTPException(400, "Enable SMS and verify the phone number first")
        destination = pref.phone_number or admin.phone
    from types import SimpleNamespace
    template = db.query(SecurityNotificationTemplate).filter_by(channel=channel).first()
    alert = SimpleNamespace(id="test", severity="medium", title="Test security notification",
        summary="This is a test message from Elsewhere security notification settings.",
        event_type="notification.test", event_count=1, created_at=datetime.utcnow())
    if template:
        values = {"severity":"MEDIUM", "title":alert.title, "summary":alert.summary,
                  "event_type":alert.event_type, "alert_id":alert.id}
        subject = template.subject_template.format_map(values) if template.subject_template else ""
        body = template.body_template.format_map(values)
        if channel == "email":
            # Send the configured subject/body using the existing SMTP transport.
            from email.message import EmailMessage
            import smtplib, os
            host=os.getenv("SECURITY_SMTP_HOST","").strip(); sender=os.getenv("SECURITY_EMAIL_FROM","").strip()
            if not host or not sender: raise HTTPException(503, "SMTP is not configured")
            msg=EmailMessage(); msg["Subject"]=subject or "Elsewhere test notification"
            msg["From"]=sender; msg["To"]=destination; msg.set_content(body)
            with smtplib.SMTP(host,int(os.getenv("SECURITY_SMTP_PORT","587")),timeout=8) as smtp:
                if os.getenv("SECURITY_SMTP_STARTTLS","true").lower()=="true": smtp.starttls()
                user=os.getenv("SECURITY_SMTP_USERNAME","")
                if user: smtp.login(user,os.getenv("SECURITY_SMTP_PASSWORD",""))
                smtp.send_message(msg)
        else:
            from urllib.parse import urlencode
            from urllib.request import Request, urlopen
            from base64 import b64encode
            account=os.getenv("SECURITY_TWILIO_ACCOUNT_SID","").strip()
            auth=os.getenv("SECURITY_TWILIO_AUTH_TOKEN","").strip()
            sender=os.getenv("SECURITY_TWILIO_FROM","").strip()
            if not all((account,auth,sender)): raise HTTPException(503, "Twilio is not configured")
            url=f"https://api.twilio.com/2010-04-01/Accounts/{account}/Messages.json"
            req=Request(url,data=urlencode({"From":sender,"To":destination,"Body":body}).encode(),
                headers={"Authorization":"Basic "+b64encode(f"{account}:{auth}".encode()).decode(),
                         "Content-Type":"application/x-www-form-urlencoded"},method="POST")
            with urlopen(req,timeout=8) as response:
                if not 200 <= response.status < 300: raise HTTPException(502,"SMS provider rejected test")
    else:
        try:
            _send_channel(channel, alert, "", destination if channel=="email" else None,
                          destination if channel=="sms" else None)
        except Exception as exc:
            raise HTTPException(502, f"Test delivery failed: {str(exc)[:180]}")
    return {"sent": True, "channel": channel, "destination": destination}


@router.get("/admin/security/notifications/analytics", tags=["security"])
def security_notification_analytics(days: int = 7, db: Session = Depends(get_db),
                                    _admin: User = Depends(require_roles("admin"))):
    days = max(1, min(days, 90))
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(SecurityNotificationDelivery).filter(
        SecurityNotificationDelivery.created_at >= since).all()
    total = len(rows)
    delivered = sum(1 for x in rows if x.status == "delivered")
    failed = sum(1 for x in rows if x.status == "failed")
    pending = sum(1 for x in rows if x.status in {"pending", "processing", "retry"})
    by_channel = {}
    for channel in ("email", "sms", "webhook"):
        channel_rows = [x for x in rows if x.channel == channel]
        by_channel[channel] = {
            "total": len(channel_rows),
            "delivered": sum(1 for x in channel_rows if x.status == "delivered"),
            "failed": sum(1 for x in channel_rows if x.status == "failed"),
            "pending": sum(1 for x in channel_rows if x.status in {"pending", "processing", "retry"}),
        }
    provider_health = []
    for channel, values in by_channel.items():
        channel_rows = [x for x in rows if x.channel == channel]
        latest = max(channel_rows, key=lambda x: x.last_attempt_at or x.created_at, default=None)
        if not values["total"]:
            state = "no_activity"
        elif values["failed"]:
            state = "degraded"
        elif values["pending"]:
            state = "attention"
        else:
            state = "healthy"
        provider_health.append({
            "channel": channel, "status": state,
            "last_attempt_at": (latest.last_attempt_at or latest.created_at).isoformat() if latest else None,
            "last_error": latest.last_error if latest and latest.status == "failed" else None,
            "delivered": values["delivered"], "failed": values["failed"],
            "pending": values["pending"],
        })
    return {"period_days": days, "since": since.isoformat(), "total": total,
            "delivered": delivered, "failed": failed, "pending": pending,
            "success_rate": round(delivered / total * 100, 1) if total else None,
            "by_channel": by_channel, "provider_health": provider_health}

@router.get("/admin/security/notifications/history", tags=["security"])
def security_notification_history(limit: int = 100, days: int = 30,
                                  db: Session = Depends(get_db),
                                  _admin: User = Depends(require_roles("admin"))):
    limit = max(1, min(limit, 500))
    days = max(1, min(days, 90))
    since = datetime.utcnow() - timedelta(days=days)
    rows = db.query(SecurityNotificationDelivery, SecurityAlert).join(
        SecurityAlert, SecurityAlert.id == SecurityNotificationDelivery.alert_id
    ).filter(SecurityNotificationDelivery.created_at >= since).order_by(
        SecurityNotificationDelivery.created_at.desc()).limit(limit).all()
    return [{
        "id": delivery.id, "alert_id": alert.id, "title": alert.title,
        "event_type": alert.event_type, "severity": alert.severity,
        "channel": delivery.channel, "status": delivery.status,
        "attempts": delivery.attempts, "response_status": delivery.response_status,
        "recipient": delivery.recipient_email or delivery.recipient_phone or "server-configured",
        "created_at": delivery.created_at.isoformat(),
        "last_attempt_at": delivery.last_attempt_at.isoformat() if delivery.last_attempt_at else None,
        "delivered_at": delivery.delivered_at.isoformat() if delivery.delivered_at else None,
        "last_error": delivery.last_error,
        "escalation_status": delivery.escalation_status,
    } for delivery, alert in rows]


@router.get("/admin/security/notifications/provider-health", tags=["security"])
def notification_provider_health(db: Session = Depends(get_db),
                                 _admin: User = Depends(require_roles("admin"))):
    rows = db.query(SecurityNotificationProviderHealth).order_by(
        SecurityNotificationProviderHealth.provider).all()
    now = datetime.utcnow()
    return [{
        "provider": row.provider, "status": (
            "open" if row.circuit_open_until and row.circuit_open_until > now else row.status),
        "consecutive_failures": row.consecutive_failures,
        "last_checked_at": row.last_checked_at.isoformat() if row.last_checked_at else None,
        "last_success_at": row.last_success_at.isoformat() if row.last_success_at else None,
        "last_failure_at": row.last_failure_at.isoformat() if row.last_failure_at else None,
        "last_error": row.last_error,
        "circuit_open_until": row.circuit_open_until.isoformat() if row.circuit_open_until else None,
    } for row in rows]

@router.post("/admin/security/notifications/provider-health/check", tags=["security"])
def trigger_provider_health_checks(_admin: User = Depends(require_roles("admin"))):
    return {"results": run_provider_health_checks()}


@router.get("/admin/security/notifications/sla", tags=["security"])
def security_notification_sla(days: int = 7, db: Session = Depends(get_db),
                              _admin: User = Depends(require_roles("admin"))):
    """Return delivery latency and outstanding SLA breach metrics."""
    days = max(1, min(days, 90))
    sla_seconds = max(60, int(os.getenv("SECURITY_NOTIFICATION_SLA_SECONDS", "900")))
    now = datetime.utcnow()
    since = now - timedelta(days=days)
    rows = db.query(SecurityNotificationDelivery).filter(
        SecurityNotificationDelivery.created_at >= since).all()
    delivered = [x for x in rows if x.status == "delivered" and x.delivered_at]
    latencies = [(x.delivered_at - x.created_at).total_seconds() for x in delivered]
    overdue = [x for x in rows if x.status in {"pending", "processing", "retry"}
               and (now - x.created_at).total_seconds() > sla_seconds]
    within = sum(1 for seconds in latencies if seconds <= sla_seconds)
    return {
        "period_days": days, "sla_seconds": sla_seconds,
        "total_deliveries": len(rows), "delivered": len(delivered),
        "within_sla": within,
        "within_sla_rate": round(within / len(delivered) * 100, 1) if delivered else None,
        "average_delivery_seconds": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "max_delivery_seconds": round(max(latencies), 1) if latencies else None,
        "currently_overdue": len(overdue),
        "overdue_by_channel": {
            channel: sum(1 for x in overdue if x.channel == channel)
            for channel in ("email", "sms", "webhook")
        },
        "oldest_overdue_seconds": int(max(
            ((now - x.created_at).total_seconds() for x in overdue), default=0)),
    }
