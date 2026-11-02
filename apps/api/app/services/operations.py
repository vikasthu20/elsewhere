"""Operational domain helpers for Elsewhere. Provider calls are deliberately isolated."""
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
import hashlib, hmac, json, secrets

ALLOWED_DOCUMENT_MIMES = {"application/pdf", "image/jpeg", "image/png"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}

def money(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

def make_otp() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"

def hash_otp(code: str, secret: str) -> str:
    return hmac.new(secret.encode(), code.encode(), hashlib.sha256).hexdigest()

def verify_otp(code: str, code_hash: str, secret: str) -> bool:
    return hmac.compare_digest(hash_otp(code, secret), code_hash)

def otp_expiry(minutes: int = 5) -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(minutes=minutes)

def audit(db, actor_id, action, resource_type, resource_id=None, details=None):
    from app.models import AuditLog
    db.add(AuditLog(actor_id=actor_id, action=action, resource_type=resource_type,
                    resource_id=resource_id, details_json=json.dumps(details or {}, default=str)))

def document_is_allowed(filename: str, mime_type: str, size_bytes: int) -> bool:
    from pathlib import PurePath
    return (PurePath(filename).suffix.lower() in ALLOWED_DOCUMENT_EXTENSIONS
            and mime_type.lower() in ALLOWED_DOCUMENT_MIMES
            and 0 < size_bytes <= 15 * 1024 * 1024)

def create_payment_intent(*, provider: str, booking_id: str, amount, currency: str, idempotency_key: str):
    """Provider adapter contract. Does not pretend to charge money without a configured gateway."""
    if provider in {"", "unconfigured", "none"}:
        return {"status": "provider_not_configured", "booking_id": booking_id,
                "amount": str(money(amount)), "currency": currency}
    raise NotImplementedError("Configure a payment provider adapter before creating live payment intents.")
