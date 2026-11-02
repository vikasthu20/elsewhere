"""Add signed audit evidence checkpoints."""
from alembic import op
import sqlalchemy as sa

revision = "0038_audit_evidence_checkpoints"
down_revision = "0037_audit_log_integrity"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "audit_checkpoints",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("checkpoint_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(128), nullable=False),
        sa.Column("signing_key_id", sa.String(80), nullable=False),
        sa.Column("entry_count", sa.Integer(), nullable=False),
        sa.Column("head_entry_hash", sa.String(64), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("report_json", sa.Text(), nullable=False),
    )
    op.create_index("ix_audit_checkpoints_checkpoint_hash", "audit_checkpoints", ["checkpoint_hash"])
    op.create_index("ix_audit_checkpoints_created_at", "audit_checkpoints", ["created_at"])

def downgrade():
    op.drop_index("ix_audit_checkpoints_created_at", table_name="audit_checkpoints")
    op.drop_index("ix_audit_checkpoints_checkpoint_hash", table_name="audit_checkpoints")
    op.drop_table("audit_checkpoints")
