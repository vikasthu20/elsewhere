"""booking confirmations and agency travel operations"""
from alembic import op
import sqlalchemy as sa

revision = "0025_tour_package_travel_operations"
down_revision = "0024_tour_package_invoices"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tour_package_travel_operations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("tour_package_invoices.id"), nullable=False, unique=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("tour_package_requests.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="confirmed"),
        sa.Column("meeting_point", sa.String(300), nullable=False, server_default=""),
        sa.Column("pickup_time", sa.String(80), nullable=False, server_default=""),
        sa.Column("emergency_contact", sa.String(80), nullable=False, server_default=""),
        sa.Column("provider_instructions", sa.Text(), nullable=False, server_default=""),
        sa.Column("checklist_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tour_package_travel_operations_invoice_id", "tour_package_travel_operations", ["invoice_id"])
    op.create_index("ix_tour_package_travel_operations_request_id", "tour_package_travel_operations", ["request_id"])
    op.create_index("ix_tour_package_travel_operations_customer_id", "tour_package_travel_operations", ["customer_id"])
    op.create_index("ix_tour_package_travel_operations_provider_id", "tour_package_travel_operations", ["provider_id"])
    op.create_index("ix_tour_package_travel_operations_status", "tour_package_travel_operations", ["status"])


def downgrade():
    op.drop_index("ix_tour_package_travel_operations_status", table_name="tour_package_travel_operations")
    op.drop_index("ix_tour_package_travel_operations_provider_id", table_name="tour_package_travel_operations")
    op.drop_index("ix_tour_package_travel_operations_customer_id", table_name="tour_package_travel_operations")
    op.drop_index("ix_tour_package_travel_operations_request_id", table_name="tour_package_travel_operations")
    op.drop_index("ix_tour_package_travel_operations_invoice_id", table_name="tour_package_travel_operations")
    op.drop_table("tour_package_travel_operations")
