"""Add encryption and retention metadata to traveller documents."""
from alembic import op
import sqlalchemy as sa

revision = "0027_traveller_document_security"
down_revision = "0026_tour_package_traveller_documents"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("tour_package_traveller_documents", sa.Column("encrypted_at_rest", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("tour_package_traveller_documents", sa.Column("retention_until", sa.Date(), nullable=True))

def downgrade():
    op.drop_column("tour_package_traveller_documents", "retention_until")
    op.drop_column("tour_package_traveller_documents", "encrypted_at_rest")
