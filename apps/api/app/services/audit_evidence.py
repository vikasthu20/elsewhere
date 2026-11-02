"""Signed audit checkpoints and portable evidence reports."""
from __future__ import annotations
import hashlib
import hmac
import json
from datetime import datetime
from app.core.config import settings
from app.models import AuditLog, AuditCheckpoint
from app.services.audit_integrity import verify_audit_chain

def _signing_key() -> bytes:
    value = settings.audit_checkpoint_signing_key.strip()
    if not value:
        raise RuntimeError("AUDIT_CHECKPOINT_SIGNING_KEY is not configured")
    if len(value) < 32:
        raise RuntimeError("AUDIT_CHECKPOINT_SIGNING_KEY must contain at least 32 characters")
    return value.encode("utf-8")

def build_evidence_report(db):
    integrity = verify_audit_chain(db)
    count = db.query(AuditLog).filter(AuditLog.entry_hash.is_not(None)).count()
    first = db.query(AuditLog).filter(AuditLog.entry_hash.is_not(None)).order_by(
        AuditLog.created_at.asc(), AuditLog.id.asc()).first()
    last = db.query(AuditLog).filter(AuditLog.entry_hash.is_not(None)).order_by(
        AuditLog.created_at.desc(), AuditLog.id.desc()).first()
    return {
        "schema": "elsewhere.audit-evidence.v1",
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "integrity": integrity,
        "entry_count": count,
        "first_entry_hash": first.entry_hash if first else None,
        "head_entry_hash": last.entry_hash if last else None,
        "chain_start": first.created_at.isoformat() if first and first.created_at else None,
        "chain_end": last.created_at.isoformat() if last and last.created_at else None,
    }

def canonical_report(report: dict) -> bytes:
    return json.dumps(report, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")

def create_checkpoint(db, admin_id: str | None = None):
    report = build_evidence_report(db)
    digest = hashlib.sha256(canonical_report(report)).hexdigest()
    signature = hmac.new(_signing_key(), digest.encode("ascii"), hashlib.sha256).hexdigest()
    row = AuditCheckpoint(
        checkpoint_hash=digest, signature=signature,
        signing_key_id=settings.audit_checkpoint_key_id,
        entry_count=report["entry_count"], head_entry_hash=report["head_entry_hash"],
        created_by=admin_id, report_json=json.dumps(report, sort_keys=True),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, report

def verify_checkpoint(row: AuditCheckpoint) -> bool:
    try:
        report = json.loads(row.report_json)
        digest = hashlib.sha256(canonical_report(report)).hexdigest()
        expected = hmac.new(_signing_key(), digest.encode("ascii"), hashlib.sha256).hexdigest()
        return hmac.compare_digest(digest, row.checkpoint_hash) and hmac.compare_digest(expected, row.signature)
    except Exception:
        return False
