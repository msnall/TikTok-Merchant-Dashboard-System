"""Observation plan with no invented time window."""


METRICS = ["spend", "orders", "ROI", "CTR", "CVR", "completion_rate"]


def build_observation_plan(analysis_result: dict, patterns: list[dict]) -> dict:
    delta = analysis_result.get("historical_delta") or {}
    uncertainties = []
    if not delta:
        uncertainties.append("暂无可比较的历史Delta")
    current = analysis_result.get("current_analysis") or {}
    if current.get("spend_pattern") == "increase_then_flat" and not analysis_result.get("reliable_timeseries"):
        uncertainties.append("缺少可靠时间序列，不能确认消耗趋平")
    if not analysis_result.get("confidence"):
        uncertainties.append("数据支持度尚未提供")
    return {"metrics_to_compare": METRICS, "time_window": None,
            "trigger_conditions": [], "uncertainties": uncertainties}
