"""Deterministic state mapping and transition validation for AI decisions."""

from dataclasses import dataclass


STATES = {"NEW", "OBSERVING", "WAIT_OBSERVE", "ACTIONABLE", "CLOSED_REBUILD", "NEEDS_CONFIRMATION"}


def state_for_decision(decision: str) -> str:
    if decision == "WAIT_OBSERVE":
        return "WAIT_OBSERVE"
    if decision.startswith("CLOSE_REBUILD") or decision == "EMPTY_BURN":
        return "CLOSED_REBUILD"
    if decision == "NEEDS_CONFIRMATION":
        return "NEEDS_CONFIRMATION"
    return "ACTIONABLE"


def transition(previous_state: str | None, decision: str) -> tuple[str, str, str]:
    """Return (from_state, to_state, trigger); no LLM input is accepted."""
    from_state = previous_state if previous_state in STATES else "NEW"
    to_state = state_for_decision(decision)
    if from_state == "NEW" and to_state == "WAIT_OBSERVE":
        return from_state, to_state, "initial analysis requires observation"
    if from_state == to_state:
        return from_state, to_state, "decision remains unchanged"
    triggers = {
        "CLOSED_REBUILD": "deterministic rule requires close and rebuild",
        "ACTIONABLE": "deterministic rule produced an actionable decision",
        "NEEDS_CONFIRMATION": "deterministic rule requires human confirmation",
        "WAIT_OBSERVE": "deterministic rule requires another observation",
    }
    return from_state, to_state, triggers[to_state]


def observation_plan(campaign_id: str, previous_analysis_id: int | None,
                     current_state: str, reason: str | None = None) -> dict | None:
    if current_state != "WAIT_OBSERVE":
        return None
    return {
        "campaign_id": campaign_id,
        "previous_analysis_id": previous_analysis_id,
        "next_observation_reason": reason or "比较下一轮数据后重新运行确定性规则",
        "metrics_to_compare": ["spend", "orders", "ROI", "CTR", "CVR", "completion_rate"],
        "current_state": current_state,
    }
