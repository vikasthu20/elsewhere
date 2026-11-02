"""Admin queue controls and archive job monitoring."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, AuditCheckpoint, AuditArchiveJob
from app.security import require_roles
from app.services.audit_archive_jobs import enqueue_checkpoint, process_due_archive_jobs

router = APIRouter()

@router.post("/admin/audit/checkpoints/{checkpoint_id}/archive-jobs", tags=["audit"])
def enqueue_audit_archive(checkpoint_id: str, db: Session = Depends(get_db),
                          admin: User = Depends(require_roles("admin"))):
    try:
        job = enqueue_checkpoint(db, checkpoint_id, admin.id)
    except ValueError as exc:
        raise HTTPException(404, detail=str(exc))
    return {"job_id": job.id, "checkpoint_id": job.checkpoint_id, "status": job.status,
            "attempts": job.attempts, "next_attempt_at": job.next_attempt_at.isoformat()}

@router.get("/admin/audit/archive-jobs", tags=["audit"])
def list_audit_archive_jobs(status: str | None = None, db: Session = Depends(get_db),
                            _admin: User = Depends(require_roles("admin"))):
    query = db.query(AuditArchiveJob)
    if status:
        if status not in {"pending", "processing", "retry", "failed", "completed"}:
            raise HTTPException(400, "Invalid job status")
        query = query.filter(AuditArchiveJob.status == status)
    rows = query.order_by(AuditArchiveJob.created_at.desc()).limit(200).all()
    return [{"id": r.id, "checkpoint_id": r.checkpoint_id, "status": r.status,
             "attempts": r.attempts, "max_attempts": r.max_attempts,
             "next_attempt_at": r.next_attempt_at.isoformat(),
             "last_error": r.last_error, "archive_id": r.archive_id,
             "created_at": r.created_at.isoformat()} for r in rows]

@router.post("/admin/audit/archive-jobs/process", tags=["audit"])
def process_audit_jobs(batch_size: int = 20, db: Session = Depends(get_db),
                       _admin: User = Depends(require_roles("admin"))):
    # Useful for controlled operations; production should use the standalone worker.
    return process_due_archive_jobs(db, batch_size)
