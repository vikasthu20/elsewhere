"""Add traveller document lifecycle notices for expiry and renewal tracking."""
from alembic import op
import sqlalchemy as sa

revision = "0028_traveller_document_lifecycle"
down_revision = "0027_traveller_document_security"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "tour_package_document_lifecycle_notices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("notice_type", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("document_id", "notice_type", name="uq_tpd_lifecycle_notice"),
    )
    op.create_index(
        "ix_tour_package_document_lifecycle_notices_document_id",
        "tour_package_document_lifecycle_notices",
        ["document_id"],
    )


def downgrade():
    op.drop_index(
        "ix_tour_package_document_lifecycle_notices_document_id",
        table_name="tour_package_document_lifecycle_notices",
    )
    op.drop_table("tour_package_document_lifecycle_notices")
