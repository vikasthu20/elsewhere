"""Admin signed audit checkpoints and compliance evidence exports."""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, AuditCheckpoint
from app.security import require_roles
from app.services.audit_evidence import create_checkpoint, verify_checkpoint, build_evidence_report

router = APIRouter()

@router.post("/admin/audit/checkpoints", tags=["audit"])
def create_audit_checkpoint(db: Session = Depends(get_db),
                            admin: User = Depends(require_roles("admin"))):
    try:
        row, report = create_checkpoint(db, admin.id)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return {"id": row.id, "checkpoint_hash": row.checkpoint_hash,
            "signature": row.signature, "signing_key_id": row.signing_key_id,
            "created_at": row.created_at.isoformat(), "report": report}

@router.get("/admin/audit/checkpoints", tags=["audit"])
def list_audit_checkpoints(db: Session = Depends(get_db),
                           _admin: User = Depends(require_roles("admin"))):
    rows = db.query(AuditCheckpoint).order_by(AuditCheckpoint.created_at.desc()).limit(200).all()
    return [{"id": r.id, "checkpoint_hash": r.checkpoint_hash,
             "signing_key_id": r.signing_key_id, "entry_count": r.entry_count,
             "created_at": r.created_at.isoformat()} for r in rows]

@router.get("/admin/audit/checkpoints/{checkpoint_id}/verify", tags=["audit"])
def verify_audit_checkpoint(checkpoint_id: str, db: Session = Depends(get_db),
                            _admin: User = Depends(require_roles("admin"))):
    row = db.get(AuditCheckpoint, checkpoint_id)
    if not row: raise HTTPException(404, "Audit checkpoint not found")
    return {"id": row.id, "signature_valid": verify_checkpoint(row),
            "checkpoint_hash": row.checkpoint_hash, "signing_key_id": row.signing_key_id}

@router.get("/admin/audit/evidence-export", tags=["audit"])
def export_audit_evidence(db: Session = Depends(get_db),
                          _admin: User = Depends(require_roles("admin"))):
    try:
        report = build_evidence_report(db)
    except Exception as exc:
        raise HTTPException(503, detail="Audit evidence report could not be generated") from exc
    return JSONResponse(content=report, headers={
        "Cache-Control": "no-store",
        "Content-Disposition": 'attachment; filename="elsewhere-audit-evidence.json"',
    })
