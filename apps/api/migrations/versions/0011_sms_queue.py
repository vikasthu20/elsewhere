"""Add SMS delivery queue."""
from alembic import op
import sqlalchemy as sa

revision = "0011_sms_queue"
down_revision = "0010_email_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "sms_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient_phone", sa.String(30), nullable=False),
        sa.Column("message", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_sms_queue_status", "sms_queue", ["status"])
    op.create_index("ix_sms_queue_scheduled_at", "sms_queue", ["scheduled_at"])


def downgrade():
    op.drop_index("ix_sms_queue_scheduled_at", table_name="sms_queue")
    op.drop_index("ix_sms_queue_status", table_name="sms_queue")
    op.drop_table("sms_queue")

