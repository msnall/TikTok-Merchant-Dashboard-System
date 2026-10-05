"""Add auditable state transitions and human decision actions.

Revision ID: 0011_stateful_decisions
Revises: 0010_ai_decision_foundation
"""
from alembic import op
import sqlalchemy as sa

revision = "0011_stateful_decisions"
down_revision = "0010_ai_decision_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_state_transitions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.String(64), nullable=False),
        sa.Column("from_state", sa.String(32), nullable=False),
        sa.Column("to_state", sa.String(32), nullable=False),
        sa.Column("trigger", sa.String(160), nullable=False),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_ai_state_transitions_campaign_id", "ai_state_transitions", ["campaign_id"])
    op.create_index("ix_ai_state_transitions_analysis_run_id", "ai_state_transitions", ["analysis_run_id"])
    op.create_table(
        "decision_actions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_run_id", sa.Integer(), sa.ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action_type", sa.String(16), nullable=False),
        sa.Column("actual_action", sa.Text(), nullable=False),
        sa.Column("operator_note", sa.Text()),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("action_type IN ('ACCEPT', 'REJECT', 'MODIFY')", name="ck_decision_action_type"),
    )
    op.create_index("ix_decision_actions_analysis_run_id", "decision_actions", ["analysis_run_id"])


def downgrade() -> None:
    op.drop_index("ix_decision_actions_analysis_run_id", table_name="decision_actions")
    op.drop_table("decision_actions")
    op.drop_index("ix_ai_state_transitions_analysis_run_id", table_name="ai_state_transitions")
    op.drop_index("ix_ai_state_transitions_campaign_id", table_name="ai_state_transitions")
    op.drop_table("ai_state_transitions")
