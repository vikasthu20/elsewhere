"""Add revocable public itinerary share tokens."""
from alembic import op
import sqlalchemy as sa

revision = "0008_itinerary_sharing"
down_revision = "0007_itinerary_stops"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.add_column("itineraries", sa.Column("share_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_itineraries_share_token", "itineraries", ["share_token"], unique=True)


def downgrade():
    op.drop_index("ix_itineraries_share_token", table_name="itineraries")
    op.drop_column("itineraries", "share_enabled")
    op.drop_column("itineraries", "share_token")
