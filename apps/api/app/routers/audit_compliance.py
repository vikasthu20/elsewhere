"""Admin access to scheduled audit compliance reports."""
import json
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from app.db import get_db
from app.models import User, AuditComplianceRun
from app.security import require_roles

router = APIRouter()

@router.get("/admin/audit/compliance-runs", tags=["audit"])
def list_compliance_runs(limit: int = 50, db: Session = Depends(get_db),
                         _admin: User = Depends(require_roles("admin"))):
    rows = db.query(AuditComplianceRun).order_by(AuditComplianceRun.created_at.desc()).limit(max(1,min(limit,200))).all()
    return [{"id": r.id, "period_key": r.period_key, "status": r.status,
             "checkpoint_id": r.checkpoint_id, "archive_job_id": r.archive_job_id,
             "created_at": r.created_at.isoformat()} for r in rows]

@router.get("/admin/audit/compliance-runs/{run_id}/report", tags=["audit"])
def get_compliance_report(run_id: str, db: Session = Depends(get_db),
                          _admin: User = Depends(require_roles("admin"))):
    row = db.get(AuditComplianceRun, run_id)
    if not row:
        raise HTTPException(404, "Compliance run not found")
    return JSONResponse(content=json.loads(row.report_json), headers={"Cache-Control":"no-store"})

@router.get("/admin/audit/retention-monitor", tags=["audit"])
def audit_retention_monitor(db: Session = Depends(get_db),
                            _admin: User = Depends(require_roles("admin"))):
    from app.services.audit_compliance import build_retention_report
    return build_retention_report(db)
