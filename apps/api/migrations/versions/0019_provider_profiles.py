"""Add owner and agency provider profiles.
Revision ID: 0019_provider_profiles
Revises: 0018_auth_session_security
"""
from alembic import op
import sqlalchemy as sa

revision = "0019_provider_profiles"
down_revision = "0018_auth_session_security"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "provider_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("business_name", sa.String(length=180), nullable=False, server_default=""),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("contact_phone", sa.String(length=30), nullable=True),
        sa.Column("website_url", sa.String(length=500), nullable=True),
        sa.Column("address", sa.String(length=300), nullable=False, server_default=""),
        sa.Column("service_areas_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("pricing_notes", sa.String(length=1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_provider_profiles_user_id", "provider_profiles", ["user_id"], unique=True)

def downgrade():
    op.drop_index("ix_provider_profiles_user_id", table_name="provider_profiles")
    op.drop_table("provider_profiles")
