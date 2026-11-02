"""Add data retention policies and automated retention run log."""
from alembic import op
import sqlalchemy as sa

revision = "0030_privacy_retention_policies"
down_revision = "0029_user_privacy_controls"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "privacy_retention_policies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_category", sa.String(50), nullable=False, unique=True),
        sa.Column("retention_days", sa.Integer(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("legal_basis_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_retention_policies_data_category", "privacy_retention_policies", ["data_category"])

    op.create_table(
        "privacy_retention_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("data_category", sa.String(50), nullable=False),
        sa.Column("run_mode", sa.String(20), nullable=False, server_default="dry_run"),
        sa.Column("candidates", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("anonymized", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("run_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("details", sa.String(1000), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_retention_runs_data_category", "privacy_retention_runs", ["data_category"])
    op.create_index("ix_privacy_retention_runs_created_at", "privacy_retention_runs", ["created_at"])


def downgrade():
    op.drop_index("ix_privacy_retention_runs_created_at", table_name="privacy_retention_runs")
    op.drop_index("ix_privacy_retention_runs_data_category", table_name="privacy_retention_runs")
    op.drop_table("privacy_retention_runs")
    op.drop_index("ix_privacy_retention_policies_data_category", table_name="privacy_retention_policies")
    op.drop_table("privacy_retention_policies")
