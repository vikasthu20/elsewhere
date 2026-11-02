"""tour package provider payout requests"""
from alembic import op
import sqlalchemy as sa

revision = "0023_tour_package_payouts"
down_revision = "0022_tour_package_payments"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tour_package_payouts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("payout_method", sa.String(24), nullable=False, server_default="bank_transfer"),
        sa.Column("account_holder", sa.String(160), nullable=False, server_default=""),
        sa.Column("bank_name", sa.String(120), nullable=False, server_default=""),
        sa.Column("account_last4", sa.String(4), nullable=False, server_default=""),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("provider_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("admin_note", sa.Text(), nullable=False, server_default=""),
        sa.Column("payout_reference", sa.String(160), nullable=False, server_default=""),
        sa.Column("processed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("requested_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_tour_package_payouts_provider_id", "tour_package_payouts", ["provider_id"])
    op.create_index("ix_tour_package_payouts_status", "tour_package_payouts", ["status"])


def downgrade():
    op.drop_index("ix_tour_package_payouts_status", table_name="tour_package_payouts")
    op.drop_index("ix_tour_package_payouts_provider_id", table_name="tour_package_payouts")
    op.drop_table("tour_package_payouts")
