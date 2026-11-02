"""Scheduled audit checkpoint creation and compliance/retention reports."""
from __future__ import annotations
import json
import logging
from datetime import datetime, timedelta
from sqlalchemy.exc import IntegrityError
from app.core.config import settings
from app.models import AuditComplianceRun, AuditEvidenceArchive, AuditArchiveJob, AuditCheckpoint
from app.services.audit_evidence import create_checkpoint, build_evidence_report
from app.services.audit_archive_jobs import enqueue_checkpoint

logger = logging.getLogger("elsewhere.audit_compliance")

def _period_key(now: datetime, period: str) -> str:
    if period == "hourly":
        return now.strftime("hourly:%Y-%m-%dT%H")
    if period == "weekly":
        iso = now.isocalendar()
        return f"weekly:{iso.year}-W{iso.week:02d}"
    return now.strftime("daily:%Y-%m-%d")

def build_retention_report(db, now: datetime | None = None) -> dict:
    now = now or datetime.utcnow()
    warning_days = max(1, settings.audit_compliance_retention_warning_days)
    warning_cutoff = now + timedelta(days=warning_days)
    archives = db.query(AuditEvidenceArchive).order_by(AuditEvidenceArchive.retention_until.asc()).all()
    expiring = []
    expired = []
    for row in archives:
        item = {"archive_id": row.id, "checkpoint_id": row.checkpoint_id,
                "bucket": row.bucket_name, "object_key": row.object_key,
                "retention_until": row.retention_until.isoformat(), "status": row.archive_status}
        if row.retention_until <= now:
            expired.append(item)
        elif row.retention_until <= warning_cutoff:
            expiring.append(item)
    failed_jobs = db.query(AuditArchiveJob).filter(AuditArchiveJob.status == "failed").count()
    pending_jobs = db.query(AuditArchiveJob).filter(AuditArchiveJob.status.in_(["pending","retry","processing"])).count()
    return {
        "schema": "elsewhere.audit-compliance.v1",
        "generated_at": now.isoformat() + "Z",
        "audit_integrity": build_evidence_report(db),
        "archive_retention": {
            "warning_days": warning_days, "expiring_count": len(expiring),
            "expired_count": len(expired), "expiring": expiring[:200], "expired": expired[:200],
        },
        "archive_jobs": {"pending_or_retrying": pending_jobs, "terminal_failures": failed_jobs},
    }

def run_scheduled_audit_compliance(db, now: datetime | None = None) -> dict:
    if not settings.audit_compliance_enabled:
        return {"enabled": False, "message": "Scheduled audit compliance is disabled"}
    now = now or datetime.utcnow()
    key = _period_key(now, settings.audit_compliance_period.strip().lower())
    existing = db.query(AuditComplianceRun).filter(AuditComplianceRun.period_key == key).first()
    if existing:
        return {"already_ran": True, "period_key": key, "run_id": existing.id, "status": existing.status}
    report = build_retention_report(db, now)
    checkpoint = None
    archive_job = None
    status = "report_only"
    # Checkpoint signing is configured separately; if absent, preserve the report run
    # and report the signing limitation rather than silently creating an unsigned checkpoint.
    if settings.audit_checkpoint_signing_key.strip():
        checkpoint, _ = create_checkpoint(db, None)
        archive_job = enqueue_checkpoint(db, checkpoint.id, None) if settings.audit_archive_enabled else None
        status = "checkpoint_created" if checkpoint else "report_only"
    else:
        report["checkpoint_note"] = "Signing key is not configured; report generated without checkpoint."
    run = AuditComplianceRun(period_key=key, report_json=json.dumps(report, sort_keys=True),
        checkpoint_id=checkpoint.id if checkpoint else None,
        archive_job_id=archive_job.id if archive_job else None, status=status)
    db.add(run)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        existing = db.query(AuditComplianceRun).filter(AuditComplianceRun.period_key == key).first()
        return {"already_ran": True, "period_key": key, "run_id": existing.id if existing else None}
    db.refresh(run)
    return {"already_ran": False, "period_key": key, "run_id": run.id,
            "status": run.status, "checkpoint_id": run.checkpoint_id,
            "archive_job_id": run.archive_job_id, "retention_expiring": report["archive_retention"]["expiring_count"],
            "retention_expired": report["archive_retention"]["expired_count"]}
