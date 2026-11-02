"""Add Data Protection Impact Assessment (DPIA) / privacy risk register."""
from alembic import op
import sqlalchemy as sa

revision = "0032_privacy_risk_assessments"
down_revision = "0031_privacy_processing_register"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "privacy_risk_assessments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("processing_activity_id", sa.String(36), sa.ForeignKey("privacy_processing_activities.id"), nullable=True),
        sa.Column("assessment_type", sa.String(40), nullable=False, server_default="DPIA"),
        sa.Column("scope", sa.Text(), nullable=False, server_default=""),
        sa.Column("necessity_proportionality", sa.Text(), nullable=False, server_default=""),
        sa.Column("consultation_notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        sa.Column("owner", sa.String(160), nullable=False, server_default=""),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_risk_assessments_title", "privacy_risk_assessments", ["title"])
    op.create_index("ix_privacy_risk_assessments_status", "privacy_risk_assessments", ["status"])
    op.create_index("ix_privacy_risk_assessments_processing_activity_id",
                    "privacy_risk_assessments", ["processing_activity_id"])

    op.create_table(
        "privacy_risk_items",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("assessment_id", sa.String(36),
                  sa.ForeignKey("privacy_risk_assessments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("risk_description", sa.Text(), nullable=False, server_default=""),
        sa.Column("affected_people", sa.String(500), nullable=False, server_default=""),
        sa.Column("likelihood", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("impact", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("mitigation", sa.Text(), nullable=False, server_default=""),
        sa.Column("mitigation_owner", sa.String(160), nullable=False, server_default=""),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("mitigation_status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("residual_likelihood", sa.Integer(), nullable=True),
        sa.Column("residual_impact", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_privacy_risk_items_assessment_id", "privacy_risk_items", ["assessment_id"])
    op.create_index("ix_privacy_risk_items_mitigation_status", "privacy_risk_items", ["mitigation_status"])


def downgrade():
    op.drop_index("ix_privacy_risk_items_mitigation_status", table_name="privacy_risk_items")
    op.drop_index("ix_privacy_risk_items_assessment_id", table_name="privacy_risk_items")
    op.drop_table("privacy_risk_items")
    op.drop_index("ix_privacy_risk_assessments_processing_activity_id", table_name="privacy_risk_assessments")
    op.drop_index("ix_privacy_risk_assessments_status", table_name="privacy_risk_assessments")
    op.drop_index("ix_privacy_risk_assessments_title", table_name="privacy_risk_assessments")
    op.drop_table("privacy_risk_assessments")
