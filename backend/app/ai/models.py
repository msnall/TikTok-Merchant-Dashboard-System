from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import Base


DATA_SOURCE_TYPES = ("uploaded_source", "manual_entry", "synthetic_demo")
SOURCE_CHECK = "source_type IN ('uploaded_source', 'manual_entry', 'synthetic_demo')"


class RoiPolicyConfig(Base):
    __tablename__ = "roi_policy_config"

    id: Mapped[int] = mapped_column(primary_key=True)
    policy_code: Mapped[str] = mapped_column(String(32), unique=True)
    policy_name: Mapped[str] = mapped_column(String(80))
    sort_order: Mapped[int] = mapped_column(Integer, unique=True)
    description: Mapped[str] = mapped_column(Text)


class CampaignVideoMetric(Base):
    __tablename__ = "campaign_video_metrics"
    __table_args__ = (CheckConstraint(SOURCE_CHECK, name="ck_campaign_video_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    video_id: Mapped[str] = mapped_column(String(128), index=True)
    video_work_id: Mapped[int | None] = mapped_column(ForeignKey("video_works.id", ondelete="SET NULL"))
    report_date: Mapped[date] = mapped_column(Date, index=True)
    impressions: Mapped[int | None] = mapped_column(Integer)
    clicks: Mapped[int | None] = mapped_column(Integer)
    ctr: Mapped[float | None] = mapped_column(Float)
    orders: Mapped[int | None] = mapped_column(Integer)
    cvr: Mapped[float | None] = mapped_column(Float)
    spend: Mapped[float | None] = mapped_column(Float)
    revenue: Mapped[float | None] = mapped_column(Float)
    official_completion_rate: Mapped[float | None] = mapped_column(Float)
    source_field_name: Mapped[str | None] = mapped_column(String(128))
    source_document: Mapped[str | None] = mapped_column(String(255))
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CampaignMetricTimeseries(Base):
    __tablename__ = "campaign_metric_timeseries"
    __table_args__ = (CheckConstraint(SOURCE_CHECK, name="ck_campaign_timeseries_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    spend: Mapped[float] = mapped_column(Float)
    orders: Mapped[int] = mapped_column(Integer)
    revenue: Mapped[float] = mapped_column(Float)
    measurement_type: Mapped[str] = mapped_column(String(20))
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIAnalysisRun(Base):
    __tablename__ = "ai_analysis_runs"
    __table_args__ = (CheckConstraint(SOURCE_CHECK, name="ck_analysis_run_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    analysis_time: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    input_spend: Mapped[float | None] = mapped_column(Float)
    input_orders: Mapped[int | None] = mapped_column(Integer)
    input_revenue: Mapped[float | None] = mapped_column(Float)
    input_current_roi: Mapped[float | None] = mapped_column(Float)
    input_target_roi: Mapped[float | None] = mapped_column(Float)
    input_ctr: Mapped[float | None] = mapped_column(Float)
    input_cvr: Mapped[float | None] = mapped_column(Float)
    input_completion_rate: Mapped[float | None] = mapped_column(Float)
    decision: Mapped[str] = mapped_column(String(40))
    rules_used: Mapped[str] = mapped_column(Text)
    facts: Mapped[str] = mapped_column(Text)
    recommendations: Mapped[str] = mapped_column(Text)
    uncertainties: Mapped[str] = mapped_column(Text)
    source_type: Mapped[str] = mapped_column(String(30), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    snapshot = relationship("AIAnalysisSnapshot", back_populates="run", uselist=False, cascade="all, delete-orphan")
    recommendation_records = relationship("AIRecommendation", back_populates="run", cascade="all, delete-orphan")


class AIAnalysisSnapshot(Base):
    __tablename__ = "ai_analysis_snapshots"
    __table_args__ = (UniqueConstraint("run_id", name="uq_analysis_snapshot_run"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"))
    campaign_data: Mapped[str] = mapped_column(Text)
    video_data: Mapped[str] = mapped_column(Text)
    source_information: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    run = relationship("AIAnalysisRun", back_populates="snapshot")


class AIStateTransition(Base):
    __tablename__ = "ai_state_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campaign_id: Mapped[str] = mapped_column(String(64), index=True)
    from_state: Mapped[str] = mapped_column(String(32))
    to_state: Mapped[str] = mapped_column(String(32))
    trigger: Mapped[str] = mapped_column(String(160))
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DecisionAction(Base):
    __tablename__ = "decision_actions"
    __table_args__ = (CheckConstraint("action_type IN ('ACCEPT', 'REJECT', 'MODIFY')",
                                      name="ck_decision_action_type"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_run_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), index=True)
    action_type: Mapped[str] = mapped_column(String(16))
    actual_action: Mapped[str] = mapped_column(Text)
    operator_note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


CASE_SOURCE_CHECK = "case_source IN ('real_operator_case', 'synthetic_demo')"


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    __table_args__ = (CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_recommendation_case_source"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("ai_analysis_runs.id", ondelete="CASCADE"), index=True)
    strategy_id: Mapped[str | None] = mapped_column(String(16))
    recommendation_content: Mapped[str] = mapped_column(Text)
    reasoning_snapshot: Mapped[str] = mapped_column(Text)
    pattern_refs: Mapped[str] = mapped_column(Text)
    case_source: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    run = relationship("AIAnalysisRun", back_populates="recommendation_records")


class AIRecommendationFeedback(Base):
    __tablename__ = "ai_recommendation_feedback"
    __table_args__ = (
        CheckConstraint("feedback_type IN ('ACCEPT', 'REJECT', 'MODIFY')", name="ck_ai_feedback_type"),
        CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_feedback_case_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("ai_recommendations.id", ondelete="CASCADE"), index=True)
    feedback_type: Mapped[str] = mapped_column(String(16))
    operator_note: Mapped[str | None] = mapped_column(Text)
    case_source: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIExecutionRecord(Base):
    __tablename__ = "ai_execution_records"
    __table_args__ = (
        CheckConstraint("execution_status IN ('UNKNOWN', 'PENDING', 'CONFIRMED', 'FAILED')",
                        name="ck_ai_execution_status"),
        CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_execution_case_source"),
        CheckConstraint("execution_status != 'CONFIRMED' OR (execution_source IS NOT NULL "
                        "AND evidence IS NOT NULL AND length(trim(evidence)) > 0)",
                        name="ck_ai_confirmed_execution_evidence"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    recommendation_id: Mapped[int] = mapped_column(ForeignKey("ai_recommendations.id", ondelete="CASCADE"), index=True)
    execution_status: Mapped[str] = mapped_column(String(16))
    action_type: Mapped[str | None] = mapped_column(String(64))
    actual_action: Mapped[str] = mapped_column(Text)
    execution_source: Mapped[str | None] = mapped_column(String(32))
    executed_at: Mapped[datetime | None] = mapped_column(DateTime)
    evidence: Mapped[str | None] = mapped_column(Text)
    case_source: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AIOutcomeObservation(Base):
    __tablename__ = "ai_outcome_observations"
    __table_args__ = (
        CheckConstraint("causal_assessment IN ('UNKNOWN', 'SUPPORTED', 'NOT_SUPPORTED')",
                        name="ck_ai_observation_causal"),
        CheckConstraint("validation_status IN ('UNVERIFIED', 'VERIFIED')",
                        name="ck_ai_observation_validation"),
        CheckConstraint(CASE_SOURCE_CHECK, name="ck_ai_observation_case_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    execution_record_id: Mapped[int] = mapped_column(ForeignKey("ai_execution_records.id", ondelete="CASCADE"), index=True)
    observation_window: Mapped[str] = mapped_column(Text)
    data_source: Mapped[str] = mapped_column(String(32))
    before_metrics: Mapped[str] = mapped_column(Text)
    after_metrics: Mapped[str] = mapped_column(Text)
    causal_assessment: Mapped[str] = mapped_column(String(16), default="UNKNOWN", server_default="UNKNOWN")
    validation_status: Mapped[str] = mapped_column(String(16), default="UNVERIFIED", server_default="UNVERIFIED")
    case_source: Mapped[str] = mapped_column(String(32), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
