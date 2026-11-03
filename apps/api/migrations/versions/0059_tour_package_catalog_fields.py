"""Add fields needed by provider and public tour package pages."""
from alembic import op
import sqlalchemy as sa

revision = "0059_tour_package_catalog_fields"
down_revision = "0057_email_retry_worker_leases"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("tour_packages", sa.Column("slug", sa.String(220), nullable=True))
    op.add_column("tour_packages", sa.Column("summary", sa.String(500), nullable=False, server_default=""))
    op.add_column("tour_packages", sa.Column("currency", sa.String(3), nullable=False, server_default="INR"))
    op.add_column("tour_packages", sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.execute("UPDATE tour_packages SET slug = id WHERE slug IS NULL OR slug = ''")
    op.alter_column("tour_packages", "slug", existing_type=sa.String(220), nullable=False)
    op.create_index("ix_tour_packages_slug", "tour_packages", ["slug"], unique=True)

def downgrade():
    op.drop_index("ix_tour_packages_slug", table_name="tour_packages")
    op.drop_column("tour_packages", "is_published")
    op.drop_column("tour_packages", "currency")
    op.drop_column("tour_packages", "summary")
    op.drop_column("tour_packages", "slug")
