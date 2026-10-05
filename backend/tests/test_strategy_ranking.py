from app.ai.strategy_ranking import rank_operator_strategies


def _input(refs, decision="NEEDS_CONFIRMATION"):
    return {"strategy_refs": refs, "decision": decision,
            "current_analysis": {"currency": "USD"},
            "reasoning_result": {"fact_summary": {"decision": decision},
                                 "metric_diagnosis": {"video_quality": "NORMAL", "roi_status": "LOW"}}}


def test_empty_burn_has_highest_priority():
    result = rank_operator_strategies(_input(["S001", "S002", "S003", "S007"]))
    assert result["primary_strategy"] == "S001"
    assert result["secondary_strategies"] == ["S003", "S007", "S002"]
    assert "强确定" in result["ranking_reason"]


def test_poor_video_precedes_roi_strategy():
    result = rank_operator_strategies(_input(["S003", "S004", "S006"]))
    assert result["primary_strategy"] == "S004"
    assert result["secondary_strategies"] == ["S003", "S006"]
    assert "视频质量差" in result["ranking_reason"]


def test_multiple_strategies_are_ranked_deterministically():
    first = rank_operator_strategies(_input(["S007", "S005", "S002", "S006"]))
    second = rank_operator_strategies(_input(["S002", "S006", "S005", "S007"]))
    assert first == second
    assert first["primary_strategy"] == "S006"


def test_unmatched_strategies_are_rejected_with_reasons():
    result = rank_operator_strategies(_input(["S003"]))
    rejected = {item["strategy_id"]: item["reason"] for item in result["rejected_strategies"]}
    assert "S001" in rejected and rejected["S001"]
    assert "S004" in rejected


def test_ranking_does_not_modify_decision():
    source = _input(["S001", "S003"], decision="EMPTY_BURN")
    result = rank_operator_strategies(source)
    assert source["decision"] == "EMPTY_BURN"
    assert result["primary_strategy"] == "S001"
