"""Persist per-admin alert delivery acknowledgements."""
from alembic import op
import sqlalchemy as sa

revision = "0042_security_alert_deliveries"
down_revision = "0041_audit_compliance_runs"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "security_alert_deliveries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("alert_id", sa.String(36), sa.ForeignKey("security_alerts.id"), nullable=False),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("delivered_at", sa.DateTime(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint("alert_id", "admin_id", name="uq_security_alert_delivery_admin"),
    )
    op.create_index("ix_security_alert_deliveries_alert_id", "security_alert_deliveries", ["alert_id"])
    op.create_index("ix_security_alert_deliveries_admin_id", "security_alert_deliveries", ["admin_id"])

def downgrade():
    op.drop_index("ix_security_alert_deliveries_admin_id", table_name="security_alert_deliveries")
    op.drop_index("ix_security_alert_deliveries_alert_id", table_name="security_alert_deliveries")
    op.drop_table("security_alert_deliveries")
