from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from .analysis_service import analyze_text, serialize_run
from .models import AIAnalysisRun, AIStateTransition, DecisionAction

router = APIRouter(prefix="/api/ai", tags=["ai analysis"])

class AnalysisRequest(BaseModel):
    campaign_id: str = Field(min_length=1, max_length=128)
    text: str = Field(min_length=1, max_length=5000)

class DecisionActionRequest(BaseModel):
    action_type: str = Field(pattern="^(ACCEPT|REJECT|MODIFY)$")
    actual_action: str = Field(min_length=1, max_length=2000)
    operator_note: str | None = Field(default=None, max_length=2000)

@router.post("/analyses")
def create_analysis(payload: AnalysisRequest, db: Session = Depends(get_db)):
    result = analyze_text(db, payload.campaign_id, payload.text)
    return {"analysis_id": result["analysis_id"], "campaign_id": payload.campaign_id,
            "decision": result["decision"], "current_analysis": result["current_analysis"],
            "historical_comparison": result["historical_comparison"],
            "recommendations": result["recommendations"], "next_observation": result["next_observation"],
            "state": result.get("state"), "state_transition": result.get("state_transition"),
            "observation_plan": result.get("observation_plan"),
            "confidence": result.get("confidence"), "confidence_reasons": result.get("confidence_reasons", []),
            "reasoning_result": result.get("reasoning_result"),
            "diagnosis_result": result.get("diagnosis_result"),
            "strategy_refs": result.get("strategy_refs", []),
            "strategy_candidate_actions": result.get("strategy_candidate_actions", []),
            "strategy_ranking": result.get("strategy_ranking"),
            "strategy_impact": result.get("strategy_impact"),
            "operation_report": result.get("operation_report"),
            "summary": result["summary"],
            "llm_status": result["llm_status"], "llm_model": result["llm_model"],
            "explanation": result["explanation"],
            "knowledge_refs": result["knowledge_refs"], "rules_used": result["rules_used"],
            "uncertainties": result["uncertainties"]}

@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: int, db: Session = Depends(get_db)):
    run = db.get(AIAnalysisRun, analysis_id)
    if not run: raise HTTPException(404, "分析记录不存在")
    return serialize_run(run)

@router.get("/campaigns/{campaign_id}/history")
def campaign_history(campaign_id: str, db: Session = Depends(get_db)):
    runs = db.scalars(select(AIAnalysisRun).where(AIAnalysisRun.campaign_id == campaign_id,
        AIAnalysisRun.source_type != "synthetic_demo").order_by(AIAnalysisRun.id.asc())).all()
    transitions = db.scalars(select(AIStateTransition).where(AIStateTransition.campaign_id == campaign_id)
                             .order_by(AIStateTransition.id.asc())).all()
    return {"campaign_id": campaign_id, "items": [serialize_run(run) for run in runs],
            "transitions": [{"id": item.id, "from_state": item.from_state, "to_state": item.to_state,
                             "trigger": item.trigger, "analysis_run_id": item.analysis_run_id,
                             "created_at": item.created_at} for item in transitions]}

@router.get("/campaigns/{campaign_id}/latest")
def campaign_latest(campaign_id: str, db: Session = Depends(get_db)):
    run = db.scalars(select(AIAnalysisRun).where(AIAnalysisRun.campaign_id == campaign_id,
        AIAnalysisRun.source_type != "synthetic_demo").order_by(AIAnalysisRun.id.desc())).first()
    if not run: raise HTTPException(404, "该计划暂无分析记录")
    return serialize_run(run)


@router.post("/analyses/{analysis_id}/actions")
def create_decision_action(analysis_id: int, payload: DecisionActionRequest,
                           db: Session = Depends(get_db)):
    run = db.get(AIAnalysisRun, analysis_id)
    if not run:
        raise HTTPException(404, "分析记录不存在")
    action = DecisionAction(analysis_run_id=analysis_id, action_type=payload.action_type,
                            actual_action=payload.actual_action, operator_note=payload.operator_note)
    db.add(action)
    db.commit()
    db.refresh(action)
    return {"id": action.id, "analysis_run_id": action.analysis_run_id,
            "action_type": action.action_type, "actual_action": action.actual_action,
            "operator_note": action.operator_note, "created_at": action.created_at}


@router.get("/analyses/{analysis_id}/actions")
def list_decision_actions(analysis_id: int, db: Session = Depends(get_db)):
    if not db.get(AIAnalysisRun, analysis_id):
        raise HTTPException(404, "分析记录不存在")
    items = db.scalars(select(DecisionAction).where(DecisionAction.analysis_run_id == analysis_id)
                       .order_by(DecisionAction.id.asc())).all()
    return {"analysis_id": analysis_id, "items": [
        {"id": item.id, "analysis_run_id": item.analysis_run_id, "action_type": item.action_type,
         "actual_action": item.actual_action, "operator_note": item.operator_note,
         "created_at": item.created_at} for item in items]}


@router.get("/analyses/{analysis_id}/audit")
def analysis_audit(analysis_id: int, db: Session = Depends(get_db)):
    run = db.get(AIAnalysisRun, analysis_id)
    if not run:
        raise HTTPException(404, "分析记录不存在")
    data = serialize_run(run)
    actions = db.scalars(select(DecisionAction).where(DecisionAction.analysis_run_id == analysis_id)
                         .order_by(DecisionAction.id.asc())).all()
    data["human_actions"] = [{"id": item.id, "action_type": item.action_type,
                               "actual_action": item.actual_action,
                               "operator_note": item.operator_note,
                               "created_at": item.created_at} for item in actions]
    return data


@router.get("/feedback/stats")
def feedback_stats(db: Session = Depends(get_db)):
    actions = db.scalars(select(DecisionAction).join(AIAnalysisRun,
                                DecisionAction.analysis_run_id == AIAnalysisRun.id)
                         .where(AIAnalysisRun.source_type != "synthetic_demo")).all()
    summary = {"total": len(actions), "accept": 0, "reject": 0, "modify": 0,
               "agreement": 0, "modification_rate": 0.0}
    for action in actions:
        key = action.action_type.lower()
        summary[key] = summary.get(key, 0) + 1
        run = db.get(AIAnalysisRun, action.analysis_run_id)
        if action.action_type == "ACCEPT" and run and run.recommendations:
            try:
                import json
                if action.actual_action in json.loads(run.recommendations):
                    summary["agreement"] += 1
            except (TypeError, ValueError, json.JSONDecodeError):
                pass
    summary["modification_rate"] = (summary["modify"] / summary["total"] if summary["total"] else 0.0)
    return summary
