"""Fact-only projection used by the reasoning layer."""


FACT_FIELDS = (
    "spend", "orders", "current_roi", "target_roi", "ctr", "cvr",
    "completion_rate", "decision", "state",
)


def build_fact_summary(analysis_result: dict) -> dict:
    current = analysis_result.get("current_analysis") or analysis_result.get("normalized_input") or {}
    rule = analysis_result.get("rule_result") or analysis_result
    video = analysis_result.get("video") or {}
    facts = {
        "spend": current.get("spend"),
        "orders": current.get("orders"),
        "current_roi": current.get("current_roi"),
        "target_roi": current.get("target_roi"),
        "ctr": video.get("ctr", current.get("ctr")),
        "cvr": video.get("cvr", current.get("cvr")),
        "completion_rate": video.get("official_completion_rate",
                                       current.get("official_completion_rate")),
        "decision": analysis_result.get("decision", rule.get("decision")),
        "state": analysis_result.get("state"),
    }
    return facts
