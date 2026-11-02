"""Add operational workflows: support, audit, notifications, drivers, maintenance, payments, OTP and documents."""
from alembic import op
import sqlalchemy as sa

revision = "0002_operations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("audit_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True, index=True),
        sa.Column("action", sa.String(100), nullable=False, index=True),
        sa.Column("resource_type", sa.String(80), nullable=False, index=True),
        sa.Column("resource_id", sa.String(36), nullable=True, index=True),
        sa.Column("details_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_table("support_tickets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("subject", sa.String(180), nullable=False), sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="open", index=True),
        sa.Column("priority", sa.String(16), nullable=False, server_default="normal"),
        sa.Column("assigned_to", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolution", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False))
    op.create_table("notifications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("title", sa.String(180), nullable=False), sa.Column("body", sa.Text(), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False, server_default="in_app"),
        sa.Column("read_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("drivers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("name", sa.String(120), nullable=False), sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("licence_number", sa.String(80), nullable=False, unique=True),
        sa.Column("licence_expiry", sa.Date(), nullable=True), sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("driver_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False, unique=True, index=True),
        sa.Column("driver_id", sa.String(36), sa.ForeignKey("drivers.id"), nullable=False, index=True),
        sa.Column("assigned_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("vehicle_maintenance",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("vehicle_id", sa.String(36), sa.ForeignKey("vehicles.id"), nullable=False, index=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("description", sa.Text(), nullable=False), sa.Column("service_date", sa.Date(), nullable=False),
        sa.Column("next_service_date", sa.Date(), nullable=True),
        sa.Column("cost", sa.Numeric(12, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="scheduled"))
    op.create_table("payment_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("booking_id", sa.String(36), sa.ForeignKey("bookings.id"), nullable=False, index=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("provider", sa.String(40), nullable=False, server_default="unconfigured"),
        sa.Column("provider_reference", sa.String(180), nullable=True),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="INR"),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending", index=True),
        sa.Column("idempotency_key", sa.String(120), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("provider", "provider_reference", name="uq_payment_provider_reference"),
        sa.CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"))
    op.create_table("otp_challenges",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("destination", sa.String(255), nullable=False, index=True),
        sa.Column("purpose", sa.String(40), nullable=False, index=True), sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False, index=True), sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("consumed_at", sa.DateTime(), nullable=True), sa.Column("created_at", sa.DateTime(), nullable=False))
    op.create_table("private_documents",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("document_type", sa.String(60), nullable=False), sa.Column("storage_key", sa.String(500), nullable=False, unique=True),
        sa.Column("original_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("scan_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("verification_status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False))

    with op.batch_alter_table("vehicles") as batch:
        batch.alter_column("price_per_day", existing_type=sa.Float(), type_=sa.Numeric(12, 2), existing_nullable=False)
    with op.batch_alter_table("bookings") as batch:
        batch.alter_column("total_amount", existing_type=sa.Float(), type_=sa.Numeric(12, 2), existing_nullable=False)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
        op.execute("""
            ALTER TABLE bookings ADD CONSTRAINT ex_bookings_vehicle_active_dates
            EXCLUDE USING gist (
                vehicle_id WITH =,
                daterange(start_date, end_date, '[]') WITH &&
            ) WHERE (status NOT IN ('cancelled', 'rejected', 'declined'))
        """)

def downgrade():
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TABLE bookings DROP CONSTRAINT IF EXISTS ex_bookings_vehicle_active_dates")

    for table in ("private_documents", "otp_challenges", "payment_records", "vehicle_maintenance",
                  "driver_assignments", "drivers", "notifications", "support_tickets", "audit_logs"):
        op.drop_table(table)

    with op.batch_alter_table("bookings") as batch:
        batch.alter_column("total_amount", existing_type=sa.Numeric(12, 2), type_=sa.Float(), existing_nullable=False)
    with op.batch_alter_table("vehicles") as batch:
        batch.alter_column("price_per_day", existing_type=sa.Numeric(12, 2), type_=sa.Float(), existing_nullable=False)
