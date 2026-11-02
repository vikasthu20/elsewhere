"""Add user consent preferences and privacy request workflow."""
from alembic import op
import sqlalchemy as sa

revision = "0029_user_privacy_controls"
down_revision = "0028_traveller_document_lifecycle"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "user_privacy_consents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("essential_acknowledged", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("analytics_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("marketing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_privacy_consents_user_id", "user_privacy_consents", ["user_id"])
    op.create_table(
        "user_privacy_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("request_type", sa.String(length=30), nullable=False),
        sa.Column("details", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="submitted"),
        sa.Column("admin_note", sa.String(length=2000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_privacy_requests_user_id", "user_privacy_requests", ["user_id"])
    op.create_index("ix_user_privacy_requests_request_type", "user_privacy_requests", ["request_type"])
    op.create_index("ix_user_privacy_requests_status", "user_privacy_requests", ["status"])

def downgrade():
    op.drop_index("ix_user_privacy_requests_status", table_name="user_privacy_requests")
    op.drop_index("ix_user_privacy_requests_request_type", table_name="user_privacy_requests")
    op.drop_index("ix_user_privacy_requests_user_id", table_name="user_privacy_requests")
    op.drop_table("user_privacy_requests")
    op.drop_index("ix_user_privacy_consents_user_id", table_name="user_privacy_consents")
    op.drop_table("user_privacy_consents")
