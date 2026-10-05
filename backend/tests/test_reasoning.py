import json
from pathlib import Path

from app.ai.reasoning import build_reasoning_result


CASES = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" /
                    "decision_reasoning_cases.json").read_text(encoding="utf-8"))


def _analysis(context):
    current = dict(context)
    status_values = {"ctr": {"LOW": 0.01, "NORMAL": 0.03, "HIGH": 0.08},
                     "cvr": {"LOW": 0.05, "NORMAL": 0.12, "HIGH": 0.25}}
    for key, values in status_values.items():
        if current.get(key) in values:
            current[key] = values[current[key]]
    if current.get("video_quality") == "NORMAL":
        current.update({"ctr": current.get("ctr", 0.03), "cvr": current.get("cvr", 0.12), "completion_rate": 0.36})
    elif current.get("video_quality") == "LOW":
        current.update({"ctr": current.get("ctr", 0.01), "cvr": current.get("cvr", 0.05), "completion_rate": 0.2})
    current.setdefault("spend", 8)
    current.setdefault("orders", 3)
    current.setdefault("target_roi", 0.82 if context.get("roi_status") else None)
    current.setdefault("current_roi", 0.71 if context.get("roi_status") == "LOW" else 0.82)
    current.setdefault("consecutive_wait_observe", context.get("consecutive_wait_observe", 0))
    rule = {"decision": context.get("decision", "NEEDS_CONFIRMATION"),
            "video_status": "VIDEO_NORMAL" if context.get("video_quality") == "NORMAL" else
                            "VIDEO_POOR" if context.get("video_quality") == "LOW" else "UNKNOWN",
            "roi_status": {"LOW": "BELOW_TARGET", "NORMAL": "NEAR_TARGET", "HIGH": "ABOVE_TARGET"}.get(context.get("roi_status"), "UNKNOWN")}
    return {"current_analysis": current, "rule_result": rule, "decision": rule["decision"],
            "state": "CLOSED_REBUILD" if rule["decision"] == "CLOSE_REBUILD" else "ACTIONABLE",
            "historical_delta": context.get("historical_delta") or {
                key: context[key] for key in ("delta_spend", "delta_orders", "delta_roi") if key in context
            },
            "historical_comparison": {"previous_analysis_id": 1 if context.get("historical_delta") else None},
            "knowledge_refs": [], "confidence": "MEDIUM",
            "consecutive_wait_observe": context.get("consecutive_wait_observe", 2 if context.get("decision") == "WAIT_OBSERVE" else 0),
            "reliable_timeseries": context.get("reliable_timeseries", False),
            "signals_conflict": context.get("signals_conflict", False)}


def test_fixture_contains_thirty_contract_cases():
    assert len(CASES) == 30
    required = {"id", "input_context", "expected_patterns", "expected_stage", "expected_uncertainties", "expected_missing_evidence"}
    assert all(required <= set(case) for case in CASES)


def test_reasoning_covers_expected_patterns_in_design_cases():
    for case in CASES:
        result = build_reasoning_result(_analysis(case["input_context"]))
        matched = {item["pattern_id"] for item in result["pattern_refs"]}
        assert set(case["expected_patterns"]) <= matched or case["expected_patterns"] == [], case["id"]


def test_low_roi_normal_video_has_uncertain_cause_and_candidate_strategy():
    result = build_reasoning_result(_analysis({"video_quality": "NORMAL", "roi_status": "LOW"}))
    assert "P001" in {item["pattern_id"] for item in result["pattern_refs"]}
    assert result["possible_causes"]
    assert all("cause" in item and "missing_evidence" in item for item in result["possible_causes"])
    assert result["candidate_strategies"]


def test_missing_target_roi_does_not_diagnose_roi_or_invent_number():
    result = build_reasoning_result(_analysis({"target_roi": None, "spend": 8, "orders": 3}))
    assert result["metric_diagnosis"]["roi_status"] == "MISSING"
    assert result["fact_summary"]["target_roi"] is None


def test_no_timeseries_does_not_match_saturation():
    result = build_reasoning_result(_analysis({"roi_status": "HIGH", "spend_pattern": "increase_then_flat"}))
    assert "P005" not in {item["pattern_id"] for item in result["pattern_refs"]}
    assert result["observation_plan"]["time_window"] is None


def test_rule_decision_and_state_are_not_changed_by_patterns():
    result = build_reasoning_result(_analysis({"decision": "CLOSE_REBUILD", "video_quality": "NORMAL", "roi_status": "LOW"}))
    assert result["fact_summary"]["decision"] == "CLOSE_REBUILD"
    assert result["fact_summary"]["state"] == "CLOSED_REBUILD"
    assert any(item["pattern_id"] == "P001" for item in result["pattern_refs"])


def test_candidate_strategies_are_not_actions_and_no_time_is_invented():
    result = build_reasoning_result(_analysis({"video_quality": "LOW"}))
    assert all("关闭广告" not in item["strategy"] and "修改预算" not in item["strategy"]
               for item in result["candidate_strategies"])
    assert result["observation_plan"]["time_window"] is None


def test_references_are_traceable_and_no_knowledge_is_not_fabricated():
    result = build_reasoning_result(_analysis({"video_quality": "NORMAL", "roi_status": "LOW"}))
    assert result["knowledge_refs"] == []
    assert "NO_KNOWLEDGE_EVIDENCE" in result["observation_plan"]["uncertainties"]
