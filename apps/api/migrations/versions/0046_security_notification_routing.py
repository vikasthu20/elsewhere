"""Add per-admin contact routing and severity preferences."""
from alembic import op
import sqlalchemy as sa

revision = "0046_security_notification_routing"
down_revision = "0045_security_notification_preferences"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("security_notification_preferences", sa.Column("email_address", sa.String(255), nullable=True))
    op.add_column("security_notification_preferences", sa.Column("phone_number", sa.String(30), nullable=True))
    for name, default in (("severity_low", False), ("severity_medium", True),
                          ("severity_high", True), ("severity_critical", True)):
        op.add_column("security_notification_preferences",
                      sa.Column(name, sa.Boolean(), nullable=False, server_default=sa.true() if default else sa.false()))
    op.add_column("security_notification_deliveries", sa.Column("recipient_email", sa.String(255), nullable=True))
    op.add_column("security_notification_deliveries", sa.Column("recipient_phone", sa.String(30), nullable=True))

def downgrade():
    op.drop_column("security_notification_deliveries", "recipient_phone")
    op.drop_column("security_notification_deliveries", "recipient_email")
    for name in ("severity_critical", "severity_high", "severity_medium", "severity_low"):
        op.drop_column("security_notification_preferences", name)
    op.drop_column("security_notification_preferences", "phone_number")
    op.drop_column("security_notification_preferences", "email_address")
