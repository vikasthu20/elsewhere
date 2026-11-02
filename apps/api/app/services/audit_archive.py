"""S3 Object Lock archival for signed audit evidence checkpoints."""
from __future__ import annotations
import hashlib
import json
from datetime import datetime, timedelta, timezone
from botocore.exceptions import ClientError
from app.core.config import settings
from app.models import AuditCheckpoint, AuditEvidenceArchive
from app.services.audit_evidence import verify_checkpoint

def _s3_client():
    import boto3
    return boto3.client("s3", region_name=settings.audit_archive_s3_region)

def _validate_config():
    if not settings.audit_archive_enabled:
        raise RuntimeError("Audit evidence archival is disabled")
    if not settings.audit_archive_s3_bucket.strip():
        raise RuntimeError("AUDIT_ARCHIVE_S3_BUCKET is not configured")
    mode = settings.audit_archive_object_lock_mode.upper()
    if mode not in {"GOVERNANCE", "COMPLIANCE"}:
        raise RuntimeError("Object Lock mode must be GOVERNANCE or COMPLIANCE")
    days = settings.audit_archive_retention_days
    if days < 1 or days > 36500:
        raise RuntimeError("AUDIT_ARCHIVE_RETENTION_DAYS must be between 1 and 36500")

def archive_checkpoint(db, checkpoint: AuditCheckpoint, admin_id: str):
    _validate_config()
    if not verify_checkpoint(checkpoint):
        raise ValueError("Checkpoint signature verification failed")
    report = json.loads(checkpoint.report_json)
    envelope = {
        "schema": "elsewhere.audit-archive.v1",
        "checkpoint": {
            "id": checkpoint.id, "checkpoint_hash": checkpoint.checkpoint_hash,
            "signature": checkpoint.signature, "signing_key_id": checkpoint.signing_key_id,
            "entry_count": checkpoint.entry_count, "head_entry_hash": checkpoint.head_entry_hash,
            "created_at": checkpoint.created_at.isoformat() if checkpoint.created_at else None,
        },
        "report": report,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    body = json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    content_hash = hashlib.sha256(body).hexdigest()
    key = f"{settings.audit_archive_s3_prefix.strip('/').rstrip('/')}/{checkpoint.id}/{content_hash}.json"
    retain_until = datetime.now(timezone.utc) + timedelta(days=settings.audit_archive_retention_days)
    kwargs = {
        "Bucket": settings.audit_archive_s3_bucket, "Key": key, "Body": body,
        "ContentType": "application/json",
        "Metadata": {"checkpoint-id": checkpoint.id, "checkpoint-hash": checkpoint.checkpoint_hash,
                     "content-sha256": content_hash, "signing-key-id": checkpoint.signing_key_id},
        "ObjectLockMode": settings.audit_archive_object_lock_mode.upper(),
        "ObjectLockRetainUntilDate": retain_until,
    }
    if settings.audit_archive_kms_key_id.strip():
        kwargs["ServerSideEncryption"] = "aws:kms"
        kwargs["SSEKMSKeyId"] = settings.audit_archive_kms_key_id.strip()
    response = _s3_client().put_object(**kwargs)
    row = AuditEvidenceArchive(
        checkpoint_id=checkpoint.id, bucket_name=settings.audit_archive_s3_bucket,
        object_key=key, object_version_id=response.get("VersionId"),
        object_etag=response.get("ETag"), retention_until=retain_until.replace(tzinfo=None),
        object_lock_mode=settings.audit_archive_object_lock_mode.upper(),
        archive_status="stored", archived_by=admin_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row

def verify_archive(row: AuditEvidenceArchive) -> dict:
    client = _s3_client()
    response = client.head_object(Bucket=row.bucket_name, Key=row.object_key,
                                  **({"VersionId": row.object_version_id} if row.object_version_id else {}))
    metadata = response.get("Metadata", {})
    return {
        "exists": True,
        "checkpoint_id_matches": metadata.get("checkpoint-id") == row.checkpoint_id,
        "object_lock_mode": response.get("ObjectLockMode"),
        "retention_until": response.get("ObjectLockRetainUntilDate").isoformat()
            if response.get("ObjectLockRetainUntilDate") else None,
        "version_id": response.get("VersionId"),
        "etag": response.get("ETag"),
        "content_sha256_metadata": metadata.get("content-sha256"),
        "content_length": response.get("ContentLength"),
    }
