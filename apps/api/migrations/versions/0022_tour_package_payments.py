"""tour package payment records"""
from alembic import op
import sqlalchemy as sa
revision = "0022_tour_package_payments"
down_revision = "0021_tour_package_requests"
branch_labels = None
depends_on = None
def upgrade():
    op.create_table("tour_package_payments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("tour_package_requests.id"), nullable=False, unique=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12,2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payment_method", sa.String(24), nullable=False, server_default="manual_transfer"),
        sa.Column("payment_reference", sa.String(160), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="awaiting_payment"),
        sa.Column("verified_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_tour_package_payments_request_id", "tour_package_payments", ["request_id"])
    op.create_index("ix_tour_package_payments_customer_id", "tour_package_payments", ["customer_id"])
    op.create_index("ix_tour_package_payments_provider_id", "tour_package_payments", ["provider_id"])
    op.create_index("ix_tour_package_payments_status", "tour_package_payments", ["status"])
def downgrade():
    for col in ("status", "provider_id", "customer_id", "request_id"):
        op.drop_index(f"ix_tour_package_payments_{col}", table_name="tour_package_payments")
    op.drop_table("tour_package_payments")
