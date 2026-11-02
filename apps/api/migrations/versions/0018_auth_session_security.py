"""Add email verification and session versioning.
Revision ID: 0018_auth_session_security
Revises: 0017_email_retry_dead_letter
"""
from alembic import op
import sqlalchemy as sa

revision = "0018_auth_session_security"
down_revision = "0017_email_retry_dead_letter"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("auth_token_version", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("users", "email_verified")
    op.drop_column("users", "auth_token_version")
