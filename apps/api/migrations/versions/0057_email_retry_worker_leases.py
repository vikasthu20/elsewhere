"""Track retry worker leases for recovery of stuck email deliveries.

Recovered from the unused alembic/versions tree, which reused revision
0017_email_retry_dead_letter and collided with the live email_retry_log migration.
"""
from alembic import op
import sqlalchemy as sa

revision = "0057_email_retry_worker_leases"
down_revision = "0056_email_retry_scheduler"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("notification_email_logs", sa.Column("retry_started_at", sa.DateTime(), nullable=True))
    op.create_index("ix_notification_email_logs_retry_started_at", "notification_email_logs", ["retry_started_at"])


def downgrade():
    op.drop_index("ix_notification_email_logs_retry_started_at", table_name="notification_email_logs")
    op.drop_column("notification_email_logs", "retry_started_at")
