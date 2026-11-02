"""Security incident and personal data breach evidence register."""
from alembic import op
import sqlalchemy as sa

revision = "0033_privacy_security_incidents"
down_revision = "0032_privacy_risk_assessments"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("privacy_security_incidents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("reference", sa.String(32), nullable=False, unique=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("discovered_at", sa.DateTime(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(), nullable=True),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(30), nullable=False, server_default="reported"),
        sa.Column("personal_data_involved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("data_categories", sa.Text(), nullable=False, server_default=""),
        sa.Column("affected_people_estimate", sa.Integer(), nullable=True),
        sa.Column("jurisdictions", sa.Text(), nullable=False, server_default=""),
        sa.Column("containment_actions", sa.Text(), nullable=False, server_default=""),
        sa.Column("notification_assessment", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("notification_due_at", sa.DateTime(), nullable=True),
        sa.Column("notification_decision", sa.Text(), nullable=False, server_default=""),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_security_incidents_reference", "privacy_security_incidents", ["reference"], unique=True)
    op.create_index("ix_privacy_security_incidents_severity", "privacy_security_incidents", ["severity"])
    op.create_index("ix_privacy_security_incidents_status", "privacy_security_incidents", ["status"])
    op.create_table("privacy_incident_evidence",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("privacy_security_incidents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("evidence_type", sa.String(60), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reference_uri", sa.String(500), nullable=True),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("recorded_at", sa.DateTime(), nullable=False))
    op.create_index("ix_privacy_incident_evidence_incident_id", "privacy_incident_evidence", ["incident_id"])

def downgrade():
    op.drop_index("ix_privacy_incident_evidence_incident_id", table_name="privacy_incident_evidence")
    op.drop_table("privacy_incident_evidence")
    op.drop_index("ix_privacy_security_incidents_status", table_name="privacy_security_incidents")
    op.drop_index("ix_privacy_security_incidents_severity", table_name="privacy_security_incidents")
    op.drop_index("ix_privacy_security_incidents_reference", table_name="privacy_security_incidents")
    op.drop_table("privacy_security_incidents")
