"""tour package requests"""
from alembic import op
import sqlalchemy as sa
revision="0021_tour_package_requests"
down_revision="0020_tour_packages"
branch_labels=None
depends_on=None
def upgrade():
 op.create_table("tour_package_requests",sa.Column("id",sa.String(36),primary_key=True),sa.Column("package_id",sa.String(36),sa.ForeignKey("tour_packages.id"),nullable=False),sa.Column("customer_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("provider_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("start_date",sa.Date(),nullable=False),sa.Column("travellers",sa.Integer(),nullable=False,server_default="1"),sa.Column("contact_phone",sa.String(30),nullable=False,server_default=""),sa.Column("message",sa.Text(),nullable=False,server_default=""),sa.Column("status",sa.String(24),nullable=False,server_default="requested"),sa.Column("provider_note",sa.Text(),nullable=False,server_default=""),sa.Column("created_at",sa.DateTime(),nullable=False),sa.Column("updated_at",sa.DateTime(),nullable=False))
 for col in ("package_id","customer_id","provider_id","status"): op.create_index(f"ix_tour_package_requests_{col}","tour_package_requests",[col])
def downgrade():
 for col in ("status","provider_id","customer_id","package_id"): op.drop_index(f"ix_tour_package_requests_{col}",table_name="tour_package_requests")
 op.drop_table("tour_package_requests")
