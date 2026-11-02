"""Add webhook subscription registry for external event delivery."""
from alembic import op
import sqlalchemy as sa

revision = "0013_webhook_subscriptions"
down_revision = "0012_push_notifications"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "webhook_subscriptions" not in inspector.get_table_names():
        op.create_table(
            "webhook_subscriptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("target_url", sa.String(500), nullable=False),
            sa.Column("secret", sa.String(128), nullable=False, server_default=""),
            sa.Column("event_types", sa.Text(), nullable=False, server_default="[]"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
        inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("webhook_subscriptions")}
    required = {"id", "owner_id", "target_url", "secret", "event_types", "active", "created_at", "updated_at"}
    if not required.issubset(columns):
        raise RuntimeError("Existing webhook_subscriptions table has an incompatible schema")
    indexes = {index["name"] for index in inspector.get_indexes("webhook_subscriptions")}
    if "ix_webhook_subscriptions_owner_id" not in indexes:
        op.create_index("ix_webhook_subscriptions_owner_id", "webhook_subscriptions", ["owner_id"])
    if "ix_webhook_subscriptions_active" not in indexes:
        op.create_index("ix_webhook_subscriptions_active", "webhook_subscriptions", ["active"])


def downgrade():
    op.drop_index("ix_webhook_subscriptions_active", table_name="webhook_subscriptions")
    op.drop_index("ix_webhook_subscriptions_owner_id", table_name="webhook_subscriptions")
    op.drop_table("webhook_subscriptions")
