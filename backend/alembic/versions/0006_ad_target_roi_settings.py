"""Add reusable target ROI settings by product and A/B variant."""

from alembic import op
import sqlalchemy as sa


revision = "0006_ad_target_roi_settings"
down_revision = "0005_ad_plan_roi_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # The application still calls create_all during startup. A reload can create
    # this exact table before Alembic runs against an existing development DB.
    if sa.inspect(op.get_bind()).has_table("ad_target_roi_settings"):
        return
    op.create_table(
        "ad_target_roi_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("product_name", sa.String(255), nullable=False),
        sa.Column("product_key", sa.String(255), nullable=False),
        sa.Column("strategy_code", sa.String(1), nullable=False),
        sa.Column("target_roi", sa.Float(), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("product_key", "strategy_code", name="uq_ad_target_roi_product_variant"),
    )
    op.create_index("ix_ad_target_roi_settings_product_key", "ad_target_roi_settings", ["product_key"])


def downgrade() -> None:
    op.drop_index("ix_ad_target_roi_settings_product_key", table_name="ad_target_roi_settings")
    op.drop_table("ad_target_roi_settings")
