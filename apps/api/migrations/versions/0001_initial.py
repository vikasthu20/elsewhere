"""Initial Elsewhere schema.

Explicit CREATE TABLE statements are used so later migrations can add
columns. Do not call Base.metadata.create_all() here: current models
include fields introduced after 0001.
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(30), nullable=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False, server_default="customer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "destinations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("region", sa.String(160), nullable=False, server_default="India"),
        sa.Column("category", sa.String(80), nullable=False, server_default="destination"),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_destinations_name", "destinations", ["name"])

    op.create_table(
        "itineraries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("origin", sa.String(180), nullable=False),
        sa.Column("destination", sa.String(180), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=True),
        sa.Column("days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("travellers", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("interests", sa.Text(), nullable=False, server_default=""),
        sa.Column("estimated_budget", sa.Float(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_itineraries_user_id", "itineraries", ["user_id"])

    op.create_table(
        "vehicles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("make_model", sa.String(120), nullable=False, server_default=""),
        sa.Column("seats", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("price_per_day", sa.Float(), nullable=False),
        sa.Column("city", sa.String(120), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("available", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_vehicles_owner_id", "vehicles", ["owner_id"])
    op.create_index("ix_vehicles_category", "vehicles", ["category"])
    op.create_index("ix_vehicles_city", "vehicles", ["city"])

    op.create_table(
        "bookings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("pickup_location", sa.String(180), nullable=False),
        sa.Column("total_amount", sa.Float(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="requested"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_bookings_customer_id", "bookings", ["customer_id"])
    op.create_index("ix_bookings_vehicle_id", "bookings", ["vehicle_id"])

    op.create_table(
        "reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("booking_id", name="uq_review_booking"),
    )


def downgrade():
    op.drop_table("reviews")
    op.drop_table("bookings")
    op.drop_table("vehicles")
    op.drop_table("itineraries")
    op.drop_table("destinations")
    op.drop_table("users")
