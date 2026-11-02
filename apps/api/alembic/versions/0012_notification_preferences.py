"""Add per-user notification preferences.

Revision ID: 0012_notification_preferences
Revises: 0011_expense_receipts
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_notification_preferences"
down_revision = "0011_expense_receipts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_preferences",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("booking_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("payment_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("trip_budget_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("support_updates", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("marketing_updates", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True)


def downgrade():
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences")
    op.drop_table("notification_preferences")
