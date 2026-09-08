"""Add persisted daily operations tasks."""
from alembic import op
import sqlalchemy as sa


revision = "0003_work_tasks"
down_revision = "0002_ad_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "work_tasks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("task_type", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("due_at", sa.DateTime()),
        sa.Column("task_date", sa.Date(), nullable=False),
        sa.Column("source", sa.String(30), nullable=False, server_default="manual"),
        sa.Column("related_type", sa.String(40)),
        sa.Column("related_id", sa.Integer()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_work_tasks_task_type", "work_tasks", ["task_type"])
    op.create_index("ix_work_tasks_status", "work_tasks", ["status"])
    op.create_index("ix_work_tasks_priority", "work_tasks", ["priority"])
    op.create_index("ix_work_tasks_due_at", "work_tasks", ["due_at"])
    op.create_index("ix_work_tasks_task_date", "work_tasks", ["task_date"])


def downgrade() -> None:
    op.drop_index("ix_work_tasks_task_date", table_name="work_tasks")
    op.drop_index("ix_work_tasks_due_at", table_name="work_tasks")
    op.drop_index("ix_work_tasks_priority", table_name="work_tasks")
    op.drop_index("ix_work_tasks_status", table_name="work_tasks")
    op.drop_index("ix_work_tasks_task_type", table_name="work_tasks")
    op.drop_table("work_tasks")
