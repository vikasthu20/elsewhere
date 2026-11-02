"""Centralized security events, alert rules and alert records."""
from alembic import op
import sqlalchemy as sa

revision = "0036_security_event_monitoring"
down_revision = "0035_security_vulnerability_register"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "security_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="low"),
        sa.Column("source_hash", sa.String(64), nullable=False, server_default=""),
        sa.Column("request_path", sa.String(300), nullable=False, server_default=""),
        sa.Column("request_method", sa.String(12), nullable=False, server_default=""),
        sa.Column("response_status", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("event_type", "severity", "source_hash", "created_at"):
        op.create_index(f"ix_security_events_{col}", "security_events", [col])
    op.create_table(
        "security_alert_rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("threshold", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("window_minutes", sa.Integer(), nullable=False, server_default="15"),
        sa.Column("severity", sa.String(20), nullable=False, server_default="high"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_security_alert_rules_event_type", "security_alert_rules", ["event_type"])
    op.create_table(
        "security_alerts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("security_alert_rules.id"), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="high"),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("event_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("window_started_at", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.Column("acknowledged_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("acknowledged_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    for col in ("rule_id", "event_type", "severity", "status", "created_at"):
        op.create_index(f"ix_security_alerts_{col}", "security_alerts", [col])

def downgrade():
    op.drop_table("security_alerts")
    op.drop_index("ix_security_alert_rules_event_type", table_name="security_alert_rules")
    op.drop_table("security_alert_rules")
    for col in ("event_type", "severity", "source_hash", "created_at"):
        op.drop_index(f"ix_security_events_{col}", table_name="security_events")
    op.drop_table("security_events")
