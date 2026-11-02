"""Create tour packages catalogue managed by agency/owner providers."""
from alembic import op
import sqlalchemy as sa

revision = "0020_tour_packages"
down_revision = "0019_provider_profiles"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tour_packages",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("provider_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("destination", sa.String(180), nullable=False, server_default=""),
        sa.Column("duration_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("price_per_person", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("max_travellers", sa.Integer(), nullable=False, server_default="10"),
        sa.Column("inclusions", sa.Text(), nullable=False, server_default=""),
        sa.Column("exclusions", sa.Text(), nullable=False, server_default=""),
        sa.Column("itinerary_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="draft"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_tour_packages_provider_id", "tour_packages", ["provider_id"])
    op.create_index("ix_tour_packages_status", "tour_packages", ["status"])
    op.create_index("ix_tour_packages_destination", "tour_packages", ["destination"])


def downgrade():
    op.drop_index("ix_tour_packages_destination", table_name="tour_packages")
    op.drop_index("ix_tour_packages_status", table_name="tour_packages")
    op.drop_index("ix_tour_packages_provider_id", table_name="tour_packages")
    op.drop_table("tour_packages")
