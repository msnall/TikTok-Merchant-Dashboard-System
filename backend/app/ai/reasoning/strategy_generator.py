"""Candidate strategy generation; no action is executed."""


def build_candidate_strategies(analysis_result: dict, patterns: list[dict], diagnosis: dict) -> list[dict]:
    ids = {item["pattern_id"] for item in patterns}
    strategies = []
    if "P001" in ids:
        strategies.append({"strategy": "建议继续观察ROI与订单并检查商品页转化", "reason": "视频质量未显示明显异常而ROI低于目标", "risk": "当前缺少商品页、人群和利润证据"})
    if "P002" in ids:
        strategies.append({"strategy": "建议检查Hook、首帧和素材结构并测试新素材", "reason": "素材指标偏低，需对比完整视频数据", "risk": "低视频指标不等于唯一转化原因"})
    if "P003" in ids:
        strategies.append({"strategy": "建议测试首帧和Hook", "reason": "CTR偏低但CVR处于当前正常区间", "risk": "曝光质量和受众规模尚未确认"})
    if "P004" in ids:
        strategies.append({"strategy": "建议检查商品页、价格和点击到订单漏斗", "reason": "CTR正常但CVR偏低", "risk": "当前没有完整落地页数据"})
    if "P005" in ids:
        strategies.append({"strategy": "建议核对可靠时序后再评估新人群或新计划", "reason": "ROI高且可靠时序显示消耗趋平候选", "risk": "没有可靠时序不能确认饱和"})
    if "P006" in ids:
        strategies.append({"strategy": "建议检查CVR、商品页和新增消耗对应订单", "reason": "消耗增加但订单未同步增加", "risk": "归因窗口和延迟尚未确认"})
    if "P007" in ids:
        strategies.append({"strategy": "建议小步探索预算扩量", "reason": "新品、消耗增长、订单和视频信号均已提供", "risk": "案例经验不是固定预算规则，需人工确认"})
    facts = (analysis_result.get("current_analysis") or {})
    if analysis_result.get("reported_first_day") and facts.get("orders") and facts.get("current_roi") is not None:
        strategies.append({"strategy": "建议继续观察订单与ROI稳定性，确认新品和增长趋势后评估小步增预算", "reason": "首日已产生订单并记录ROI", "risk": "缺少目标ROI和连续趋势，不能确认已经进入扩量"})
    if "P009" in ids and (facts.get("spend") is None or facts.get("orders") is None):
        strategies.append({"strategy": "建议补充缺失字段并暂缓经验归因", "reason": "当前数据不足以支持完整推理", "risk": "缺失证据可能改变问题定位"})
    if not strategies:
        strategies.append({"strategy": "建议继续收集可比数据", "reason": "当前没有足够Pattern证据", "risk": "时间窗口和业务背景仍需确认"})
    return strategies
