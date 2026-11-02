"""Per-admin security notification channel preferences."""
from alembic import op
import sqlalchemy as sa

revision = "0045_security_notification_preferences"
down_revision = "0044_security_notification_job_locking"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "security_notification_preferences",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("webhook_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_notification_preferences_admin_id", "security_notification_preferences", ["admin_id"])

def downgrade():
    op.drop_index("ix_security_notification_preferences_admin_id", table_name="security_notification_preferences")
    op.drop_table("security_notification_preferences")
