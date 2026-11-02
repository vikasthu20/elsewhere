"""Add per-provider circuit breaker health table for notification delivery."""
from alembic import op
import sqlalchemy as sa

revision = "0048_notification_provider_circuit_breakers"
down_revision = "0047_notification_channel_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "security_notification_provider_health",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider", sa.String(20), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="unknown"),
        sa.Column("consecutive_failures", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_checked_at", sa.DateTime(), nullable=True),
        sa.Column("last_success_at", sa.DateTime(), nullable=True),
        sa.Column("last_failure_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("circuit_open_until", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_notification_provider_health_provider",
                    "security_notification_provider_health", ["provider"])


def downgrade():
    op.drop_index("ix_security_notification_provider_health_provider",
                  table_name="security_notification_provider_health")
    op.drop_table("security_notification_provider_health")

