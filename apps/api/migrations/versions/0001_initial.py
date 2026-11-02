"""Initial Elsewhere schema."""
from alembic import op
from app.db import Base
from app import models  # register original and operational model metadata

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_INITIAL_TABLES = ("users", "destinations", "itineraries", "vehicles", "bookings", "reviews")

def upgrade():
    Base.metadata.create_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in _INITIAL_TABLES])

def downgrade():
    Base.metadata.drop_all(bind=op.get_bind(), tables=[Base.metadata.tables[name] for name in reversed(_INITIAL_TABLES)])
