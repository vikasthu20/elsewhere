"""Conservative, opt-in retention runner. Only support-ticket content is currently supported."""
from datetime import datetime, timedelta
from app.models import SupportTicket, PrivacyRetentionPolicy, PrivacyRetentionRun

SUPPORTED_CATEGORIES = {"support_ticket_content"}

def run_privacy_retention(db, category="support_ticket_content", apply=False, run_by=None, now=None):
    if category not in SUPPORTED_CATEGORIES:
        raise ValueError("Unsupported retention category")
    policy = db.query(PrivacyRetentionPolicy).filter_by(data_category=category).first()
    if not policy or not policy.enabled or not policy.retention_days:
        raise ValueError("Retention policy is not enabled/configured")
    now = now or datetime.utcnow()
    cutoff = now - timedelta(days=policy.retention_days)
    query = db.query(SupportTicket).filter(
        SupportTicket.status.in_(["resolved", "closed"]),
        SupportTicket.updated_at <= cutoff,
    )
    candidates = query.all()
    changed = 0
    if apply:
        for ticket in candidates:
            ticket.subject = "[content anonymized under retention policy]"
            ticket.message = "[content anonymized under retention policy]"
            ticket.resolution = None
            ticket.updated_at = now
            changed += 1
    run = PrivacyRetentionRun(data_category=category, run_mode="apply" if apply else "dry_run",
        candidates=len(candidates), anonymized=changed, run_by=run_by,
        details=f"cutoff={cutoff.isoformat()}; only resolved/closed ticket text is anonymized")
    db.add(run); db.commit(); db.refresh(run)
    return {"run_id": run.id, "category": category, "mode": run.run_mode,
            "cutoff": cutoff.isoformat(), "candidates": len(candidates), "anonymized": changed}
