from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text
from app.ai.explanation import build_operation_report
from app.db import Base


def _analyze(tmp_path, text, campaign_id="explain-case"):
    engine = create_engine(f"sqlite:///{(tmp_path / f'{campaign_id}.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = analyze_text(db, campaign_id, text)
    engine.dispose()
    return result


def test_empty_burn_has_complete_fallback_report(tmp_path):
    result = _analyze(tmp_path, "A计划成本3.5美元，一单没有。", "empty-burn")
    report = result["operation_report"]
    assert result["decision"] == "EMPTY_BURN"
    assert report["decision"] == "EMPTY_BURN"
    assert report["state"] == result["state"]
    assert report["recommended_actions"]
    assert report["mode"] == "template_fallback"


def test_low_roi_normal_video_report_keeps_uncertain_causes(tmp_path):
    result = _analyze(tmp_path, "A*9.10产品0.82，成本8.6美元，3单，ROI0.71，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "low-roi")
    report = result["operation_report"]
    assert result["decision"] == "NEEDS_CONFIRMATION"
    assert report["roi_problem_judgment"].startswith("当前 ROI 低于目标 ROI")
    assert report["possible_causes"]
    assert report["next_observation_metrics"]


def test_poor_video_report_mentions_video_quality(tmp_path):
    result = _analyze(tmp_path, "A*9.10产品0.82，成本8美元，3单，ROI0.5，目标ROI0.82，CTR1%，CVR5%，完播率20%。", "poor-video")
    assert result["decision"] == "CLOSE_REBUILD"
    assert "未达到" in result["operation_report"]["video_quality_judgment"]


def test_new_product_report_does_not_claim_execution(tmp_path):
    result = _analyze(tmp_path, "新品A*9.10产品0.82，成本8美元，3单，ROI0.82，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "new-product")
    report = result["operation_report"]
    assert all("已关闭" not in item and "已修改预算" not in item for item in report["recommended_actions"])


def test_wait_observe_report_has_next_metrics_and_no_invented_time(tmp_path):
    result = _analyze(tmp_path, "A*9.10产品0.82，成本8美元，3单，ROI0.82，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。", "wait")
    assert result["decision"] == "WAIT_OBSERVE"
    assert result["operation_report"]["next_observation_metrics"]
    assert result["reasoning_result"]["observation_plan"]["time_window"] is None


def test_missing_target_roi_is_explicitly_uncertain(tmp_path):
    result = _analyze(tmp_path, "A计划成本8美元，3单，ROI0.71，CTR2.6%，CVR11.3%，完播率36%。", "missing-target")
    report = result["operation_report"]
    assert "缺少目标 ROI" in report["roi_problem_judgment"]
    assert result["reasoning_result"]["metric_diagnosis"]["roi_status"] == "MISSING"


def test_llm_prose_cannot_change_deterministic_fields():
    reasoning = {"campaign_stage": "TESTING", "fact_summary": {"decision": "WAIT_OBSERVE", "state": "WAIT_OBSERVE", "spend": 8, "orders": 3},
                 "metric_diagnosis": {"video_quality": "NORMAL", "roi_status": "NORMAL"},
                 "possible_causes": [], "candidate_strategies": [{"strategy": "建议继续观察", "reason": "指标接近目标", "risk": "时间窗口待确认"}],
                 "observation_plan": {"metrics_to_compare": ["ROI"], "time_window": None, "uncertainties": []},
                 "pattern_refs": [], "knowledge_refs": []}
    report = build_operation_report(reasoning, decision="WAIT_OBSERVE", state="WAIT_OBSERVE",
                                    llm_explanation={"summary": "已经关闭广告"})
    assert report["decision"] == "WAIT_OBSERVE"
    assert report["state"] == "WAIT_OBSERVE"
    assert report["llm_summary"] == "已经关闭广告"
