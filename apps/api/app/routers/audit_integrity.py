"""Admin audit-log integrity verification and retention controls."""
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, AuditLog
from app.security import require_roles
from app.services.audit_integrity import verify_audit_chain

router = APIRouter()

class RetentionPreviewIn(BaseModel):
    older_than_days: int = Field(ge=30, le=3650)
    resource_type: str | None = Field(default=None, max_length=80)

@router.get("/admin/audit/integrity", tags=["audit"])
def audit_integrity(db: Session = Depends(get_db), _admin: User = Depends(require_roles("admin"))):
    return verify_audit_chain(db)

@router.get("/admin/audit/entries", tags=["audit"])
def audit_entries(limit: int = 100, db: Session = Depends(get_db),
                  _admin: User = Depends(require_roles("admin"))):
    rows = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return [{"id": r.id, "actor_id": r.actor_id, "action": r.action,
             "resource_type": r.resource_type, "resource_id": r.resource_id,
             "created_at": r.created_at.isoformat(), "entry_hash": r.entry_hash}
            for r in rows]

@router.post("/admin/audit/retention/preview", tags=["audit"])
def audit_retention_preview(payload: RetentionPreviewIn, db: Session = Depends(get_db),
                            _admin: User = Depends(require_roles("admin"))):
    cutoff = datetime.utcnow() - timedelta(days=payload.older_than_days)
    query = db.query(AuditLog).filter(AuditLog.created_at < cutoff)
    if payload.resource_type:
        query = query.filter(AuditLog.resource_type == payload.resource_type)
    return {"cutoff": cutoff.isoformat(), "eligible_count": query.count(),
            "deletion_enabled": False,
            "note": "Audit logs are retained as integrity-chain evidence; export and legal review are required before any retention action."}
