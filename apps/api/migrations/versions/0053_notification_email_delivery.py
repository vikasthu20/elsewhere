"""Add opt-in email notification delivery.

Recovered from the unused alembic/versions tree (was 0013_notification_email_delivery).
"""
from alembic import op
import sqlalchemy as sa

revision = "0053_notification_email_delivery"
down_revision = "0052_notification_preferences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notification_preferences", sa.Column(
        "email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
    ))


def downgrade():
    op.drop_column("notification_preferences", "email_enabled")
