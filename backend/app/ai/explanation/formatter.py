"""Deterministic fallback report for the Decision Reasoning Layer."""


def _stage_text(stage: str) -> str:
    return {
        "UNKNOWN": "当前阶段无法确认",
        "TESTING": "测试观察阶段",
        "LEARNING": "学习优化阶段",
        "SCALING": "扩量探索阶段",
        "SATURATING": "可能进入消耗趋平阶段",
        "REBUILD_CANDIDATE": "候选重建阶段",
    }.get(stage, "当前阶段无法确认")


def _video_text(status: str) -> str:
    return {"NORMAL": "视频指标达到当前业务正常标准", "LOW": "视频指标未达到当前业务正常标准",
            "MISSING": "缺少完整视频指标，暂时无法判断视频质量",
            "UNKNOWN": "当前无法判断视频质量"}.get(status, "当前无法判断视频质量")


def _roi_text(status: str, facts: dict) -> str:
    labels = {"LOW": "当前 ROI 低于目标 ROI", "HIGH": "当前 ROI 高于目标 ROI",
              "NORMAL": "当前 ROI 接近目标 ROI", "MISSING": "缺少目标 ROI，无法判断 ROI 是否达标",
              "UNKNOWN": "当前无法判断 ROI 是否达标"}
    text = labels.get(status, "当前无法判断 ROI 是否达标")
    if facts.get("current_roi") is not None and facts.get("target_roi") is not None:
        text += f"（当前 {facts['current_roi']}，目标 {facts['target_roi']}）"
    return text


def build_operation_report(reasoning_result: dict, *, decision: str | None = None,
                           state: str | None = None, llm_explanation: dict | None = None) -> dict:
    """Return a complete report while preserving deterministic fields.

    `llm_explanation` is accepted only as prose. It cannot replace facts,
    decision, state, references, strategies, or observation metrics.
    """
    facts = reasoning_result.get("fact_summary") or {}
    diagnosis = reasoning_result.get("metric_diagnosis") or {}
    causes = reasoning_result.get("possible_causes") or []
    strategies = reasoning_result.get("candidate_strategies") or []
    plan = reasoning_result.get("observation_plan") or {}
    llm = llm_explanation or {}
    report = {
        "campaign_stage": _stage_text(reasoning_result.get("campaign_stage", "UNKNOWN")),
        "campaign_stage_code": reasoning_result.get("campaign_stage", "UNKNOWN"),
        "current_situation_summary": (
            f"消耗 {facts['spend']}，订单 {facts['orders']}。"
            if facts.get("spend") is not None and facts.get("orders") is not None
            else "当前缺少完整消耗或订单事实，无法形成完整总结。"
        ),
        "video_quality_judgment": _video_text(diagnosis.get("video_quality", "UNKNOWN")),
        "roi_problem_judgment": _roi_text(diagnosis.get("roi_status", "UNKNOWN"), facts),
        "possible_causes": causes,
        "recommended_actions": [item["strategy"] for item in strategies],
        "recommendation_reasons": [item["reason"] for item in strategies],
        "next_observation_metrics": plan.get("metrics_to_compare", []),
        "uncertainties": list(plan.get("uncertainties", [])),
        "decision": decision or facts.get("decision"),
        "state": state or facts.get("state"),
        "pattern_refs": reasoning_result.get("pattern_refs", []),
        "knowledge_refs": reasoning_result.get("knowledge_refs", []),
        "mode": "template_fallback",
    }
    # Existing LLM explanation may improve prose, but it is deliberately kept
    # in a separate field and cannot alter any deterministic report field.
    if isinstance(llm.get("summary"), str) and llm["summary"].strip():
        report["llm_summary"] = llm["summary"]
        report["mode"] = "llm_prose_plus_deterministic_facts"
    return report
