"""Persist editable itinerary stops."""
from alembic import op
import sqlalchemy as sa

revision = "0007_itinerary_stops"
down_revision = "0006_editorial_content"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("stops_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("itineraries", "stops_json")
