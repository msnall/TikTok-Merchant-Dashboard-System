"""Add timed script segments and bind them to mix timelines."""

from alembic import op
import sqlalchemy as sa


revision = "0009_script_timeline"
down_revision = "0008_script_audio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("script_segments"):
        op.create_table(
            "script_segments",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("script_id", sa.Integer(), sa.ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False),
            sa.Column("order_index", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("role", sa.String(20), nullable=False, server_default="body"),
            sa.Column("start_second", sa.Float(), nullable=False, server_default="0"),
            sa.Column("end_second", sa.Float(), nullable=False, server_default="3"),
            sa.Column("spoken_text", sa.Text(), nullable=False),
            sa.Column("visual_direction", sa.Text()),
            sa.Column("recommended_asset_type", sa.String(50)),
            sa.Column("is_key", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("highlight_text", sa.Text()),
            sa.Column("notes", sa.Text()),
            sa.Column("created_at", sa.DateTime()),
            sa.Column("updated_at", sa.DateTime()),
        )
        op.create_index("ix_script_segments_script_id", "script_segments", ["script_id"])

    mix_columns = {column["name"] for column in sa.inspect(bind).get_columns("mix_project_assets")}
    if "script_segment_id" not in mix_columns:
        with op.batch_alter_table("mix_project_assets") as batch:
            batch.add_column(sa.Column("script_segment_id", sa.Integer()))
            batch.add_column(sa.Column("script_text_snapshot", sa.Text()))
            batch.add_column(sa.Column("source_start_second", sa.Float()))
            batch.add_column(sa.Column("source_end_second", sa.Float()))
            batch.create_foreign_key("fk_mix_project_assets_script_segment", "script_segments", ["script_segment_id"], ["id"], ondelete="SET NULL")

    rows = bind.execute(sa.text("SELECT id, hook, body, ending, cta, duration FROM scripts")).mappings().all()
    role_asset = {"hook": "usage", "body": "usage", "ending": "result", "cta": "cta"}
    for row in rows:
        if bind.execute(sa.text("SELECT COUNT(*) FROM script_segments WHERE script_id=:id"), {"id": row["id"]}).scalar():
            continue
        parts = [(role, row[role]) for role in ("hook", "body", "ending", "cta") if row[role] and str(row[role]).strip()]
        if not parts:
            continue
        duration = float(row["duration"] or 20)
        weights = [max(len(str(text).strip()), 1) for _, text in parts]
        cursor = 0.0
        for index, ((role, text), weight) in enumerate(zip(parts, weights)):
            end = duration if index == len(parts) - 1 else round(cursor + duration * weight / sum(weights), 1)
            bind.execute(sa.text("""INSERT INTO script_segments
                (script_id, order_index, role, start_second, end_second, spoken_text, recommended_asset_type, is_key)
                VALUES (:script_id, :order_index, :role, :start_second, :end_second, :spoken_text, :asset_type, :is_key)"""),
                {"script_id": row["id"], "order_index": index, "role": role, "start_second": cursor, "end_second": end,
                 "spoken_text": str(text).strip(), "asset_type": role_asset[role], "is_key": role in ("hook", "ending", "cta")})
            cursor = end


def downgrade() -> None:
    with op.batch_alter_table("mix_project_assets") as batch:
        batch.drop_constraint("fk_mix_project_assets_script_segment", type_="foreignkey")
        batch.drop_column("source_end_second")
        batch.drop_column("source_start_second")
        batch.drop_column("script_text_snapshot")
        batch.drop_column("script_segment_id")
    op.drop_index("ix_script_segments_script_id", table_name="script_segments")
    op.drop_table("script_segments")
