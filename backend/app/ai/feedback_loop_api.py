"""Record operator feedback, execution assertions and later observations."""

import json
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from .models import (AIAnalysisRun, AIExecutionRecord, AIOutcomeObservation,
                     AIRecommendation, AIRecommendationFeedback)

router = APIRouter(prefix="/api/ai", tags=["ai feedback loop"])


class FeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    feedback_type: Literal["ACCEPT", "REJECT", "MODIFY"]
    operator_note: str | None = Field(default=None, max_length=2000)


class ExecutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    execution_status: Literal["UNKNOWN", "PENDING", "CONFIRMED", "FAILED"] = "UNKNOWN"
    action_type: str | None = Field(default=None, max_length=64)
    actual_action: str = Field(min_length=1, max_length=2000)
    execution_source: Literal["operator_input", "operator_verified", "manual_screenshot", "import"] | None = None
    executed_at: datetime | None = None
    evidence: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_execution(self):
        if self.execution_status == "CONFIRMED":
            if self.execution_source not in {"operator_verified", "manual_screenshot", "import"} or not self.evidence or not self.evidence.strip():
                raise ValueError("CONFIRMED requires a verification source and non-empty evidence")
        if self.execution_status == "FAILED" and (not self.evidence or not self.evidence.strip()):
            raise ValueError("FAILED requires evidence of the attempted execution")
        if self.execution_status != "CONFIRMED" and self.executed_at is not None:
            raise ValueError("executed_at is only allowed for confirmed execution")
        return self


class ObservationWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: float | None = Field(default=None, gt=0)
    unit: Literal["hours", "days", "weeks", "custom"] | None = None
    source: Literal["operator_input", "business_config", "platform_data", "UNKNOWN"] = "UNKNOWN"
    start: date | None = None
    end: date | None = None

    @model_validator(mode="after")
    def validate_window(self):
        if self.source == "UNKNOWN":
            if any(value is not None for value in (self.value, self.unit, self.start, self.end)):
                raise ValueError("Unknown observation window cannot contain a time range")
        elif (self.value is None or self.unit is None) and (self.start is None or self.end is None):
            raise ValueError("Observation window needs a value/unit or start/end dates")
        if (self.start is None) != (self.end is None):
            raise ValueError("Observation window dates must be provided together")
        if self.start and self.end and self.end < self.start:
            raise ValueError("Observation window end cannot precede start")
        return self


class ObservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    observation_window: ObservationWindow
    data_source: Literal["manual", "import"]
    before_metrics: dict[str, int | float | None] = Field(default_factory=dict)
    after_metrics: dict[str, int | float | None] = Field(default_factory=dict)


def _recommendation(item: AIRecommendation, db: Session) -> dict:
    feedback = db.scalars(select(AIRecommendationFeedback).where(
        AIRecommendationFeedback.recommendation_id == item.id).order_by(AIRecommendationFeedback.id.desc())).first()
    executions = db.scalars(select(AIExecutionRecord).where(
        AIExecutionRecord.recommendation_id == item.id).order_by(AIExecutionRecord.id.desc())).all()
    execution = executions[0] if executions else None

    def execution_detail(record: AIExecutionRecord) -> dict:
        observations = db.scalars(select(AIOutcomeObservation).where(
            AIOutcomeObservation.execution_record_id == record.id)
            .order_by(AIOutcomeObservation.id)).all()
        return {"id": record.id, "execution_status": record.execution_status,
                "action_type": record.action_type, "actual_action": record.actual_action,
                "execution_source": record.execution_source,
                "executed_at": record.executed_at, "evidence": record.evidence,
                "created_at": record.created_at,
                "observations": [{"id": observation.id,
                                  "observation_window": json.loads(observation.observation_window),
                                  "data_source": observation.data_source,
                                  "before_metrics": json.loads(observation.before_metrics),
                                  "after_metrics": json.loads(observation.after_metrics),
                                  "causal_assessment": observation.causal_assessment,
                                  "validation_status": observation.validation_status,
                                  "created_at": observation.created_at} for observation in observations]}

    execution_history = [execution_detail(record) for record in executions]
    return {"id": item.id, "analysis_id": item.analysis_id, "strategy_id": item.strategy_id,
            "recommendation_content": item.recommendation_content,
            "reasoning_snapshot": json.loads(item.reasoning_snapshot),
            "pattern_refs": json.loads(item.pattern_refs), "case_source": item.case_source,
            "feedback_type": feedback.feedback_type if feedback else None,
            "operator_note": feedback.operator_note if feedback else None,
            "status": {"ACCEPT": "ACCEPTED", "REJECT": "REJECTED", "MODIFY": "MODIFIED"}.get(
                feedback.feedback_type if feedback else None, "UNREVIEWED"),
            "execution_status": execution.execution_status if execution else "UNKNOWN",
            "execution": ({key: value for key, value in execution_history[0].items()
                           if key != "observations"} if execution else None),
            "observations": execution_history[0]["observations"] if execution else [],
            "execution_history": execution_history,
            "created_at": item.created_at}


