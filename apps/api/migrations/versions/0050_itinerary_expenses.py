"""Persist itinerary actual expenses.

Recovered from the unused alembic/versions tree, which reused revision
0010_itinerary_expenses and never applied against the live migrations chain.
"""
from alembic import op
import sqlalchemy as sa

revision = "0050_itinerary_expenses"
down_revision = "0049_notification_routing_policies"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("expenses_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("itineraries", "expenses_json")
