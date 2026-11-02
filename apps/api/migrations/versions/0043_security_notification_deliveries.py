"""Durable security notification webhook delivery outbox."""
from alembic import op
import sqlalchemy as sa

revision = "0043_security_notification_deliveries"
down_revision = "0042_security_alert_deliveries"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "security_notification_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_id", sa.String(36), sa.ForeignKey("security_alerts.id"), nullable=False),
        sa.Column("channel", sa.String(30), nullable=False, server_default="webhook"),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("alert_id", "channel", name="uq_security_notification_alert_channel"),
    )
    op.create_index("ix_security_notification_deliveries_alert_id", "security_notification_deliveries", ["alert_id"])
    op.create_index("ix_security_notification_deliveries_status", "security_notification_deliveries", ["status"])
    op.create_index("ix_security_notification_deliveries_next_attempt_at", "security_notification_deliveries", ["next_attempt_at"])

def downgrade():
    op.drop_index("ix_security_notification_deliveries_next_attempt_at", table_name="security_notification_deliveries")
    op.drop_index("ix_security_notification_deliveries_status", table_name="security_notification_deliveries")
    op.drop_index("ix_security_notification_deliveries_alert_id", table_name="security_notification_deliveries")
    op.drop_table("security_notification_deliveries")
