"""Add queued audit archive jobs and retry state."""
from alembic import op
import sqlalchemy as sa

revision = "0040_audit_archive_jobs"
down_revision = "0039_audit_evidence_archives"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_archive_jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("checkpoint_id", sa.String(36), sa.ForeignKey("audit_checkpoints.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("max_attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("archive_id", sa.String(36), sa.ForeignKey("audit_evidence_archives.id"), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_audit_archive_jobs_checkpoint_id", "audit_archive_jobs", ["checkpoint_id"])
    op.create_index("ix_audit_archive_jobs_status", "audit_archive_jobs", ["status"])
    op.create_index("ix_audit_archive_jobs_next_attempt_at", "audit_archive_jobs", ["next_attempt_at"])

def downgrade():
    op.drop_index("ix_audit_archive_jobs_next_attempt_at", table_name="audit_archive_jobs")
    op.drop_index("ix_audit_archive_jobs_status", table_name="audit_archive_jobs")
    op.drop_index("ix_audit_archive_jobs_checkpoint_id", table_name="audit_archive_jobs")
    op.drop_table("audit_archive_jobs")
