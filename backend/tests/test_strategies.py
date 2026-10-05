from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text
from app.ai.strategies import match_operator_strategies
from app.db import Base


def _analyze(tmp_path, text, campaign_id):
    engine = create_engine(f"sqlite:///{(tmp_path / f'{campaign_id}.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = analyze_text(db, campaign_id, text)
    engine.dispose()
    return result


def test_empty_burn_strategy_matches_without_changing_rule(tmp_path):
    result = _analyze(tmp_path, "A计划成本3.5美元，一单没有。", "s001")
    assert result["decision"] == "EMPTY_BURN"
    assert "S001" in result["strategy_refs"]
    assert any("候选" in action for action in result["strategy_candidate_actions"])


def test_few_orders_strategy_matches(tmp_path):
    result = _analyze(tmp_path, "A*9.10产品0.82，成本8美元，3单，ROI0.71，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "s002")
    assert "S002" in result["strategy_refs"]


def test_new_product_scaling_strategy_matches(tmp_path):
    result = _analyze(tmp_path, "新品A*9.10产品0.82，成本8美元，3单，ROI0.82，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "s005")
    # Text-only input does not claim the deterministic scaling confirmations;
    # strategy matcher must not infer them from the word 新品 alone.
    assert "S005" not in result["strategy_refs"]


def test_multiple_strategies_match_together(tmp_path):
    result = _analyze(tmp_path, "A*9.10产品0.82，成本8美元，3单，ROI0.71，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "s-multi")
    assert {"S002", "S003", "S006", "S007"} <= set(result["strategy_refs"])


def test_strategies_cannot_override_decision():
    reasoning = {"fact_summary": {"spend": 8, "orders": 3, "current_roi": 0.71, "target_roi": 0.82,
                                   "decision": "NEEDS_CONFIRMATION", "state": "NEEDS_CONFIRMATION"},
                 "metric_diagnosis": {"video_quality": "NORMAL", "roi_status": "LOW"}}
    result = match_operator_strategies({"current_analysis": reasoning["fact_summary"],
                                        "reasoning_result": reasoning,
                                        "decision": "NEEDS_CONFIRMATION"})
    assert result["strategy_refs"]
    assert reasoning["fact_summary"]["decision"] == "NEEDS_CONFIRMATION"
    assert all("关闭广告" not in action for action in result["candidate_actions"])
