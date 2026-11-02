"""Add email retry queue with dead-letter support.
Revision ID: 0017_email_retry_dead_letter
Revises: 0016_user_activity_log
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_email_retry_dead_letter"
down_revision = "0016_user_activity_log"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "email_retry_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("email_queue_id", sa.String(36), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_retry_log_email_queue_id", "email_retry_log", ["email_queue_id"])
    # dead-letter table for permanently failed emails
    op.create_table(
        "email_dead_letter",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("original_id", sa.String(36), nullable=False, unique=True),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False, server_default=""),
        sa.Column("body_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("total_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("dead_lettered_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_email_dead_letter_recipient", "email_dead_letter", ["recipient"])


def downgrade():
    op.drop_index("ix_email_dead_letter_recipient", table_name="email_dead_letter")
    op.drop_table("email_dead_letter")
    op.drop_index("ix_email_retry_log_email_queue_id", table_name="email_retry_log")
    op.drop_table("email_retry_log")
