"""Create the initial content system schema.

This migration intentionally describes the schema with Alembic operations rather
than delegating to SQLAlchemy's ``create_all``.  It is the baseline from which
future migrations can be added safely.
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "markets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("language", sa.String(length=50)),
        sa.Column("country_code", sa.String(length=5)),
        sa.Column("description", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("name", name="uq_markets_name"),
    )
    op.create_index("ix_markets_country_code", "markets", ["country_code"])

    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("category", sa.String(length=100)),
        sa.Column("selling_points", sa.Text()),
        sa.Column("target_markets", sa.Text()),
        sa.Column("tags", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_products_market_id", "products", ["market_id"])

    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=50)),
        sa.Column("created_at", sa.DateTime()),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    op.create_table(
        "assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("file_path", sa.String(length=500)),
        sa.Column("thumbnail_path", sa.String(length=500)),
        sa.Column("source_platform", sa.String(length=50)),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("asset_type", sa.String(length=50)),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("duration", sa.Float()),
        sa.Column("width", sa.Integer()),
        sa.Column("height", sa.Integer()),
        sa.Column("fps", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column("tags", sa.Text()),
        sa.Column("visual_features", sa.Text()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="active"),
        sa.Column("semantic_summary", sa.Text()),
        sa.Column("embedding_json", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_assets_market_id", "assets", ["market_id"])
    op.create_index("ix_assets_product_id", "assets", ["product_id"])
    op.create_index("ix_assets_asset_type", "assets", ["asset_type"])

    op.create_table(
        "scripts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_platform", sa.String(length=50)),
        sa.Column("source_url", sa.String(length=500)),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("script_type", sa.String(length=50)),
        sa.Column("hook", sa.Text()),
        sa.Column("body", sa.Text()),
        sa.Column("ending", sa.Text()),
        sa.Column("cta", sa.Text()),
        sa.Column("full_text", sa.Text()),
        sa.Column("duration", sa.Float()),
        sa.Column("tags", sa.Text()),
        sa.Column("notes", sa.Text()),
        sa.Column("embedding_json", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_scripts_market_id", "scripts", ["market_id"])
    op.create_index("ix_scripts_product_id", "scripts", ["product_id"])
    op.create_index("ix_scripts_script_type", "scripts", ["script_type"])

    op.create_table(
        "content_templates",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("template_type", sa.String(length=50)),
        sa.Column("structure", sa.Text()),
        sa.Column("description", sa.Text()),
        sa.Column("recommended_duration", sa.Float()),
        sa.Column("tags", sa.Text()),
        sa.Column("embedding_json", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_content_templates_market_id", "content_templates", ["market_id"])
    op.create_index("ix_content_templates_product_id", "content_templates", ["product_id"])

    op.create_table(
        "mix_projects",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id", ondelete="SET NULL")),
        sa.Column("template_id", sa.Integer(), sa.ForeignKey("content_templates.id", ondelete="SET NULL")),
        sa.Column("target_duration", sa.Float()),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_mix_projects_market_id", "mix_projects", ["market_id"])
    op.create_index("ix_mix_projects_product_id", "mix_projects", ["product_id"])

    op.create_table(
        "video_works",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("mix_project_id", sa.Integer(), sa.ForeignKey("mix_projects.id", ondelete="SET NULL")),
        sa.Column("market_id", sa.Integer(), sa.ForeignKey("markets.id", ondelete="SET NULL")),
        sa.Column("product_id", sa.Integer(), sa.ForeignKey("products.id", ondelete="SET NULL")),
        sa.Column("file_path", sa.String(length=500)),
        sa.Column("thumbnail_path", sa.String(length=500)),
        sa.Column("duration", sa.Float()),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="draft"),
        sa.Column("publish_status", sa.String(length=30), nullable=False, server_default="unpublished"),
        sa.Column("publish_date", sa.DateTime()),
        sa.Column("notes", sa.Text()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_video_works_mix_project_id", "video_works", ["mix_project_id"])

    op.create_table(
        "asset_files",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_path", sa.String(length=500), nullable=False),
        sa.Column("file_type", sa.String(length=30)),
        sa.Column("file_size", sa.Integer()),
        sa.Column("is_thumbnail", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_asset_files_asset_id", "asset_files", ["asset_id"])

    op.create_table(
        "content_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("video_work_id", sa.Integer(), sa.ForeignKey("video_works.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("change_note", sa.Text()),
        sa.Column("snapshot_json", sa.Text()),
        sa.Column("is_latest", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime()),
        sa.Column("updated_at", sa.DateTime()),
    )
    op.create_index("ix_content_versions_video_work_id", "content_versions", ["video_work_id"])

    op.create_table(
        "asset_tags",
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "script_tags",
        sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
    )

    op.create_table(
        "mix_project_assets",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("mix_project_id", sa.Integer(), sa.ForeignKey("mix_projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("asset_id", sa.Integer(), sa.ForeignKey("assets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("start_second", sa.Float()),
        sa.Column("end_second", sa.Float()),
        sa.Column("usage_type", sa.String(length=30)),
        sa.Column("notes", sa.Text()),
    )
    op.create_index("ix_mix_project_assets_mix_project_id", "mix_project_assets", ["mix_project_id"])
    op.create_index("ix_mix_project_assets_asset_id", "mix_project_assets", ["asset_id"])


def downgrade() -> None:
    op.drop_index("ix_mix_project_assets_asset_id", table_name="mix_project_assets")
    op.drop_index("ix_mix_project_assets_mix_project_id", table_name="mix_project_assets")
    op.drop_table("mix_project_assets")
    op.drop_table("script_tags")
    op.drop_table("asset_tags")
    op.drop_index("ix_content_versions_video_work_id", table_name="content_versions")
    op.drop_table("content_versions")
    op.drop_index("ix_asset_files_asset_id", table_name="asset_files")
    op.drop_table("asset_files")
    op.drop_index("ix_video_works_mix_project_id", table_name="video_works")
    op.drop_table("video_works")
    op.drop_index("ix_mix_projects_product_id", table_name="mix_projects")
    op.drop_index("ix_mix_projects_market_id", table_name="mix_projects")
    op.drop_table("mix_projects")
    op.drop_index("ix_content_templates_product_id", table_name="content_templates")
    op.drop_index("ix_content_templates_market_id", table_name="content_templates")
    op.drop_table("content_templates")
    op.drop_index("ix_scripts_script_type", table_name="scripts")
    op.drop_index("ix_scripts_product_id", table_name="scripts")
    op.drop_index("ix_scripts_market_id", table_name="scripts")
    op.drop_table("scripts")
    op.drop_index("ix_assets_asset_type", table_name="assets")
    op.drop_index("ix_assets_product_id", table_name="assets")
    op.drop_index("ix_assets_market_id", table_name="assets")
    op.drop_table("assets")
    op.drop_table("tags")
    op.drop_index("ix_products_market_id", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_markets_country_code", table_name="markets")
    op.drop_table("markets")
