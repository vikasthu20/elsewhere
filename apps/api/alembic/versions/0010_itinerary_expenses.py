"""Persist itinerary actual expenses.

Revision ID: 0010_itinerary_expenses
Revises: 0009_itinerary_budget
"""
from alembic import op
import sqlalchemy as sa

revision = "0010_itinerary_expenses"
down_revision = "0009_itinerary_budget"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("expenses_json", sa.Text(), nullable=False, server_default="[]"))


def downgrade():
    op.drop_column("itineraries", "expenses_json")
