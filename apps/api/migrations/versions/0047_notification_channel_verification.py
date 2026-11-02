"""Add per-admin contact verification for security notification channels."""
from alembic import op
import sqlalchemy as sa

revision = "0047_notification_channel_verification"
down_revision = "0046_security_notification_routing"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "security_notification_verifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("admin_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("destination", sa.String(255), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_notification_verifications_admin_id",
                    "security_notification_verifications", ["admin_id"])
    # Mark email and phone as verified fields on preferences
    op.add_column("security_notification_preferences",
                  sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("security_notification_preferences",
                  sa.Column("phone_verified", sa.Boolean(), nullable=False, server_default=sa.false()))
    # Custom templates
    op.create_table(
        "security_notification_templates",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("channel", sa.String(10), nullable=False, unique=True),
        sa.Column("subject_template", sa.String(200), nullable=False,
                  server_default="[{severity}] Elsewhere security alert"),
        sa.Column("body_template", sa.Text(), nullable=False, server_default="{title} - {summary}"),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade():
    op.drop_table("security_notification_templates")
    op.drop_column("security_notification_preferences", "phone_verified")
    op.drop_column("security_notification_preferences", "email_verified")
    op.drop_index("ix_security_notification_verifications_admin_id",
                  table_name="security_notification_verifications")
    op.drop_table("security_notification_verifications")
