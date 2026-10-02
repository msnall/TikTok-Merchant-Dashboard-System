"""Add uploaded audio metadata to scripts."""

from alembic import op
import sqlalchemy as sa


revision = "0008_script_audio"
down_revision = "0007_product_code_mappings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("scripts")}
    if "audio_path" not in columns:
        op.add_column("scripts", sa.Column("audio_path", sa.String(500)))
    if "audio_file_name" not in columns:
        op.add_column("scripts", sa.Column("audio_file_name", sa.String(255)))


def downgrade() -> None:
    op.drop_column("scripts", "audio_file_name")
    op.drop_column("scripts", "audio_path")
