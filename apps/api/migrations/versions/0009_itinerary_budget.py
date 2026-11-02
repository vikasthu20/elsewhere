"""Persist itinerary budget breakdown."""
from alembic import op
import sqlalchemy as sa

revision = "0009_itinerary_budget"
down_revision = "0008_itinerary_sharing"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("budget_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("itineraries", "budget_json")
