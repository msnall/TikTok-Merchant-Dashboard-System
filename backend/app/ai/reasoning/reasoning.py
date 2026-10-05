"""Orchestrates deterministic reasoning without parsing text or calling rules."""

from .fact_summary import build_fact_summary
from .metric_diagnosis import build_metric_diagnosis
from .observation_planner import build_observation_plan
from .pattern_matcher import match_patterns
from .strategy_generator import build_candidate_strategies


def _stage(analysis_result: dict, facts: dict, diagnosis: dict) -> str:
    decision = str(analysis_result.get("decision", "")).split(".")[-1]
    state = str(analysis_result.get("state", "")).split(".")[-1]
    current = analysis_result.get("current_analysis") or {}
    delta = analysis_result.get("historical_delta") or {}
    if decision.startswith("CLOSE_REBUILD") or decision == "EMPTY_BURN" or state == "CLOSED_REBUILD":
        return "REBUILD_CANDIDATE"
    if current.get("is_new_product") and current.get("spend_growth_confirmed") and current.get("orders_normal_confirmed"):
        return "SCALING"
    if current.get("spend_pattern") == "increase_then_flat" and analysis_result.get("reliable_timeseries"):
        return "SATURATING"
    if delta and (delta.get("delta_spend") or delta.get("delta_orders")):
        return "LEARNING"
    if facts.get("spend") is not None or facts.get("orders") is not None:
        return "TESTING"
    return "UNKNOWN"


def build_reasoning_result(analysis_result: dict) -> dict:
    """Build a schema-shaped result from already computed analysis evidence."""
    facts = build_fact_summary(analysis_result)
    diagnosis = build_metric_diagnosis(analysis_result, facts)
    patterns = match_patterns(analysis_result)
    strategies = build_candidate_strategies(analysis_result, patterns, diagnosis)
    stage = _stage(analysis_result, facts, diagnosis)
    plan = build_observation_plan(analysis_result, patterns)
    refs = analysis_result.get("knowledge_refs") or []
    knowledge_refs = [item.get("rule_id") for item in refs if item.get("rule_id")]
    if not refs:
        plan["uncertainties"].append("NO_KNOWLEDGE_EVIDENCE")
    causes = []
    ids = {item["pattern_id"] for item in patterns}
    if "P001" in ids:
        causes.append({"cause": "可能存在人群、商品页或目标ROI策略问题", "supporting_evidence": ["video_quality == NORMAL", "roi_status == LOW"], "missing_evidence": ["商品页转化数据", "人群数据"], "confidence": "LOW"})
    if "P002" in ids:
        causes.append({"cause": "可能存在素材前几秒或卖点表达不足", "supporting_evidence": ["video_quality == LOW"], "missing_evidence": ["素材版本对比", "受众数据"], "confidence": "MEDIUM"})
    if "P004" in ids:
        causes.append({"cause": "可能存在商品页承接或价格转化不足", "supporting_evidence": ["ctr_status == NORMAL", "cvr_status == LOW"], "missing_evidence": ["商品页漏斗", "价格信息"], "confidence": "LOW"})
    if "P009" in ids:
        causes.append({"cause": "可能只是当前数据不足以支持完整诊断", "supporting_evidence": ["required evidence missing"], "missing_evidence": ["缺失字段"], "confidence": "HIGH"})
    return {"campaign_stage": stage, "fact_summary": facts, "metric_diagnosis": diagnosis,
            "possible_causes": causes, "candidate_strategies": strategies,
            "observation_plan": plan, "pattern_refs": patterns,
            "knowledge_refs": knowledge_refs}
