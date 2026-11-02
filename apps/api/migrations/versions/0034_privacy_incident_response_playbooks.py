"""Incident response playbooks and post-incident reviews."""
from alembic import op
import sqlalchemy as sa

revision = "0034_privacy_incident_response"
down_revision = "0033_privacy_security_incidents"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "privacy_incident_playbooks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False, unique=True),
        sa.Column("incident_type", sa.String(80), nullable=False, server_default="general"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("response_steps", sa.Text(), nullable=False, server_default=""),
        sa.Column("escalation_roles", sa.Text(), nullable=False, server_default=""),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_incident_playbooks_name", "privacy_incident_playbooks", ["name"])
    op.create_table(
        "privacy_incident_reviews",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("privacy_security_incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False, server_default=""),
        sa.Column("impact_summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("response_effectiveness", sa.Text(), nullable=False, server_default=""),
        sa.Column("lessons_learned", sa.Text(), nullable=False, server_default=""),
        sa.Column("corrective_actions", sa.Text(), nullable=False, server_default=""),
        sa.Column("owner", sa.String(160), nullable=False, server_default=""),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("reviewed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_incident_reviews_incident_id", "privacy_incident_reviews", ["incident_id"])
    op.create_index("ix_privacy_incident_reviews_status", "privacy_incident_reviews", ["status"])


def downgrade():
    op.drop_index("ix_privacy_incident_reviews_status", table_name="privacy_incident_reviews")
    op.drop_index("ix_privacy_incident_reviews_incident_id", table_name="privacy_incident_reviews")
    op.drop_table("privacy_incident_reviews")
    op.drop_index("ix_privacy_incident_playbooks_name", table_name="privacy_incident_playbooks")
    op.drop_table("privacy_incident_playbooks")
