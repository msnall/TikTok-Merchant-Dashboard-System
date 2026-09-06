"""initial content system schema"""
revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    from app.db import Base
    from app import models
    from alembic import op
    Base.metadata.create_all(op.get_bind())

def downgrade():
    from app.db import Base
    from alembic import op
    Base.metadata.drop_all(op.get_bind())

