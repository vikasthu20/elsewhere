"""Add immutable audit evidence archive records."""
from alembic import op
import sqlalchemy as sa

revision = "0039_audit_evidence_archives"
down_revision = "0038_audit_evidence_checkpoints"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_evidence_archives",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("checkpoint_id", sa.String(36), sa.ForeignKey("audit_checkpoints.id"), nullable=False),
        sa.Column("storage_provider", sa.String(30), nullable=False),
        sa.Column("bucket_name", sa.String(255), nullable=False),
        sa.Column("object_key", sa.String(1024), nullable=False, unique=True),
        sa.Column("object_version_id", sa.String(255), nullable=True),
        sa.Column("object_etag", sa.String(128), nullable=True),
        sa.Column("retention_until", sa.DateTime(), nullable=False),
        sa.Column("object_lock_mode", sa.String(20), nullable=False),
        sa.Column("archive_status", sa.String(30), nullable=False),
        sa.Column("archived_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("archived_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_evidence_archives_checkpoint_id", "audit_evidence_archives", ["checkpoint_id"])
    op.create_index("ix_audit_evidence_archives_archived_at", "audit_evidence_archives", ["archived_at"])

def downgrade():
    op.drop_index("ix_audit_evidence_archives_archived_at", table_name="audit_evidence_archives")
    op.drop_index("ix_audit_evidence_archives_checkpoint_id", table_name="audit_evidence_archives")
    op.drop_table("audit_evidence_archives")
