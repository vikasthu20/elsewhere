"""Add due time for automatic email retries.

Recovered from the unused alembic/versions tree (was 0016_email_retry_scheduler).
"""
from alembic import op
import sqlalchemy as sa

revision = "0056_email_retry_scheduler"
down_revision = "0055_email_delivery_retry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notification_email_logs", sa.Column("next_retry_at", sa.DateTime(), nullable=True))
    op.create_index("ix_notification_email_logs_next_retry_at", "notification_email_logs", ["next_retry_at"])


def downgrade():
    op.drop_index("ix_notification_email_logs_next_retry_at", table_name="notification_email_logs")
    op.drop_column("notification_email_logs", "next_retry_at")
