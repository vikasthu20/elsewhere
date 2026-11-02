"""Tamper-evident hash chaining for SQLAlchemy AuditLog rows."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from app.models import AuditLog

def canonical_payload(row: AuditLog) -> str:
    created = row.created_at or datetime.utcnow()
    return json.dumps({
        "id": row.id, "actor_id": row.actor_id, "action": row.action,
        "resource_type": row.resource_type, "resource_id": row.resource_id,
        "details_json": row.details_json or "{}", "created_at": created.isoformat(),
        "previous_hash": row.previous_hash, "integrity_version": row.integrity_version or 1,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

def calculate_hash(row: AuditLog) -> str:
    return hashlib.sha256(canonical_payload(row).encode("utf-8")).hexdigest()

@event.listens_for(AuditLog, "before_insert")
def attach_integrity_hash(mapper, connection, target):
    # A single ordered writer is required for a strict chain. Concurrent writers
    # can race; use the verification endpoint and serialize writes at deployment.
    previous = connection.execute(
        select(AuditLog.entry_hash).where(AuditLog.entry_hash.is_not(None))
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(1)
    ).scalar_one_or_none()
    target.previous_hash = previous
    target.integrity_version = 1
    target.entry_hash = calculate_hash(target)

def verify_audit_chain(db: Session, limit: int | None = None) -> dict:
    query = db.query(AuditLog).filter(AuditLog.entry_hash.is_not(None)).order_by(
        AuditLog.created_at.asc(), AuditLog.id.asc())
    rows = query.limit(limit).all() if limit else query.all()
    previous = None
    checked = 0
    broken = []
    for row in rows:
        expected = calculate_hash(row)
        if row.previous_hash != previous or row.entry_hash != expected:
            broken.append({"id": row.id, "created_at": row.created_at.isoformat() if row.created_at else None})
        previous = row.entry_hash
        checked += 1
    return {"checked": checked, "valid": not broken, "broken_entries": broken[:100],
            "truncated": len(broken) > 100, "head_hash": previous}
