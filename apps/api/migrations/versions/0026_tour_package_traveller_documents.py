"""Traveller document collection and verification"""
from alembic import op
import sqlalchemy as sa

revision = "0026_tour_package_traveller_documents"
down_revision = "0025_tour_package_travel_operations"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "tour_package_traveller_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("operation_id", sa.String(36), sa.ForeignKey("tour_package_travel_operations.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("traveller_name", sa.String(160), nullable=False),
        sa.Column("document_type", sa.String(30), nullable=False),
        sa.Column("document_number", sa.String(100), nullable=False, server_default=""),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("stored_filename", sa.String(255), nullable=False, unique=True),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewer_note", sa.String(1000), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tour_package_traveller_documents_operation_id", "tour_package_traveller_documents", ["operation_id"])
    op.create_index("ix_tour_package_traveller_documents_customer_id", "tour_package_traveller_documents", ["customer_id"])
    op.create_index("ix_tour_package_traveller_documents_provider_id", "tour_package_traveller_documents", ["provider_id"])
    op.create_index("ix_tour_package_traveller_documents_verification_status", "tour_package_traveller_documents", ["verification_status"])

def downgrade():
    op.drop_table("tour_package_traveller_documents")
