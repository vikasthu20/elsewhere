"""Create traveller refund requests."""
from alembic import op
import sqlalchemy as sa

revision = "0004_refund_requests"
down_revision = "0003_vehicle_availability"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "refund_requests",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("booking_id", sa.String(length=36), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("customer_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="pending"),
        sa.Column("decision_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_refund_requests_booking_id", "refund_requests", ["booking_id"])
    op.create_index("ix_refund_requests_customer_id", "refund_requests", ["customer_id"])
    op.create_index("ix_refund_requests_status", "refund_requests", ["status"])


def downgrade():
    op.drop_index("ix_refund_requests_status", table_name="refund_requests")
    op.drop_index("ix_refund_requests_customer_id", table_name="refund_requests")
    op.drop_index("ix_refund_requests_booking_id", table_name="refund_requests")
    op.drop_table("refund_requests")
