"""Append-only analysis records with the exact inputs seen by each run."""

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AIAnalysisRun, AIAnalysisSnapshot, AIRecommendation
from .models import AIStateTransition


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


def save_analysis(db: Session, campaign: dict, video: dict | None,
                  source_information: dict, result: dict, *, raw_input_text: str | None = None,
                  historical_delta: dict | None = None,
                  state_transition: tuple[str, str, str] | None = None,
                  recommendation_snapshots: list[dict] | None = None) -> AIAnalysisRun:
    source_type = campaign.get("source_type")
    if source_type not in {"uploaded_source", "manual_entry", "synthetic_demo"}:
        raise ValueError("必须提供有效 source_type")
    if result.get("source_type") != source_type or result.get("campaign_id") != campaign.get("campaign_id"):
        raise ValueError("分析结果与输入来源或计划 ID 不一致")
    run = AIAnalysisRun(
        campaign_id=str(campaign.get("campaign_id") or ""),
        analysis_time=datetime.utcnow(),
        input_spend=campaign.get("spend"), input_orders=campaign.get("orders"),
        input_revenue=campaign.get("revenue"), input_current_roi=campaign.get("current_roi"),
        input_target_roi=result.get("target_roi"),
        input_ctr=video.get("ctr") if video else None,
        input_cvr=video.get("cvr") if video else None,
        input_completion_rate=video.get("official_completion_rate") if video else None,
        decision=result["decision"], rules_used=_json(result["rules_used"]),
        facts=_json(result["facts"]), recommendations=_json(result["recommendations"]),
        uncertainties=_json(result["uncertainties"]), source_type=source_type,
    )
    run.snapshot = AIAnalysisSnapshot(
        campaign_data=_json(campaign), video_data=_json(video),
        source_information=_json({**source_information, "raw_input_text": raw_input_text,
                                  "retrieved_knowledge": result.get("knowledge_refs", []),
                                  "historical_delta": historical_delta or {},
                                  "next_observation": result.get("next_observation", []),
                                  "state": result.get("state"),
                                  "observation_plan": result.get("observation_plan"),
                                  "state_transition": state_transition}),
    )
    case_source = "synthetic_demo" if source_type == "synthetic_demo" else "real_operator_case"
    run.recommendation_records = [AIRecommendation(
        strategy_id=item.get("strategy_id"),
        recommendation_content=item["content"],
        reasoning_snapshot=_json(item.get("reasoning_snapshot", {})),
        pattern_refs=_json(item.get("pattern_refs", [])),
        case_source=case_source,
    ) for item in (recommendation_snapshots or [])]
    db.add(run)
    db.commit()
    db.refresh(run)
    if state_transition:
        from_state, to_state, trigger = state_transition
        db.add(AIStateTransition(campaign_id=run.campaign_id, from_state=from_state,
                                 to_state=to_state, trigger=trigger, analysis_run_id=run.id))
        db.commit()
    return run


def list_analysis_history(db: Session, campaign_id: str | None = None,
                          include_synthetic: bool = False) -> list[AIAnalysisRun]:
    stmt = select(AIAnalysisRun).order_by(AIAnalysisRun.id.desc())
    if campaign_id is not None:
        stmt = stmt.where(AIAnalysisRun.campaign_id == campaign_id)
    if not include_synthetic:
        stmt = stmt.where(AIAnalysisRun.source_type != "synthetic_demo")
    return list(db.scalars(stmt).all())
