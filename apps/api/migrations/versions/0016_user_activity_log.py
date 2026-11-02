"""Add user activity and login audit trail."""
from alembic import op
import sqlalchemy as sa

revision = "0016_user_activity_log"
down_revision = "0015_vehicle_pricing_tiers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("activity_type", sa.String(60), nullable=False),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_activity_log_user_id", "user_activity_log", ["user_id"])
    op.create_index("ix_user_activity_log_activity_type", "user_activity_log", ["activity_type"])
    op.create_index("ix_user_activity_log_created_at", "user_activity_log", ["created_at"])


def downgrade():
    op.drop_index("ix_user_activity_log_created_at", table_name="user_activity_log")
    op.drop_index("ix_user_activity_log_activity_type", table_name="user_activity_log")
    op.drop_index("ix_user_activity_log_user_id", table_name="user_activity_log")
    op.drop_table("user_activity_log")
