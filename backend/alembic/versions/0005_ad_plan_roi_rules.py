"""Support real TikTok campaign fields and nullable snapshot metrics."""

from alembic import op
import sqlalchemy as sa


revision = "0005_ad_plan_roi_rules"
down_revision = "0004_work_task_archive"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("ad_plans", sa.Column("platform_campaign_id", sa.String(64), nullable=True))
    op.add_column("ad_plans", sa.Column("imported_product_name", sa.String(255), nullable=True))
    op.create_index("ix_ad_plans_platform_campaign_id", "ad_plans", ["platform_campaign_id"])
    with op.batch_alter_table("ad_plan_snapshots") as batch_op:
        batch_op.alter_column("spend", existing_type=sa.Float(), nullable=True, server_default=None)
        batch_op.alter_column("orders", existing_type=sa.Integer(), nullable=True, server_default=None)
        batch_op.alter_column("revenue", existing_type=sa.Float(), nullable=True, server_default=None)


def downgrade() -> None:
    op.execute("UPDATE ad_plan_snapshots SET spend = 0 WHERE spend IS NULL")
    op.execute("UPDATE ad_plan_snapshots SET orders = 0 WHERE orders IS NULL")
    op.execute("UPDATE ad_plan_snapshots SET revenue = 0 WHERE revenue IS NULL")
    with op.batch_alter_table("ad_plan_snapshots") as batch_op:
        batch_op.alter_column("revenue", existing_type=sa.Float(), nullable=False, server_default="0")
        batch_op.alter_column("orders", existing_type=sa.Integer(), nullable=False, server_default="0")
        batch_op.alter_column("spend", existing_type=sa.Float(), nullable=False, server_default="0")
    op.drop_index("ix_ad_plans_platform_campaign_id", table_name="ad_plans")
    op.drop_column("ad_plans", "imported_product_name")
    op.drop_column("ad_plans", "platform_campaign_id")
