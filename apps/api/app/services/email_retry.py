"""Database-backed automatic retry worker for notification emails."""
import html
import os
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from sqlalchemy import update
from app.db import SessionLocal
from app.models import NotificationEmailLog

MAX_ATTEMPTS = 3
POLL_SECONDS = 30
BACKOFF_MINUTES = (1, 5, 20)

def _send(row):
    host = os.getenv("SMTP_HOST", "").strip()
    sender = os.getenv("SMTP_FROM", "").strip()
    if not host or not sender:
        raise RuntimeError("SMTP_HOST or SMTP_FROM is not configured.")
    message = EmailMessage()
    message["Subject"], message["From"], message["To"] = row.subject, sender, row.recipient_email
    message.set_content("ELSEWHERE | TRAVEL, THOUGHTFULLY DISCOVERED\n\n" + (row.email_body or "") + "\n\nSign in to Elsewhere to view details.\n")
    title = html.escape(row.subject.removeprefix("Elsewhere update: "))
    body = html.escape(row.email_body or "").replace("\n", "<br>")
    html_body = ('<html><body style="background:#f5f2eb;font-family:Arial;color:#242720">'
                 '<div style="max-width:600px;margin:32px auto;padding:32px;background:#fff">'
                 '<p style="letter-spacing:3px;color:#718071">ELSEWHERE</p><h1>' + title +
                 '</h1><p style="line-height:1.7">' + body +
                 '</p><p>Travel, thoughtfully discovered.</p></div></body></html>')
    message.add_alternative(html_body, subtype="html")
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=5) as server:
        if os.getenv("SMTP_STARTTLS", "true").lower() in ("1", "true", "yes"):
            server.starttls()
        username = os.getenv("SMTP_USER", "").strip()
        if username:
            server.login(username, os.getenv("SMTP_PASSWORD", ""))
        server.send_message(message)

def process_due_email_retries(batch_size=20):
    now = datetime.utcnow()
    db = SessionLocal()
    try:
        stale_before = now - timedelta(minutes=10)
        stale_rows = db.query(NotificationEmailLog).filter(
            NotificationEmailLog.status == "retrying",
            NotificationEmailLog.retry_started_at.is_not(None),
            NotificationEmailLog.retry_started_at <= stale_before,
        ).all()
        for stale in stale_rows:
            stale.retry_count = (stale.retry_count or 0) + 1
            stale.status = "dead_letter" if stale.retry_count >= MAX_ATTEMPTS else "failed"
            stale.error_message = "Retry worker lease expired; delivery outcome is unknown."
            stale.retry_started_at = None
            stale.next_retry_at = (now + timedelta(minutes=BACKOFF_MINUTES[min(stale.retry_count - 1, 2)])) if stale.retry_count < MAX_ATTEMPTS else None
        db.commit()
        due_ids = [r[0] for r in db.query(NotificationEmailLog.id).filter(
            NotificationEmailLog.status == "failed",
            NotificationEmailLog.email_body.is_not(None),
            NotificationEmailLog.retry_count < MAX_ATTEMPTS,
            NotificationEmailLog.next_retry_at.is_not(None),
            NotificationEmailLog.next_retry_at <= now
        ).order_by(NotificationEmailLog.next_retry_at.asc()).limit(batch_size).all()]
    finally:
        db.close()
    processed = 0
    for log_id in due_ids:
        claim = SessionLocal()
        try:
            result = claim.execute(update(NotificationEmailLog).where(
                NotificationEmailLog.id == log_id,
                NotificationEmailLog.status == "failed",
                NotificationEmailLog.retry_count < MAX_ATTEMPTS,
                NotificationEmailLog.next_retry_at <= now
            ).values(status="retrying", retry_started_at=now))
            claim.commit()
            if result.rowcount != 1:
                continue
        finally:
            claim.close()
        db = SessionLocal()
        try:
            row = db.get(NotificationEmailLog, log_id)
            if row is None:
                continue
            try:
                _send(row)
                row.status, row.sent_at, row.error_message, row.next_retry_at, row.retry_started_at = "sent", datetime.utcnow(), None, None, None
            except Exception as exc:
                row.retry_count = (row.retry_count or 0) + 1
                row.status = "failed"
                row.error_message = str(exc)[:1000]
                row.next_retry_at = (datetime.utcnow() + timedelta(minutes=BACKOFF_MINUTES[min(row.retry_count - 1, 2)])) if row.retry_count < MAX_ATTEMPTS else None
                row.retry_started_at = None
            else:
                row.retry_count = (row.retry_count or 0) + 1
            db.commit()
            processed += 1
        finally:
            db.close()
    return processed

def run_email_retry_loop(stop_event):
    while not stop_event.is_set():
        try:
            process_due_email_retries()
        except Exception:
            pass
        stop_event.wait(POLL_SECONDS)
