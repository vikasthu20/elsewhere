"""Add provider payment and refund references for webhook reconciliation."""
from alembic import op
import sqlalchemy as sa

revision = "0005_payment_webhooks_refunds"
down_revision = "0004_refund_requests"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("payment_records", sa.Column("provider_payment_id", sa.String(length=180), nullable=True))
    op.add_column("payment_records", sa.Column("refund_reference", sa.String(length=180), nullable=True))
    op.add_column("payment_records", sa.Column("refund_status", sa.String(length=24), nullable=False, server_default="none"))
    op.create_index("ix_payment_records_provider_payment_id", "payment_records", ["provider_payment_id"])


def downgrade():
    op.drop_index("ix_payment_records_provider_payment_id", table_name="payment_records")
    op.drop_column("payment_records", "refund_status")
    op.drop_column("payment_records", "refund_reference")
    op.drop_column("payment_records", "provider_payment_id")