@router.get("/analyses/{analysis_id}/recommendations")
def list_recommendations(analysis_id: int, db: Session = Depends(get_db)):
    if not db.get(AIAnalysisRun, analysis_id):
        raise HTTPException(404, "分析记录不存在")
    items = db.scalars(select(AIRecommendation).where(AIRecommendation.analysis_id == analysis_id)
                       .order_by(AIRecommendation.id)).all()
    return [_recommendation(item, db) for item in items]


@router.post("/recommendations/{recommendation_id}/feedback", status_code=201)
def create_feedback(recommendation_id: int, payload: FeedbackRequest, db: Session = Depends(get_db)):
    recommendation = db.get(AIRecommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(404, "建议不存在")
    item = AIRecommendationFeedback(recommendation_id=recommendation_id,
                                    feedback_type=payload.feedback_type,
                                    operator_note=payload.operator_note,
                                    case_source=recommendation.case_source)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "recommendation_id": item.recommendation_id,
            "feedback_type": item.feedback_type, "operator_note": item.operator_note,
            "case_source": item.case_source, "execution_status": "UNKNOWN",
            "created_at": item.created_at}


@router.post("/recommendations/{recommendation_id}/execution", status_code=201)
def create_execution(recommendation_id: int, payload: ExecutionRequest, db: Session = Depends(get_db)):
    recommendation = db.get(AIRecommendation, recommendation_id)
    if not recommendation:
        raise HTTPException(404, "建议不存在")
    item = AIExecutionRecord(recommendation_id=recommendation_id,
                             execution_status=payload.execution_status,
                             action_type=payload.action_type, actual_action=payload.actual_action,
                             execution_source=payload.execution_source, executed_at=payload.executed_at,
                             evidence=payload.evidence, case_source=recommendation.case_source)
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "recommendation_id": item.recommendation_id,
            "execution_status": item.execution_status, "action_type": item.action_type,
            "actual_action": item.actual_action, "execution_source": item.execution_source,
            "executed_at": item.executed_at, "evidence": item.evidence,
            "case_source": item.case_source, "created_at": item.created_at}


@router.post("/executions/{execution_id}/observation", status_code=201)
def create_observation(execution_id: int, payload: ObservationRequest, db: Session = Depends(get_db)):
    execution = db.get(AIExecutionRecord, execution_id)
    if not execution:
        raise HTTPException(404, "执行记录不存在")
    item = AIOutcomeObservation(
        execution_record_id=execution_id,
        observation_window=payload.observation_window.model_dump_json(),
        data_source=payload.data_source,
        before_metrics=json.dumps(payload.before_metrics, ensure_ascii=False),
        after_metrics=json.dumps(payload.after_metrics, ensure_ascii=False),
        causal_assessment="UNKNOWN", validation_status="UNVERIFIED",
        case_source=execution.case_source,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return {"id": item.id, "execution_record_id": item.execution_record_id,
            "observation_window": json.loads(item.observation_window),
            "data_source": item.data_source,
            "before_metrics": json.loads(item.before_metrics),
            "after_metrics": json.loads(item.after_metrics),
            "causal_assessment": item.causal_assessment,
            "validation_status": item.validation_status,
            "case_source": item.case_source, "created_at": item.created_at}
