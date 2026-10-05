"""Separate recommendation, feedback, execution and observation records.

Revision ID: 0012_feedback_loop
Revises: 0011_stateful_decisions
"""
from alembic import op
import sqlalchemy as sa

revision = "0012_feedback_loop"
down_revision = "0011_stateful_decisions"
branch_labels = None
depends_on = None

CASE_SOURCE_CHECK = "case_source IN ('real_operator_case', 'synthetic_demo')"


def upgrade() -> None:
    op.create_table(
        "ai_recommendations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("analysis_id", sa.Integer(), sa.ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("strategy_id", sa.String(16)),
        sa.Column("recommendation_content", sa.Text(), nullable=False),
        sa.Column("reasoning_snapshot", sa.Text(), nullable=False),
        sa.Column("pattern_refs", sa.Text(), nullable=False),
        sa.Column("case_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_recommendation_case_source"),
    )
    op.create_index("ix_ai_recommendations_analysis_id", "ai_recommendations", ["analysis_id"])
    op.create_index("ix_ai_recommendations_case_source", "ai_recommendations", ["case_source"])
    op.create_table(
        "ai_recommendation_feedback",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("ai_recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("feedback_type", sa.String(16), nullable=False),
        sa.Column("operator_note", sa.Text()),
        sa.Column("case_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("feedback_type IN ('ACCEPT', 'REJECT', 'MODIFY')", name="ck_ai_feedback_type"),
        sa.CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_feedback_case_source"),
    )
    op.create_index("ix_ai_recommendation_feedback_recommendation_id", "ai_recommendation_feedback", ["recommendation_id"])
    op.create_index("ix_ai_recommendation_feedback_case_source", "ai_recommendation_feedback", ["case_source"])
    op.create_table(
        "ai_execution_records",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("recommendation_id", sa.Integer(), sa.ForeignKey("ai_recommendations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_status", sa.String(16), nullable=False),
        sa.Column("action_type", sa.String(64)),
        sa.Column("actual_action", sa.Text(), nullable=False),
        sa.Column("execution_source", sa.String(32)),
        sa.Column("executed_at", sa.DateTime()),
        sa.Column("evidence", sa.Text()),
        sa.Column("case_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("execution_status IN ('UNKNOWN', 'PENDING', 'CONFIRMED', 'FAILED')", name="ck_ai_execution_status"),
        sa.CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_execution_case_source"),
        sa.CheckConstraint("execution_status != 'CONFIRMED' OR (execution_source IS NOT NULL AND evidence IS NOT NULL AND length(trim(evidence)) > 0)", name="ck_ai_confirmed_execution_evidence"),
    )
    op.create_index("ix_ai_execution_records_recommendation_id", "ai_execution_records", ["recommendation_id"])
    op.create_index("ix_ai_execution_records_case_source", "ai_execution_records", ["case_source"])
    op.create_table(
        "ai_outcome_observations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("execution_record_id", sa.Integer(), sa.ForeignKey("ai_execution_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("observation_window", sa.Text(), nullable=False),
        sa.Column("data_source", sa.String(32), nullable=False),
        sa.Column("before_metrics", sa.Text(), nullable=False),
        sa.Column("after_metrics", sa.Text(), nullable=False),
        sa.Column("causal_assessment", sa.String(16), nullable=False, server_default="UNKNOWN"),
        sa.Column("validation_status", sa.String(16), nullable=False, server_default="UNVERIFIED"),
        sa.Column("case_source", sa.String(32), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("causal_assessment IN ('UNKNOWN', 'SUPPORTED', 'NOT_SUPPORTED')", name="ck_ai_observation_causal"),
        sa.CheckConstraint("validation_status IN ('UNVERIFIED', 'VERIFIED')", name="ck_ai_observation_validation"),
        sa.CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_observation_case_source"),
    )
    op.create_index("ix_ai_outcome_observations_execution_record_id", "ai_outcome_observations", ["execution_record_id"])
    op.create_index("ix_ai_outcome_observations_case_source", "ai_outcome_observations", ["case_source"])


def downgrade() -> None:
    op.drop_index("ix_ai_outcome_observations_case_source", table_name="ai_outcome_observations")
    op.drop_index("ix_ai_outcome_observations_execution_record_id", table_name="ai_outcome_observations")
    op.drop_table("ai_outcome_observations")
    op.drop_index("ix_ai_execution_records_case_source", table_name="ai_execution_records")
    op.drop_index("ix_ai_execution_records_recommendation_id", table_name="ai_execution_records")
    op.drop_table("ai_execution_records")
    op.drop_index("ix_ai_recommendation_feedback_case_source", table_name="ai_recommendation_feedback")
    op.drop_index("ix_ai_recommendation_feedback_recommendation_id", table_name="ai_recommendation_feedback")
    op.drop_table("ai_recommendation_feedback")
    op.drop_index("ix_ai_recommendations_case_source", table_name="ai_recommendations")
    op.drop_index("ix_ai_recommendations_analysis_id", table_name="ai_recommendations")
    op.drop_table("ai_recommendations")
