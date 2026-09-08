"""Add advertising operations and import snapshot tables."""
from alembic import op
import sqlalchemy as sa

revision = "0002_ad_operations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.create_table("ad_import_batches", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("file_name", sa.String(255), nullable=False), sa.Column("imported_at", sa.DateTime()), sa.Column("row_count", sa.Integer(), nullable=False, server_default="0"), sa.Column("status", sa.String(30), nullable=False, server_default="completed"), sa.Column("error_message", sa.Text()))
    op.create_table("ad_plans", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("plan_name", sa.String(255), nullable=False), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")), sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")), sa.Column("strategy_code", sa.String(20)), sa.Column("current_status", sa.String(40), nullable=False, server_default="unknown"), sa.Column("target_roi", sa.Float()), sa.Column("product_unit_price", sa.Float()), sa.Column("created_at", sa.DateTime()), sa.Column("updated_at", sa.DateTime()))
    op.create_index("ix_ad_plans_plan_name", "ad_plans", ["plan_name"])
    op.create_table("ad_plan_snapshots", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ad_plan_id", sa.Integer(), sa.ForeignKey("ad_plans.id", ondelete="CASCADE"), nullable=False), sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("ad_import_batches.id", ondelete="CASCADE"), nullable=False), sa.Column("snapshot_at", sa.DateTime()), sa.Column("spend", sa.Float(), nullable=False, server_default="0"), sa.Column("orders", sa.Integer(), nullable=False, server_default="0"), sa.Column("revenue", sa.Float(), nullable=False, server_default="0"), sa.Column("actual_roi", sa.Float()), sa.Column("budget", sa.Float()), sa.Column("status", sa.String(40), nullable=False, server_default="unknown"), sa.Column("reason", sa.Text()), sa.Column("recommendation", sa.Text()))
    op.create_table("ad_strategies", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False), sa.Column("strategy_code", sa.String(20), nullable=False, server_default="A"), sa.Column("base_target_roi", sa.Float(), nullable=False, server_default="2.0"), sa.Column("multiplier", sa.Float(), nullable=False, server_default="1.0"), sa.Column("empty_burn_threshold", sa.Float(), nullable=False, server_default="0"), sa.Column("low_roi_threshold", sa.Float(), nullable=False, server_default="0"), sa.Column("no_spend_hours", sa.Float(), nullable=False, server_default="24"), sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.create_table("operation_records", sa.Column("id", sa.Integer(), primary_key=True), sa.Column("ad_plan_id", sa.Integer(), sa.ForeignKey("ad_plans.id", ondelete="CASCADE"), nullable=False), sa.Column("operation_type", sa.String(40), nullable=False), sa.Column("old_target_roi", sa.Float()), sa.Column("new_target_roi", sa.Float()), sa.Column("reason", sa.Text()), sa.Column("notes", sa.Text()), sa.Column("operated_at", sa.DateTime()))

def downgrade() -> None:
    op.drop_table("operation_records"); op.drop_table("ad_strategies"); op.drop_table("ad_plan_snapshots"); op.drop_index("ix_ad_plans_plan_name", table_name="ad_plans"); op.drop_table("ad_plans"); op.drop_table("ad_import_batches")
