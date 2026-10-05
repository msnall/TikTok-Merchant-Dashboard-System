"""Deterministic metric status classification; missing values stay UNKNOWN."""

from .fact_summary import build_fact_summary

STATUSES = {"NORMAL", "LOW", "HIGH", "MISSING", "UNKNOWN"}


def _ratio(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    return value / 100 if value > 1 else value


def _video_status(rule_result: dict, facts: dict) -> str:
    status = str(rule_result.get("video_status", "")).split(".")[-1]
    if status == "VIDEO_NORMAL":
        return "NORMAL"
    if status == "VIDEO_POOR":
        return "LOW"
    if any(facts.get(field) is None for field in ("ctr", "cvr", "completion_rate")):
        return "MISSING"
    return "UNKNOWN"


def _roi_status(rule_result: dict, facts: dict) -> str:
    status = str(rule_result.get("roi_status", "")).split(".")[-1]
    return {"BELOW_TARGET": "LOW", "NEAR_TARGET": "NORMAL", "ABOVE_TARGET": "HIGH"}.get(status, "UNKNOWN")


def _threshold_status(value, low, high):
    if value is None:
        return "MISSING"
    ratio = _ratio(value)
    if ratio is None:
        return "UNKNOWN"
    if ratio < low:
        return "LOW"
    if ratio > high:
        return "HIGH"
    return "NORMAL"


def build_metric_diagnosis(analysis_result: dict, facts: dict | None = None) -> dict:
    facts = facts or build_fact_summary(analysis_result)
    rule = analysis_result.get("rule_result") or analysis_result
    delta = analysis_result.get("historical_delta") or {}
    comparison = analysis_result.get("historical_comparison") or {}
    historical = "NORMAL" if delta else ("MISSING" if not comparison.get("previous_analysis_id") else "UNKNOWN")
    spend_status = "UNKNOWN"
    if facts.get("spend") is None:
        spend_status = "MISSING"
    elif delta.get("delta_spend") is not None:
        spend_status = "HIGH" if delta["delta_spend"] > 0 else ("LOW" if delta["delta_spend"] < 0 else "NORMAL")
    return {
        "video_quality": _video_status(rule, facts),
        "roi_status": _roi_status(rule, facts) if facts.get("target_roi") is not None else "MISSING",
        "ctr_status": _threshold_status(facts.get("ctr"), 0.02, 0.04),
        "cvr_status": _threshold_status(facts.get("cvr"), 0.10, 0.20),
        "spend_status": spend_status,
        "historical_status": historical,
    }
