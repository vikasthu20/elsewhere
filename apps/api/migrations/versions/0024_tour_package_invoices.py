"""tour package invoices and payment receipts"""
from alembic import op
import sqlalchemy as sa

revision = "0024_tour_package_invoices"
down_revision = "0023_tour_package_payouts"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tour_package_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("invoice_number", sa.String(40), nullable=False, unique=True),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("tour_package_payments.id"), nullable=False, unique=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("tour_package_requests.id"), nullable=False),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("package_title", sa.String(200), nullable=False),
        sa.Column("destination", sa.String(160), nullable=False, server_default=""),
        sa.Column("customer_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("customer_email", sa.String(255), nullable=False, server_default=""),
        sa.Column("provider_name", sa.String(160), nullable=False, server_default=""),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("travellers", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("subtotal", sa.Numeric(12, 2), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(20), nullable=False, server_default="issued"),
        sa.Column("issued_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tour_package_invoices_invoice_number", "tour_package_invoices", ["invoice_number"])
    op.create_index("ix_tour_package_invoices_payment_id", "tour_package_invoices", ["payment_id"])
    op.create_index("ix_tour_package_invoices_request_id", "tour_package_invoices", ["request_id"])
    op.create_index("ix_tour_package_invoices_customer_id", "tour_package_invoices", ["customer_id"])
    op.create_index("ix_tour_package_invoices_provider_id", "tour_package_invoices", ["provider_id"])


def downgrade():
    op.drop_index("ix_tour_package_invoices_provider_id", table_name="tour_package_invoices")
    op.drop_index("ix_tour_package_invoices_customer_id", table_name="tour_package_invoices")
    op.drop_index("ix_tour_package_invoices_request_id", table_name="tour_package_invoices")
    op.drop_index("ix_tour_package_invoices_payment_id", table_name="tour_package_invoices")
    op.drop_index("ix_tour_package_invoices_invoice_number", table_name="tour_package_invoices")
    op.drop_table("tour_package_invoices")
