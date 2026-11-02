"""Add per-admin notification routing and failover policies."""
from alembic import op
import sqlalchemy as sa

revision = "0049_notification_routing_policies"
down_revision = "0048_notification_provider_circuit_breakers"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("security_notification_preferences", sa.Column("delivery_mode", sa.String(20), nullable=False, server_default="parallel"))
    op.add_column("security_notification_preferences", sa.Column("channel_priority", sa.String(60), nullable=False, server_default="email,sms,webhook"))
    op.add_column("security_notification_preferences", sa.Column("failover_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    # SQLite cannot add a foreign key or DROP CONSTRAINT with ALTER TABLE.
    # Batch mode keeps SQLite and PostgreSQL aligned with the ORM declaration.
    with op.batch_alter_table("security_notification_deliveries") as batch:
        batch.add_column(sa.Column("admin_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_security_notification_deliveries_admin_id", "users", ["admin_id"], ["id"])
        batch.create_index("ix_security_notification_deliveries_admin_id", ["admin_id"])
        batch.drop_constraint("uq_security_notification_alert_channel", type_="unique")
        batch.create_unique_constraint("uq_security_notification_alert_admin_channel",
            ["alert_id", "admin_id", "channel"])

def downgrade():
    with op.batch_alter_table("security_notification_deliveries") as batch:
        batch.drop_constraint("uq_security_notification_alert_admin_channel", type_="unique")
        batch.create_unique_constraint("uq_security_notification_alert_channel", ["alert_id", "channel"])
    op.drop_index("ix_security_notification_deliveries_admin_id", table_name="security_notification_deliveries")
    op.drop_column("security_notification_deliveries", "admin_id")
    op.drop_column("security_notification_preferences", "failover_enabled")
    op.drop_column("security_notification_preferences", "channel_priority")
    op.drop_column("security_notification_preferences", "delivery_mode")
