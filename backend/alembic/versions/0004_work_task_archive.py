"""Allow daily tasks to be hidden without regenerating them."""
from alembic import op
import sqlalchemy as sa


revision = "0004_work_task_archive"
down_revision = "0003_work_tasks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("work_tasks", sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_index("ix_work_tasks_is_archived", "work_tasks", ["is_archived"])


def downgrade() -> None:
    op.drop_index("ix_work_tasks_is_archived", table_name="work_tasks")
    op.drop_column("work_tasks", "is_archived")
