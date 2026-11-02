"""Add booking cancellation workflow and cancellation fee tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0014_booking_cancellations"
down_revision = "0013_webhook_subscriptions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "booking_cancellations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False, unique=True),
        sa.Column("requested_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False, server_default=""),
        sa.Column("cancellation_fee", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("refund_amount", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(24), nullable=False, server_default="requested"),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_booking_cancellations_booking_id", "booking_cancellations", ["booking_id"])
    op.create_index("ix_booking_cancellations_status", "booking_cancellations", ["status"])


def downgrade():
    op.drop_index("ix_booking_cancellations_status", table_name="booking_cancellations")
    op.drop_index("ix_booking_cancellations_booking_id", table_name="booking_cancellations")
    op.drop_table("booking_cancellations")
