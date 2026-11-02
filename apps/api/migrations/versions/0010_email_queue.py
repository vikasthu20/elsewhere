"""Add outbound email queue for async notification delivery."""
from alembic import op
import sqlalchemy as sa

revision = "0010_email_queue"
down_revision = "0009_itinerary_budget"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_queue",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("body_html", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_queue_status", "email_queue", ["status"])
    op.create_index("ix_email_queue_scheduled_at", "email_queue", ["scheduled_at"])
    op.create_index("ix_email_queue_recipient", "email_queue", ["recipient"])


def downgrade():
    op.drop_index("ix_email_queue_recipient", table_name="email_queue")
    op.drop_index("ix_email_queue_scheduled_at", table_name="email_queue")
    op.drop_index("ix_email_queue_status", table_name="email_queue")
    op.drop_table("email_queue")

