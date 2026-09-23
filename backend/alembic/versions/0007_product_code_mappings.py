"""Add persistent Seller SKU to product name mappings."""

from alembic import op
import sqlalchemy as sa


revision = "0007_product_code_mappings"
down_revision = "0006_ad_target_roi_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Local development starts the application with create_all, so the table
    # may already exist before Alembic is run against that database.
    if sa.inspect(op.get_bind()).has_table("product_code_mappings"):
        return
    op.create_table(
        "product_code_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("sellersku", sa.String(150), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
        sa.UniqueConstraint("sellersku", name="uq_product_code_mappings_sellersku"),
    )
    op.create_index(
        "ix_product_code_mappings_sellersku",
        "product_code_mappings",
        ["sellersku"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_product_code_mappings_sellersku", table_name="product_code_mappings")
    op.drop_table("product_code_mappings")
