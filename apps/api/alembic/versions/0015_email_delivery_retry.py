"""Store email bodies and retry counts.
Revision ID: 0015_email_delivery_retry
Revises: 0014_notification_email_logs
"""
from alembic import op
import sqlalchemy as sa
revision = "0015_email_delivery_retry"
down_revision = "0014_notification_email_logs"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("notification_email_logs", sa.Column("email_body", sa.Text(), nullable=True))
    op.add_column("notification_email_logs", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))

def downgrade():
    op.drop_column("notification_email_logs", "retry_count")
    op.drop_column("notification_email_logs", "email_body")
