"""Queue, retry and monitor signed audit checkpoint archive jobs."""
from __future__ import annotations
import logging
import urllib.request
import json
from datetime import datetime, timedelta
from sqlalchemy import or_
from app.core.config import settings
from app.models import AuditCheckpoint, AuditArchiveJob
from app.services.audit_archive import archive_checkpoint

logger = logging.getLogger("elsewhere.audit_archive.jobs")

def enqueue_checkpoint(db, checkpoint_id: str, created_by: str | None = None):
    checkpoint = db.get(AuditCheckpoint, checkpoint_id)
    if checkpoint is None:
        raise ValueError("Audit checkpoint not found")
    existing = db.query(AuditArchiveJob).filter(
        AuditArchiveJob.checkpoint_id == checkpoint_id,
        AuditArchiveJob.status.in_(["pending", "processing", "completed"])
    ).first()
    if existing:
        return existing
    job = AuditArchiveJob(checkpoint_id=checkpoint_id, created_by=created_by,
                          status="pending", next_attempt_at=datetime.utcnow())
    db.add(job)
    db.commit()
    db.refresh(job)
    return job

def _notify_failure(job: AuditArchiveJob):
    url = settings.audit_archive_failure_webhook_url.strip()
    if not url:
        logger.error("audit_archive_job_failed job_id=%s checkpoint_id=%s attempts=%s",
                     job.id, job.checkpoint_id, job.attempts)
        return
    payload = json.dumps({
        "event": "elsewhere.audit_archive.failed",
        "job_id": job.id, "checkpoint_id": job.checkpoint_id,
        "attempts": job.attempts, "error": (job.last_error or "")[:500],
    }).encode()
    request = urllib.request.Request(url, data=payload,
        headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=4):
            pass
    except Exception:
        logger.exception("audit archive failure webhook delivery failed job_id=%s", job.id)

def process_due_archive_jobs(db, batch_size: int = 20) -> dict:
    now = datetime.utcnow()
    jobs = db.query(AuditArchiveJob).filter(
        AuditArchiveJob.status.in_(["pending", "retry"]),
        AuditArchiveJob.next_attempt_at <= now
    ).order_by(AuditArchiveJob.next_attempt_at.asc()).limit(max(1, min(batch_size, 100))).all()
    result = {"processed": 0, "completed": 0, "retrying": 0, "failed": 0}
    for job in jobs:
        result["processed"] += 1
        job.status = "processing"
        job.attempts += 1
        db.commit()
        try:
            checkpoint = db.get(AuditCheckpoint, job.checkpoint_id)
            if checkpoint is None:
                raise ValueError("Audit checkpoint no longer exists")
            archive = archive_checkpoint(db, checkpoint, job.created_by or "")
            job.archive_id = archive.id
            job.status = "completed"
            job.last_error = None
            job.completed_at = datetime.utcnow()
            db.commit()
            result["completed"] += 1
        except Exception as exc:
            db.rollback()
            job = db.get(AuditArchiveJob, job.id)
            job.last_error = f"{type(exc).__name__}: {str(exc)}"[:2000]
            if job.attempts >= job.max_attempts:
                job.status = "failed"
                result["failed"] += 1
                db.commit()
                _notify_failure(job)
            else:
                delay = min(settings.audit_archive_retry_max_seconds,
                            settings.audit_archive_retry_base_seconds * (2 ** max(0, job.attempts - 1)))
                job.status = "retry"
                job.next_attempt_at = datetime.utcnow() + timedelta(seconds=max(5, delay))
                db.commit()
                result["retrying"] += 1
    return result
