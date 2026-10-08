from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text
from app.ai.text_parser import parse_operator_text
from app.db import Base


def _analyze(text: str, campaign_id: str):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            return analyze_text(db, campaign_id, text)
    finally:
        engine.dispose()


def test_case_1_multiline_empty_burn_has_rule_and_rebuild_candidate():
    result = _analyze("计划：\nA链接\n消耗:\n8 USD\n订单:\n0\n目标ROI:\n0.8", "case-1")
    assert result["current_analysis"]["spend"] == 8
    assert result["current_analysis"]["orders"] == 0
    assert result["current_analysis"]["current_roi"] is None
    assert result["decision"] == "EMPTY_BURN"
    assert result["state"] == "CLOSED_REBUILD"
    assert result["recommended_action"] == "CLOSE_REBUILD_KEEP_ROI"
    assert "S001" in result["strategy_refs"]
    assert "空烧" in result["diagnosis_result"]["problem_summary"]


def test_case_2_low_roi_with_normal_video_remains_human_decision():
    result = _analyze("计划:\nB链接\n消耗:\n100 USD\n订单:\n10\n收入:\n70 USD\nROI:\n0.7\n目标ROI:\n1.0\nCTR:\n3%\nCVR:\n11%\n完播率:\n40%", "case-2")
    assert result["roi_status"] == "BELOW_TARGET"
    assert result["video_status"] == "VIDEO_NORMAL"
    assert result["decision"] == "NEEDS_CONFIRMATION"
    assert "P001" in {item["pattern_id"] for item in result["reasoning_result"]["pattern_refs"]}
    assert "S003" in result["strategy_refs"]
    assert len(result["diagnosis_result"]["failure_hypotheses"]) == 3
    assert all(item["confidence"] == "LOW" for item in result["diagnosis_result"]["failure_hypotheses"])


def test_case_3_partial_video_metrics_support_candidate_not_roi_verdict():
    result = _analyze("消耗:\n50\n订单:\n2\nROI:\n0.3\nCTR:\n0.5%\n完播率:\n10%", "case-3")
    assert result["current_analysis"]["target_roi"] is None
    assert result["roi_status"] == "UNKNOWN"
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["diagnosis_result"]["judgment_candidate"] == "素材风险候选"
    assert "素材" in result["diagnosis_result"]["failure_hypotheses"][0]["cause"]
    assert "P002" in {item["pattern_id"] for item in result["reasoning_result"]["pattern_refs"]}
    assert any("测试新素材" in item["strategy"] for item in result["reasoning_result"]["candidate_strategies"])
    assert "S004" in result["strategy_refs"]


def test_case_4_first_day_is_observation_candidate_not_confirmed_scaling():
    result = _analyze("第一天:\n消耗:\n50\n订单:\n8\nROI:\n1.5\nCTR:\n4%\nCVR:\n8%", "case-4")
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["reasoning_result"]["campaign_stage"] == "TESTING"
    assert result["diagnosis_result"]["judgment_candidate"] == "首日起量观察候选"
    assert "不能判断已经进入扩量" in result["diagnosis_result"]["problem_summary"]
    assert any("增预算" in item["strategy"] and "确认新品" in item["strategy"]
               for item in result["reasoning_result"]["candidate_strategies"])


def test_case_5_two_dollars_zero_orders_stays_insufficient():
    result = _analyze("消耗:\n2\n订单:\n0", "case-5")
    assert result["decision"] == "INSUFFICIENT_DATA"
    assert result["diagnosis_result"]["judgment_candidate"] is None
    assert "EMPTY_BURN_USD_3" not in result["rules_used"]
    assert "S001" not in result["strategy_refs"]


def test_target_roi_alone_does_not_become_current_roi():
    for label in ("目标ROI", "目标 ROI"):
        parsed = parse_operator_text(f"计划：A链接\n{label}:\n0.8")
        assert parsed["target_roi"] == 0.8
        assert parsed["current_roi"] is None
