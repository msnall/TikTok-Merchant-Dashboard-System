"""Read-only visibility into the recommendation feedback workflow."""

import json
import math
from collections import Counter

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from .models import (AIAnalysisRun, AIExecutionRecord, AIOutcomeObservation,
                     AIRecommendation, AIRecommendationFeedback)

router = APIRouter(prefix="/api/ai", tags=["ai feedback evaluation"])


def _valid_window(raw: str) -> bool:
    try:
        window = json.loads(raw)
        return window.get("source") not in (None, "UNKNOWN") and (
            bool(window.get("start") and window.get("end")) or
            window.get("value") is not None and bool(window.get("unit")))
    except (TypeError, ValueError, AttributeError):
        return False


def _paired_metrics(observation: AIOutcomeObservation) -> dict[str, tuple[float, float]]:
    try:
        before = json.loads(observation.before_metrics)
        after = json.loads(observation.after_metrics)
    except (TypeError, ValueError):
        return {}
    if not isinstance(before, dict) or not isinstance(after, dict):
        return {}
    return {key: (value, after[key]) for key, value in before.items()
            if key in after and isinstance(value, (int, float)) and not isinstance(value, bool)
            and isinstance(after[key], (int, float)) and not isinstance(after[key], bool)
            and math.isfinite(value) and math.isfinite(after[key])}


def evaluate_feedback(db: Session) -> dict:
    recommendations = db.scalars(select(AIRecommendation).join(
        AIAnalysisRun, AIRecommendation.analysis_id == AIAnalysisRun.id).where(
        AIRecommendation.case_source == "real_operator_case",
        AIAnalysisRun.source_type != "synthetic_demo").order_by(AIRecommendation.id)).all()
    ids = [item.id for item in recommendations]
    latest_feedback = {}
    latest_execution = {}
    observations_by_execution = {}
    if ids:
        for item in db.scalars(select(AIRecommendationFeedback).where(
                AIRecommendationFeedback.recommendation_id.in_(ids),
                AIRecommendationFeedback.case_source == "real_operator_case")
                .order_by(AIRecommendationFeedback.id.desc())):
            latest_feedback.setdefault(item.recommendation_id, item)
        for item in db.scalars(select(AIExecutionRecord).where(
                AIExecutionRecord.recommendation_id.in_(ids),
                AIExecutionRecord.case_source == "real_operator_case")
                .order_by(AIExecutionRecord.id.desc())):
            latest_execution.setdefault(item.recommendation_id, item)
        execution_ids = [item.id for item in latest_execution.values()]
        if execution_ids:
            for item in db.scalars(select(AIOutcomeObservation).where(
                    AIOutcomeObservation.execution_record_id.in_(execution_ids),
                    AIOutcomeObservation.case_source == "real_operator_case")
                    .order_by(AIOutcomeObservation.id.desc())):
                observations_by_execution.setdefault(item.execution_record_id, []).append(item)

    generated = len(ids)
    feedback_received = len(latest_feedback)
    accepted_ids = {rec_id for rec_id, item in latest_feedback.items()
                    if item.feedback_type == "ACCEPT"}
    confirmed_ids = {rec_id for rec_id in accepted_ids
                     if rec_id in latest_execution and
                     latest_execution[rec_id].execution_status == "CONFIRMED"}
    observed_ids = {rec_id for rec_id in confirmed_ids
                    if observations_by_execution.get(latest_execution[rec_id].id)}
    status_counts = Counter(item.execution_status for item in latest_execution.values())
    window_ids = set()
    metrics_ids = set()
    changes = []
    quality = Counter()

    for recommendation in recommendations:
        rec_id = recommendation.id
        execution = latest_execution.get(rec_id)
        observations = observations_by_execution.get(execution.id, []) if execution else []
        if rec_id in confirmed_ids:
            if any(_valid_window(item.observation_window) for item in observations):
                window_ids.add(rec_id)
            if any(_paired_metrics(item) for item in observations):
                metrics_ids.add(rec_id)
            for item in observations:
                paired = _paired_metrics(item)
                if "roi" in paired:
                    before, after = paired["roi"]
                    changes.append({"recommendation_id": rec_id,
                                    "strategy_id": recommendation.strategy_id,
                                    "observation_id": item.id,
                                    "roi_before": before, "roi_after": after,
                                    "observed_roi_change": round(after - before, 6),
                                    "observation_window": json.loads(item.observation_window),
                                    "causal_assessment": item.causal_assessment})
                    break
        if rec_id in confirmed_ids and any(
                _valid_window(item.observation_window) and _paired_metrics(item)
                for item in observations):
            quality["HIGH"] += 1
        elif execution is not None:
            quality["MEDIUM"] += 1
        elif rec_id in latest_feedback:
            quality["LOW"] += 1
        else:
            quality["NONE"] += 1

    return {
        "scope": "real_operator_case",
        "unit": "recommendation_id",
        "funnel": {
            "generated": {"count": generated, "denominator": None},
            "feedback_received": {"count": feedback_received, "denominator": generated},
            "accepted": {"count": len(accepted_ids), "denominator": feedback_received},
            "confirmed_execution": {"count": len(confirmed_ids), "denominator": len(accepted_ids)},
            "with_observation": {"count": len(observed_ids), "denominator": len(confirmed_ids)},
        },
        "execution_summary": {status: status_counts[status]
                              for status in ("UNKNOWN", "PENDING", "CONFIRMED", "FAILED")},
        "without_execution_record": generated - len(latest_execution),
        "observation_summary": {
            "with_window": {"count": len(window_ids), "denominator": len(confirmed_ids)},
            "with_paired_metrics": {"count": len(metrics_ids), "denominator": len(confirmed_ids)},
        },
        "data_completeness": {status: quality[status]
                              for status in ("HIGH", "MEDIUM", "LOW", "NONE")},
        "observed_changes": changes,
        "causal_assessment": "UNKNOWN",
    }


@router.get("/feedback/evaluation")
def feedback_evaluation(db: Session = Depends(get_db)):
    return evaluate_feedback(db)
