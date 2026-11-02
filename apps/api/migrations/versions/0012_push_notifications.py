"""Add push notification tokens and delivery queue."""
from alembic import op
import sqlalchemy as sa

revision = "0012_push_notifications"
down_revision = "0011_sms_queue"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "push_tokens",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("platform", sa.String(20), nullable=False, server_default="fcm"),
        sa.Column("token", sa.String(500), nullable=False, unique=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_push_tokens_user_id", "push_tokens", ["user_id"])


def downgrade():
    op.drop_index("ix_push_tokens_user_id", table_name="push_tokens")
    op.drop_table("push_tokens")
