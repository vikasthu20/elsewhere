"""Add scheduled audit compliance run records."""
from alembic import op
import sqlalchemy as sa

revision = "0041_audit_compliance_runs"
down_revision = "0040_audit_archive_jobs"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_compliance_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("period_key", sa.String(40), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
        sa.Column("checkpoint_id", sa.String(36), sa.ForeignKey("audit_checkpoints.id"), nullable=True),
        sa.Column("archive_job_id", sa.String(36), sa.ForeignKey("audit_archive_jobs.id"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("period_key", name="uq_audit_compliance_runs_period_key"),
    )
    op.create_index("ix_audit_compliance_runs_period_key", "audit_compliance_runs", ["period_key"])
    op.create_index("ix_audit_compliance_runs_created_at", "audit_compliance_runs", ["created_at"])

def downgrade():
    op.drop_index("ix_audit_compliance_runs_created_at", table_name="audit_compliance_runs")
    op.drop_index("ix_audit_compliance_runs_period_key", table_name="audit_compliance_runs")
    op.drop_table("audit_compliance_runs")
