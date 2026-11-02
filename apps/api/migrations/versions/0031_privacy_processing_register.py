"""Privacy processing register, processors and cross-border transfer records."""
from alembic import op
import sqlalchemy as sa

revision = "0031_privacy_processing_register"
down_revision = "0030_privacy_retention_policies"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("privacy_processors",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("service_description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("data_categories", sa.String(1000), nullable=False, server_default=""),
        sa.Column("processing_purpose", sa.String(1000), nullable=False, server_default=""),
        sa.Column("country", sa.String(120), nullable=False, server_default=""),
        sa.Column("subprocessors", sa.String(1000), nullable=False, server_default=""),
        sa.Column("contract_reference", sa.String(250), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_processors_name", "privacy_processors", ["name"])
    op.create_table("privacy_processing_activities",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("activity_name", sa.String(180), nullable=False),
        sa.Column("purpose", sa.String(1000), nullable=False, server_default=""),
        sa.Column("data_subjects", sa.String(500), nullable=False, server_default=""),
        sa.Column("data_categories", sa.String(1000), nullable=False, server_default=""),
        sa.Column("lawful_basis", sa.String(250), nullable=False, server_default=""),
        sa.Column("retention_rule", sa.String(500), nullable=False, server_default=""),
        sa.Column("security_measures", sa.String(1000), nullable=False, server_default=""),
        sa.Column("processor_ids", sa.String(2000), nullable=False, server_default=""),
        sa.Column("owner_department", sa.String(160), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_processing_activities_activity_name", "privacy_processing_activities", ["activity_name"])
    op.create_table("privacy_cross_border_transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("processor_id", sa.String(36), sa.ForeignKey("privacy_processors.id"), nullable=True),
        sa.Column("origin_country", sa.String(120), nullable=False), sa.Column("destination_country", sa.String(120), nullable=False),
        sa.Column("data_categories", sa.String(1000), nullable=False, server_default=""),
        sa.Column("transfer_purpose", sa.String(1000), nullable=False, server_default=""),
        sa.Column("transfer_mechanism", sa.String(500), nullable=False, server_default=""),
        sa.Column("safeguards_note", sa.String(1500), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_cross_border_transfers_processor_id", "privacy_cross_border_transfers", ["processor_id"])


def downgrade():
    op.drop_index("ix_privacy_cross_border_transfers_processor_id", table_name="privacy_cross_border_transfers")
    op.drop_table("privacy_cross_border_transfers")
    op.drop_index("ix_privacy_processing_activities_activity_name", table_name="privacy_processing_activities")
    op.drop_table("privacy_processing_activities")
    op.drop_index("ix_privacy_processors_name", table_name="privacy_processors")
    op.drop_table("privacy_processors")
