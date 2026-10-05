"""Deterministic operator strategy matching; strategies never change decisions."""


def match_operator_strategies(analysis_result: dict) -> dict:
    current = analysis_result.get("current_analysis") or {}
    reasoning = analysis_result.get("reasoning_result") or {}
    diagnosis = reasoning.get("metric_diagnosis") or analysis_result.get("metric_diagnosis") or {}
    facts = reasoning.get("fact_summary") or {}
    orders = facts.get("orders", current.get("orders"))
    spend = facts.get("spend", current.get("spend"))
    decision = analysis_result.get("decision", facts.get("decision"))
    matched = []
    actions = []

    def add(strategy_id, action):
        matched.append(strategy_id)
        actions.append(action)

    if isinstance(spend, (int, float)) and spend > 3 and orders == 0 and current.get("currency", "USD") == "USD":
        add("S001", "候选：关停并重建计划，需人工确认")
    if isinstance(orders, int) and 1 <= orders <= 9:
        add("S002", "候选：继续观察订单和ROI，检查转化链路")
    if diagnosis.get("roi_status") == "LOW" and diagnosis.get("video_quality") == "NORMAL":
        add("S003", "候选：检查商品页和CVR，人工确认后测试相邻ROI档位")
    if diagnosis.get("roi_status") == "LOW" and diagnosis.get("video_quality") == "LOW":
        add("S004", "候选：检查Hook和素材结构，测试新素材")
    if (current.get("is_new_product") is True and current.get("spend_growth_confirmed") is True
            and current.get("orders_normal_confirmed") is True
            and diagnosis.get("video_quality") == "NORMAL"):
        add("S005", "候选：小步增加预算进行探索，需人工确认")
    if diagnosis.get("roi_status") == "LOW" and current.get("target_roi") is not None and current.get("current_roi") is not None:
        add("S006", "候选：检查CVR和商品页，测试相邻ROI档位，不自动修改目标ROI")
    if current.get("link_type") in {"A", "B"} and current.get("target_roi") is not None:
        add("S007", "候选：设计多个ROI档位进行对照测试，需人工确认")
    return {"strategy_refs": matched, "candidate_actions": actions}
