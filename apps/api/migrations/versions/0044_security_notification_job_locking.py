"""Add notification delivery leases and escalation tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0044_security_notification_job_locking"
down_revision = "0043_security_notification_deliveries"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("security_notification_deliveries", sa.Column("locked_at", sa.DateTime(), nullable=True))
    op.add_column("security_notification_deliveries", sa.Column("locked_by", sa.String(120), nullable=True))
    op.add_column("security_notification_deliveries", sa.Column("escalation_status", sa.String(20), nullable=False, server_default="not_required"))
    op.add_column("security_notification_deliveries", sa.Column("escalation_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("security_notification_deliveries", sa.Column("escalation_sent_at", sa.DateTime(), nullable=True))
    op.create_index("ix_security_notification_delivery_lease", "security_notification_deliveries", ["status", "locked_at"])

def downgrade():
    op.drop_index("ix_security_notification_delivery_lease", table_name="security_notification_deliveries")
    op.drop_column("security_notification_deliveries", "escalation_sent_at")
    op.drop_column("security_notification_deliveries", "escalation_attempts")
    op.drop_column("security_notification_deliveries", "escalation_status")
    op.drop_column("security_notification_deliveries", "locked_by")
    op.drop_column("security_notification_deliveries", "locked_at")
