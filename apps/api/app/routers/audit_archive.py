"""Admin endpoints for immutable S3 audit evidence archival."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, AuditCheckpoint, AuditEvidenceArchive
from app.security import require_roles
from app.services.audit_archive import archive_checkpoint, verify_archive

router = APIRouter()

@router.post("/admin/audit/checkpoints/{checkpoint_id}/archive", tags=["audit"])
def archive_audit_checkpoint(checkpoint_id: str, db: Session = Depends(get_db),
                             admin: User = Depends(require_roles("admin"))):
    checkpoint = db.get(AuditCheckpoint, checkpoint_id)
    if not checkpoint:
        raise HTTPException(404, "Audit checkpoint not found")
    try:
        row = archive_checkpoint(db, checkpoint, admin.id)
    except RuntimeError as exc:
        raise HTTPException(503, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(409, detail=str(exc))
    except Exception as exc:
        raise HTTPException(502, detail="Audit evidence storage operation failed") from exc
    return {"archive_id": row.id, "checkpoint_id": row.checkpoint_id,
            "bucket": row.bucket_name, "object_key": row.object_key,
            "version_id": row.object_version_id, "retention_until": row.retention_until.isoformat(),
            "object_lock_mode": row.object_lock_mode, "status": row.archive_status}

@router.get("/admin/audit/archives", tags=["audit"])
def list_audit_archives(db: Session = Depends(get_db),
                        _admin: User = Depends(require_roles("admin"))):
    rows = db.query(AuditEvidenceArchive).order_by(AuditEvidenceArchive.archived_at.desc()).limit(200).all()
    return [{"id": r.id, "checkpoint_id": r.checkpoint_id, "bucket": r.bucket_name,
             "object_key": r.object_key, "version_id": r.object_version_id,
             "retention_until": r.retention_until.isoformat(), "object_lock_mode": r.object_lock_mode,
             "status": r.archive_status, "archived_at": r.archived_at.isoformat()} for r in rows]

@router.get("/admin/audit/archives/{archive_id}/verify", tags=["audit"])
def verify_audit_archive(archive_id: str, db: Session = Depends(get_db),
                         _admin: User = Depends(require_roles("admin"))):
    row = db.get(AuditEvidenceArchive, archive_id)
    if not row:
        raise HTTPException(404, "Audit archive not found")
    try:
        result = verify_archive(row)
    except Exception as exc:
        raise HTTPException(502, detail="Could not verify archived S3 object") from exc
    return {"archive_id": row.id, **result}
