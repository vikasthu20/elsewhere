"""Add receipt metadata to itinerary expenses.

Recovered from the unused alembic/versions tree (was 0011_expense_receipts).
"""
from alembic import op
import sqlalchemy as sa

revision = "0051_expense_receipts"
down_revision = "0050_itinerary_expenses"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("itineraries", sa.Column("receipts_json", sa.Text(), nullable=False, server_default="{}"))


def downgrade():
    op.drop_column("itineraries", "receipts_json")
