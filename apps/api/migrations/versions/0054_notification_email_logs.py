"""Track notification email delivery attempts.

Recovered from the unused alembic/versions tree (was 0014_notification_email_logs).
"""
from alembic import op
import sqlalchemy as sa

revision = "0054_notification_email_logs"
down_revision = "0053_notification_email_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "notification_email_logs",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("recipient_email", sa.String(length=255), nullable=False),
        sa.Column("subject", sa.String(length=255), nullable=False),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_notification_email_logs_user_id", "notification_email_logs", ["user_id"])


def downgrade():
    op.drop_index("ix_notification_email_logs_user_id", table_name="notification_email_logs")
    op.drop_table("notification_email_logs")
