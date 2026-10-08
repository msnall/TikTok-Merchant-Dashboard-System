"""Pattern matching over existing deterministic analysis output."""

from .fact_summary import build_fact_summary
from .metric_diagnosis import build_metric_diagnosis

PATTERN_IDS = tuple(f"P{i:03d}" for i in range(1, 11))


def _status(value):
    return str(value or "").split(".")[-1]


def match_patterns(analysis_result: dict) -> list[dict]:
    facts = build_fact_summary(analysis_result)
    diagnosis = build_metric_diagnosis(analysis_result, facts)
    delta = analysis_result.get("historical_delta") or {}
    current = analysis_result.get("current_analysis") or {}
    rule = analysis_result.get("rule_result") or analysis_result
    matched: list[dict] = []

    def add(pattern_id, conditions, confidence="MEDIUM"):
        matched.append({"pattern_id": pattern_id, "matched_conditions": conditions, "confidence": confidence})

    if diagnosis["video_quality"] == "NORMAL" and diagnosis["roi_status"] == "LOW":
        add("P001", ["video_quality == NORMAL", "roi_status == LOW"])
    if diagnosis["video_quality"] == "LOW":
        add("P002", ["video_quality == LOW"], "HIGH")
    elif diagnosis["video_quality"] == "MISSING" and (diagnosis["ctr_status"] == "LOW" or diagnosis["completion_status"] == "LOW"):
        add("P002", ["partial video metric below normal threshold"], "LOW")
    if diagnosis["ctr_status"] == "LOW" and diagnosis["cvr_status"] == "NORMAL":
        add("P003", ["ctr_status == LOW", "cvr_status == NORMAL"])
    if diagnosis["ctr_status"] == "NORMAL" and diagnosis["cvr_status"] == "LOW":
        add("P004", ["ctr_status == NORMAL", "cvr_status == LOW"])
    reliable_timeseries = bool(analysis_result.get("reliable_timeseries") or current.get("reliable_timeseries"))
    if diagnosis["roi_status"] == "HIGH" and reliable_timeseries and current.get("spend_pattern") == "increase_then_flat":
        add("P005", ["roi_status == HIGH", "reliable_timeseries == true", "spend_pattern == increase_then_flat"])
    if delta.get("delta_spend", 0) > 0 and delta.get("delta_orders", 0) <= 0:
        add("P006", ["delta_spend > 0", "delta_orders <= 0"])
    if current.get("is_new_product") is True and current.get("spend_growth_confirmed") is True and current.get("orders_normal_confirmed") is True and diagnosis["video_quality"] == "NORMAL":
        add("P007", ["new product", "spend growth confirmed", "normal orders", "video_quality == NORMAL"])
    wait_count = analysis_result.get("consecutive_wait_observe", current.get("consecutive_wait_observe", 0))
    if wait_count and wait_count >= 2:
        add("P008", ["consecutive_wait_observe >= 2"])
    missing = [field for field in ("spend", "orders", "target_roi", "ctr", "cvr", "completion_rate") if facts.get(field) is None]
    if missing or (current.get("spend_pattern") == "increase_then_flat" and not reliable_timeseries):
        add("P009", ["required evidence missing"], "HIGH")
    if current.get("signals_conflict") or current.get("source_definitions_conflict") or analysis_result.get("signals_conflict"):
        add("P010", ["signals or source definitions conflict"], "HIGH")
    return matched
