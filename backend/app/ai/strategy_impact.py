"""Explain possible effects of a ranked strategy without predicting outcomes."""


_IMPACTS = {
    "S001": (
        ("人工确认后重建可能重新探索投放人群",),
        ("重建可能产生新的试错消耗，不能保证获得订单",),
        ("spend", "orders", "current_roi"),
        ("重建后的新增消耗仍未带来订单", "人工核对发现空烧条件或币种不成立"),
    ),
    "S002": (
        ("继续观察可能积累更多订单和转化证据",),
        ("订单样本少，短期波动可能误导判断",),
        ("orders", "spend", "current_roi", "cvr"),
        ("后续订单没有改善且消耗继续增加", "出现更高优先级的确定性风险信号"),
    ),
    "S003": (
        ("检查转化链路可能帮助定位视频之外的 ROI 问题",),
        ("视频正常不代表商品页、人群或目标 ROI 一定有问题",),
        ("current_roi", "target_roi", "orders", "cvr", "ctr"),
        ("补充数据后视频质量不再正常", "受控测试后 ROI 或订单表现恶化"),
    ),
    "S004": (
        ("测试新素材可能改善点击与视频观看表现",),
        ("新素材效果不确定，额外测试可能增加消耗",),
        ("ctr", "cvr", "official_completion_rate", "orders", "current_roi"),
        ("测试素材后视频指标仍未改善", "核对后发现视频指标口径不可靠"),
    ),
    "S005": (
        ("经人工确认的小步预算探索可能获得更多订单信号",),
        ("增加预算可能先扩大消耗，而订单和 ROI 未必同步改善",),
        ("spend", "orders", "current_roi", "cvr"),
        ("消耗增加而订单未同步改善", "履约或退货风险不适合继续探索"),
    ),
    "S006": (
        ("检查转化与受控 ROI 档位测试可能帮助定位优化方向",),
        ("调整目标 ROI 的方向和幅度尚未确定，测试可能降低实际 ROI",),
        ("current_roi", "target_roi", "orders", "cvr", "spend"),
        ("受控测试后 ROI 或订单表现恶化", "缺少可比的目标 ROI 或利润依据"),
    ),
    "S007": (
        ("人工设计多档位对照可能提供不同目标 ROI 下的可比证据",),
        ("不同档位可能带来额外试错消耗，不能据此推导利润公式",),
        ("target_roi", "current_roi", "spend", "orders"),
        ("档位之间缺少可比报表口径", "测试消耗增加而未获得可用结论"),
    ),
}


def analyze_strategy_impact(primary_strategy: str | None,
                            current_reasoning_result: dict,
                            current_state: str | None) -> dict | None:
    """Return conditional impact for the primary strategy, or None if absent.

    Confidence describes evidence support for this explanation, not the
    probability that a benefit will occur. Inputs are read but never mutated.
    """
    if primary_strategy is None:
        return None
    if primary_strategy not in _IMPACTS:
        raise ValueError(f"Unknown strategy: {primary_strategy}")

    benefits, risks, metrics, failures = _IMPACTS[primary_strategy]
    facts = current_reasoning_result.get("fact_summary") or {}
    diagnosis = current_reasoning_result.get("metric_diagnosis") or {}
    confidence = "LOW"
    if (primary_strategy == "S001" and isinstance(facts.get("spend"), (int, float))
            and facts["spend"] > 3 and facts.get("orders") == 0):
        confidence = "MEDIUM"
    elif (primary_strategy == "S003" and diagnosis.get("roi_status") == "LOW"
          and diagnosis.get("video_quality") == "NORMAL"):
        confidence = "MEDIUM"
    elif (primary_strategy == "S004" and diagnosis.get("roi_status") == "LOW"
          and diagnosis.get("video_quality") == "LOW"):
        confidence = "MEDIUM"
    elif (primary_strategy == "S006" and diagnosis.get("roi_status") == "LOW"
          and facts.get("current_roi") is not None and facts.get("target_roi") is not None):
        confidence = "MEDIUM"
    elif primary_strategy == "S002" and isinstance(facts.get("orders"), int) and 1 <= facts["orders"] <= 9:
        confidence = "MEDIUM"

    return {
        "strategy_id": primary_strategy,
        "expected_benefits": list(benefits),
        "potential_risks": list(risks),
        "monitor_metrics": list(metrics),
        "failure_conditions": list(failures),
        "confidence": confidence,
    }
