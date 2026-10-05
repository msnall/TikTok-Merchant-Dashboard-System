import pytest

from app.ai.state_machine import observation_plan, state_for_decision, transition


@pytest.mark.parametrize("decision,expected", [
    ("WAIT_OBSERVE", "WAIT_OBSERVE"),
    ("CLOSE_REBUILD_KEEP_ROI", "CLOSED_REBUILD"),
    ("CLOSE_REBUILD_RAISE_ROI", "CLOSED_REBUILD"),
    ("EMPTY_BURN", "CLOSED_REBUILD"),
    ("NEEDS_CONFIRMATION", "NEEDS_CONFIRMATION"),
    ("ACTIONABLE", "ACTIONABLE"),
    ("KEEP_OBSERVING", "ACTIONABLE"),
])
def test_state_mapping_is_deterministic(decision, expected):
    assert state_for_decision(decision) == expected


@pytest.mark.parametrize("previous,decision,expected_from,expected_to", [
    (None, "WAIT_OBSERVE", "NEW", "WAIT_OBSERVE"),
    ("WAIT_OBSERVE", "WAIT_OBSERVE", "WAIT_OBSERVE", "WAIT_OBSERVE"),
    ("WAIT_OBSERVE", "NEEDS_CONFIRMATION", "WAIT_OBSERVE", "NEEDS_CONFIRMATION"),
    ("WAIT_OBSERVE", "CLOSE_REBUILD_KEEP_ROI", "WAIT_OBSERVE", "CLOSED_REBUILD"),
    ("WAIT_OBSERVE", "ACTIONABLE", "WAIT_OBSERVE", "ACTIONABLE"),
    ("ACTIONABLE", "WAIT_OBSERVE", "ACTIONABLE", "WAIT_OBSERVE"),
    ("ACTIONABLE", "CLOSE_REBUILD_RAISE_ROI", "ACTIONABLE", "CLOSED_REBUILD"),
    ("CLOSED_REBUILD", "ACTIONABLE", "CLOSED_REBUILD", "ACTIONABLE"),
])
def test_transition_cases(previous, decision, expected_from, expected_to):
    from_state, to_state, trigger = transition(previous, decision)
    assert (from_state, to_state) == (expected_from, expected_to)
    assert trigger


def test_observation_plan_contains_required_comparison_fields():
    plan = observation_plan("demo", 10, "WAIT_OBSERVE")
    assert plan["campaign_id"] == "demo"
    assert plan["previous_analysis_id"] == 10
    assert plan["current_state"] == "WAIT_OBSERVE"
    assert plan["metrics_to_compare"] == ["spend", "orders", "ROI", "CTR", "CVR", "completion_rate"]


def test_non_wait_state_has_no_observation_plan():
    assert observation_plan("demo", None, "ACTIONABLE") is None
