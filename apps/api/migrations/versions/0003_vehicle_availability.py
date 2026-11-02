"""Add owner-managed vehicle availability blocks."""
from alembic import op
import sqlalchemy as sa

revision = "0003_vehicle_availability"
down_revision = "0002_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "vehicle_availability_blocks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("vehicle_id", sa.String(length=36), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("owner_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("reason", sa.String(length=180), nullable=False, server_default="Unavailable"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("start_date <= end_date", name="ck_vehicle_block_date_order"),
    )
    op.create_index("ix_vehicle_availability_blocks_vehicle_id", "vehicle_availability_blocks", ["vehicle_id"])
    op.create_index("ix_vehicle_availability_blocks_owner_id", "vehicle_availability_blocks", ["owner_id"])
    op.create_index("ix_vehicle_availability_blocks_start_date", "vehicle_availability_blocks", ["start_date"])
    op.create_index("ix_vehicle_availability_blocks_end_date", "vehicle_availability_blocks", ["end_date"])


def downgrade():
    op.drop_table("vehicle_availability_blocks")
