"""Add managed editorial content for guides, highlights and collections."""
from alembic import op
import sqlalchemy as sa

revision = "0006_editorial_content"
down_revision = "0005_payment_webhooks_refunds"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "editorial_contents",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("slug", sa.String(length=200), nullable=False),
        sa.Column("content_type", sa.String(length=32), nullable=False, server_default="guide"),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("body", sa.Text(), nullable=False, server_default=""),
        sa.Column("image_url", sa.String(length=500), nullable=True),
        sa.Column("destination_name", sa.String(length=160), nullable=True),
        sa.Column("is_featured", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("slug", name="uq_editorial_contents_slug"),
    )
    op.create_index("ix_editorial_contents_title", "editorial_contents", ["title"])
    op.create_index("ix_editorial_contents_slug", "editorial_contents", ["slug"])
    op.create_index("ix_editorial_contents_content_type", "editorial_contents", ["content_type"])
    op.create_index("ix_editorial_contents_is_published", "editorial_contents", ["is_published"])


def downgrade():
    op.drop_index("ix_editorial_contents_is_published", table_name="editorial_contents")
    op.drop_index("ix_editorial_contents_content_type", table_name="editorial_contents")
    op.drop_index("ix_editorial_contents_slug", table_name="editorial_contents")
    op.drop_index("ix_editorial_contents_title", table_name="editorial_contents")
    op.drop_table("editorial_contents")
