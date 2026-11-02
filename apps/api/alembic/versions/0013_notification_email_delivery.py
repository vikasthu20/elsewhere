"""Add opt-in email notification delivery.

Revision ID: 0013_notification_email_delivery
Revises: 0012_notification_preferences
"""
from alembic import op
import sqlalchemy as sa

revision = "0013_notification_email_delivery"
down_revision = "0012_notification_preferences"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notification_preferences", sa.Column(
        "email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()
    ))


def downgrade():
    op.drop_column("notification_preferences", "email_enabled")
