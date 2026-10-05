"""Deterministic, evidence-bound diagnostic explanation of an existing decision."""


def _present(value):
    return value is not None and not isinstance(value, bool)


def build_diagnosis_result(reasoning_result: dict, rule_result: dict) -> dict:
    facts = reasoning_result.get("fact_summary") or {}
    metrics = reasoning_result.get("metric_diagnosis") or {}
    decision = rule_result.get("decision")
    confirmed = []
    currency = next((item.get("value") for item in (rule_result.get("facts") or [])
                     if item.get("field") == "currency"), None)
    labels = (("spend", "已消耗", f" {currency}" if currency else "（币种未确认）"),
              ("orders", "当前订单", "单"),
              ("current_roi", "当前 ROI", ""), ("target_roi", "目标 ROI", ""),
              ("ctr", "CTR", ""), ("cvr", "CVR", ""),
              ("completion_rate", "完播率", ""))
    for key, label, unit in labels:
        if _present(facts.get(key)):
            value = facts[key]
            if key in {"ctr", "cvr", "completion_rate"}:
                value = f"{value * 100:g}%"
            confirmed.append(f"{label} {value}{unit}")

    hypotheses = []

    def add(cause, support, missing):
        hypotheses.append({"cause": f"可能{cause}", "confidence": "LOW",
                           "supporting_evidence": support, "missing_evidence": missing})

    summary = "当前证据不足，无法定位主要问题。"
    steps = []
    limitations = []
    if decision == "EMPTY_BURN":
        summary = "广告已有消耗，但尚未产生订单；满足当前空烧判断条件。"
        confirmed.append("已满足当前空烧判断条件")
        support = [f"消耗 {facts['spend']} {currency or '（币种待核对）'}，订单 0 单"] if _present(facts.get("spend")) and facts.get("orders") == 0 else []
        add("素材吸引不足", support,
            (["CTR"] if not _present(facts.get("ctr")) else ["CTR 趋势"])
            + (["完播率"] if not _present(facts.get("completion_rate")) else ["完播率趋势"])
            + ["素材对比"])
        add("商品转化不足", support,
            (["CVR"] if not _present(facts.get("cvr")) else ["CVR 趋势"])
            + ["商品页转化数据"])
        add("流量匹配不足", support, ["CPC", "受众数据"])
        steps = ["核对 CTR 与完播率", "核对 CVR 与商品页数据", "核对 CPC 与受众数据"]
    elif (metrics.get("roi_status") == "LOW" and metrics.get("video_quality") == "NORMAL"
          and _present(facts.get("current_roi")) and _present(facts.get("target_roi"))):
        summary = "视频指标未显示明显异常，但当前 ROI 低于目标。"
        support = [f"当前 ROI {facts['current_roi']} 低于目标 {facts['target_roi']}", "视频指标达到当前业务正常标准"]
        add("商品转化效率不足", support, ["商品页转化数据", "CVR 趋势"])
        add("流量质量不匹配", support, ["CPC", "受众数据", "CTR 趋势"])
        add("目标 ROI 策略与当前投放表现不匹配", support, ["利润依据", "可比 ROI 档位结果"])
        steps = ["检查商品页转化和 CVR 趋势", "核对流量来源与 CPC", "核对目标 ROI 策略依据"]
    elif metrics.get("ctr_status") == "LOW" and _present(facts.get("ctr")):
        summary = "当前 CTR 低于业务正常标准，点击意愿可能不足。"
        add("素材吸引力不足", [f"CTR {facts['ctr'] * 100:g}%"], ["CTR 趋势", "素材版本对比"])
        steps = ["比较 CTR 趋势与素材版本"]
    elif metrics.get("cvr_status") == "LOW" and _present(facts.get("cvr")):
        summary = "当前 CVR 低于业务正常标准，点击后转化可能不足。"
        support = [f"CVR {facts['cvr'] * 100:g}%"]
        add("商品页承接不足", support, ["商品页转化数据"])
        add("价格或优惠与用户预期不匹配", support, ["价格与优惠对照数据"])
        add("购买流程存在阻力", support, ["购买流程漏斗数据"])
        steps = ["核对商品页、价格与优惠数据", "检查购买流程漏斗"]
    elif metrics.get("roi_status") == "LOW" and _present(facts.get("current_roi")) and _present(facts.get("target_roi")):
        summary = "当前 ROI 低于目标，但缺少足够证据定位原因。"
        steps = ["补充完整视频指标和转化数据"]
    elif metrics.get("roi_status") == "HIGH":
        summary = "当前 ROI 高于目标，仍需结合订单和消耗变化评估。"
    elif decision == "WAIT_OBSERVE":
        summary = "当前判断为继续观察，下一轮应比较订单、消耗和 ROI 的变化。"

    if not _present(facts.get("target_roi")):
        limitations.append("缺少目标 ROI，不能判断 ROI 是否达标。")
    if metrics.get("video_quality") not in {"NORMAL", "LOW", "HIGH"}:
        limitations.append("缺少可信的完整视频指标，不能判断素材质量。")
    if not _present(facts.get("orders")) or not _present(facts.get("spend")):
        limitations.append("缺少订单或消耗数据，不能确认转化与消耗关系。")
    if not rule_result.get("historical_comparison", {}).get("previous_analysis_id"):
        limitations.append("缺少上一轮可比分析，不能判断变化趋势。")
    if not steps:
        steps = ["补充消耗、订单、ROI 与视频指标后再比较"]
    return {"confirmed_facts": confirmed, "problem_summary": summary,
            "failure_hypotheses": hypotheses, "diagnostic_limitations": limitations,
            "next_validation_steps": steps}
