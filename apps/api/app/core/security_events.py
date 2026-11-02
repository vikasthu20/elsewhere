"""Persist selected security response events and evaluate admin alert rules."""
import hashlib
import json
import logging
from datetime import datetime, timedelta
from app.db import SessionLocal
from app.models import SecurityEvent, SecurityAlert, SecurityAlertRule, SecurityNotificationDelivery, SecurityNotificationPreference, User

logger = logging.getLogger("elsewhere.security.events")
ALERT_CHANNEL = "elsewhere:security:alerts:v1"
ALERT_STREAM = "elsewhere:security:alert-stream:v1"
ALERT_STREAM_MAXLEN = 10000

def publish_security_alert(alert_id: str) -> None:
    """Publish an alert-created signal for WebSocket workers on every API instance."""
    try:
        from app.core.redis_security import get_redis_client
        client = get_redis_client()
        if client is not None:
            payload = {"type": "alert_changed", "alert_id": alert_id}
            # Redis Streams retain events for reconnecting consumers; Pub/Sub remains
            # as a low-latency wake-up signal for older consumers.
            client.xadd(ALERT_STREAM, payload, maxlen=ALERT_STREAM_MAXLEN, approximate=True)
            client.publish(ALERT_CHANNEL, json.dumps(payload))
    except Exception:
        logger.exception("Unable to publish security alert event")

def classify_security_event(path: str, status: int, headers) -> tuple[str, str] | None:
    if status == 429:
        return "rate_limit_block", "medium"
    if status == 403 and "challenge" in path:
        return "bot_challenge_block", "medium"
    if status == 401 and path.endswith("/auth/login"):
        return "login_failure", "low"
    if status == 403:
        return "authorization_denied", "low"
    return None

def persist_security_event(request, response):
    path = request.url.path
    classified = classify_security_event(path, response.status_code, response.headers)
    if not classified:
        return
    event_type, severity = classified
    raw_ip = request.client.host if request.client else "unknown"
    source_hash = hashlib.sha256(raw_ip.encode("utf-8")).hexdigest()
    event = None
    db = SessionLocal()
    try:
        event = SecurityEvent(event_type=event_type, severity=severity, source_hash=source_hash,
            request_path=path[:300], request_method=request.method[:12],
            response_status=response.status_code,
            details_json=json.dumps({"route": path[:180]}, separators=(",", ":")))
        db.add(event)
        db.flush()
        rules = db.query(SecurityAlertRule).filter(
            SecurityAlertRule.enabled.is_(True), SecurityAlertRule.event_type == event_type).all()
        now = datetime.utcnow()
        created_alert_ids = []
        for rule in rules:
            start = now - timedelta(minutes=rule.window_minutes)
            count = db.query(SecurityEvent).filter(SecurityEvent.event_type == event_type,
                SecurityEvent.source_hash == source_hash, SecurityEvent.created_at >= start).count()
            # Avoid generating repeated open alerts for every request in the same threshold window.
            existing = db.query(SecurityAlert).filter(SecurityAlert.rule_id == rule.id,
                SecurityAlert.status == "open", SecurityAlert.created_at >= start).first()
            if count >= rule.threshold and not existing:
                alert = SecurityAlert(rule_id=rule.id, event_type=event_type, severity=rule.severity,
                    title=f"{rule.name}: threshold reached",
                    summary=f"{count} matching events from one pseudonymized source within {rule.window_minutes} minutes.",
                    event_count=count, window_started_at=start)
                db.add(alert)
                db.flush()
                preferences = db.query(SecurityNotificationPreference).all()
                if preferences:
                    severity_field = f"severity_{rule.severity.lower()}"
                    for preference in preferences:
                        if not getattr(preference, severity_field, False):
                            continue
                        admin_user = db.get(User, preference.admin_id)
                        enabled_channels = {
                            "webhook": preference.webhook_enabled,
                            "email": preference.email_enabled and preference.email_verified,
                            "sms": preference.sms_enabled and preference.phone_verified,
                        }
                        ordered = [c.strip() for c in (preference.channel_priority or "email,sms,webhook").split(",")
                                   if c.strip() in enabled_channels and enabled_channels[c.strip()]]
                        if preference.delivery_mode == "priority":
                            ordered = ordered[:1]
                        for channel in ordered:
                            db.add(SecurityNotificationDelivery(
                                alert_id=alert.id, admin_id=preference.admin_id, channel=channel, status="pending",
                                next_attempt_at=now,
                                recipient_email=(preference.email_address or (admin_user.email if admin_user else None)) if channel == "email" else None,
                                recipient_phone=(preference.phone_number or (admin_user.phone if admin_user else None)) if channel == "sms" else None))
                else:
                    db.add(SecurityNotificationDelivery(alert_id=alert.id, channel="webhook",
                        status="pending", next_attempt_at=now))
                created_alert_ids.append(alert.id)
        db.commit()
        for alert_id in created_alert_ids:
            publish_security_alert(alert_id)
    except Exception:
        db.rollback()
        logger.exception("Unable to persist security event")
    finally:
        db.close()
