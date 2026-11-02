"""Add tamper-evident fields to audit logs."""
from alembic import op
import sqlalchemy as sa

revision = "0037_audit_log_integrity"
down_revision = "0036_security_event_monitoring"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("audit_logs", sa.Column("previous_hash", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("entry_hash", sa.String(64), nullable=True))
    op.add_column("audit_logs", sa.Column("integrity_version", sa.Integer(), nullable=False, server_default="1"))
    op.create_index("ix_audit_logs_entry_hash", "audit_logs", ["entry_hash"])

def downgrade():
    op.drop_index("ix_audit_logs_entry_hash", table_name="audit_logs")
    op.drop_column("audit_logs", "integrity_version")
    op.drop_column("audit_logs", "entry_hash")
    op.drop_column("audit_logs", "previous_hash")
