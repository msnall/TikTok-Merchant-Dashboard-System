"""Deterministic ranking of matched operator strategies.

Ranking is advisory only and never changes Rule Engine decisions or state.
"""

_PRIORITY = {"S001": 300, "S004": 220, "S003": 200, "S006": 180,
             "S005": 160, "S007": 120, "S002": 100}
_TITLES = {"S001": "空烧计划关闭重建", "S002": "有订单但订单少", "S003": "ROI低但视频正常",
           "S004": "视频差导致ROI低", "S005": "新品快速起量加预算", "S006": "ROI提升策略",
           "S007": "多ROI档位测试"}


def rank_operator_strategies(analysis_result: dict) -> dict:
    refs = list(analysis_result.get("strategy_refs") or [])
    current = analysis_result.get("current_analysis") or {}
    reasoning = analysis_result.get("reasoning_result") or {}
    facts = reasoning.get("fact_summary") or {}
    diagnosis = reasoning.get("metric_diagnosis") or {}
    matched = sorted(set(refs), key=lambda item: (-_PRIORITY.get(item, 0), item))
    primary = matched[0] if matched else None
    secondary = matched[1:]
    rejected = []
    for strategy_id in _PRIORITY:
        if strategy_id in matched:
            continue
        reason = _rejection_reason(strategy_id, current, facts, diagnosis)
        rejected.append({"strategy_id": strategy_id, "title": _TITLES[strategy_id], "reason": reason})
    ranking_reason = _ranking_reason(primary, secondary)
    return {"primary_strategy": primary,
            "secondary_strategies": secondary,
            "rejected_strategies": rejected,
            "ranking_reason": ranking_reason}


def _rejection_reason(strategy_id: str, current: dict, facts: dict, diagnosis: dict) -> str:
    if strategy_id == "S001":
        return "未同时满足 USD 消耗超过 3 且订单为 0"
    if strategy_id == "S002":
        return "订单不是 1-9 单，或订单数据缺失"
    if strategy_id == "S003":
        return "未同时满足 ROI 低和视频质量正常"
    if strategy_id == "S004":
        return "未同时满足 ROI 低和视频质量差"
    if strategy_id == "S005":
        return "缺少新品、消耗增长、订单正常和视频正常的完整确认信号"
    if strategy_id == "S006":
        return "未同时提供 ROI 低、当前 ROI 和目标 ROI"
    if strategy_id == "S007":
        return "缺少 A/B 链接或明确目标 ROI"
    return "当前条件不适用"


def _ranking_reason(primary: str | None, secondary: list[str]) -> str:
    if not primary:
        return "当前没有命中的运营策略，不能生成策略排序。"
    if primary == "S001":
        return "空烧是强确定条件，优先于视频和经验型策略。"
    if primary == "S004":
        return "视频质量差存在明确指标证据，优先于一般 ROI 优化策略。"
    if secondary:
        return "按确定条件、指标证据、经验候选的优先级排序；其余策略作为备选。"
    return "当前只有一个适用策略。"
