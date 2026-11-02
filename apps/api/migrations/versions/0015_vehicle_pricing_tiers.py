"""Add pricing tiers and seasonal rate overrides for vehicles."""
from alembic import op
import sqlalchemy as sa

revision = "0015_vehicle_pricing_tiers"
down_revision = "0014_booking_cancellations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_pricing_tiers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("tier_name", sa.String(80), nullable=False, server_default="standard"),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("price_per_day", sa.Numeric(12, 2), nullable=False),
        sa.Column("min_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_vehicle_pricing_tiers_vehicle_id", "vehicle_pricing_tiers", ["vehicle_id"])


def downgrade():
    op.drop_index("ix_vehicle_pricing_tiers_vehicle_id", table_name="vehicle_pricing_tiers")
    op.drop_table("vehicle_pricing_tiers")
