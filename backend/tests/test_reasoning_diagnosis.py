from copy import deepcopy

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text, serialize_run
from app.ai.models import AIAnalysisRun
from app.ai.reasoning.diagnosis import build_diagnosis_result
from app.db import Base


def _result(facts=None, statuses=None, decision="NEEDS_CONFIRMATION"):
    reasoning = {"fact_summary": facts or {}, "metric_diagnosis": statuses or {}}
    rule = {"decision": decision, "historical_comparison": {"previous_analysis_id": None}}
    return reasoning, rule


def test_empty_burn_explains_trigger_without_asserting_cause():
    reasoning, rule = _result({"spend": 3.5, "orders": 0}, decision="EMPTY_BURN")
    rule["facts"] = [{"field": "currency", "value": "USD"}]
    before = deepcopy((reasoning, rule))
    result = build_diagnosis_result(reasoning, rule)
    assert "空烧" in result["problem_summary"]
    assert "已消耗 3.5 USD" in result["confirmed_facts"]
    assert len(result["failure_hypotheses"]) == 3
    assert all(item["cause"].startswith("可能") and item["missing_evidence"]
               for item in result["failure_hypotheses"])
    assert (reasoning, rule) == before
    assert rule["decision"] == "EMPTY_BURN"


def test_low_roi_normal_video_keeps_causes_uncertain():
    reasoning, rule = _result({"current_roi": 0.71, "target_roi": 0.82},
                              {"roi_status": "LOW", "video_quality": "NORMAL"})
    result = build_diagnosis_result(reasoning, rule)
    assert "视频指标未显示明显异常" in result["problem_summary"]
    assert len(result["failure_hypotheses"]) == 3
    assert all(item["confidence"] == "LOW" for item in result["failure_hypotheses"])


@pytest.mark.parametrize(("metric", "value", "summary"), [
    ("ctr_status", "ctr", "点击意愿"),
    ("cvr_status", "cvr", "点击后转化"),
])
def test_low_click_or_conversion_metric(metric, value, summary):
    reasoning, rule = _result({value: 0.01}, {metric: "LOW"})
    result = build_diagnosis_result(reasoning, rule)
    assert summary in result["problem_summary"]
    assert result["failure_hypotheses"]
    assert all("趋势" in str(item["missing_evidence"]) or item["missing_evidence"]
               for item in result["failure_hypotheses"])


def test_missing_data_never_invents_facts_or_hypotheses():
    reasoning, rule = _result()
    result = build_diagnosis_result(reasoning, rule)
    assert result["confirmed_facts"] == []
    assert result["failure_hypotheses"] == []
    assert any("目标 ROI" in item for item in result["diagnostic_limitations"])
    assert any("视频指标" in item for item in result["diagnostic_limitations"])


def test_conflicting_metric_status_without_value_does_not_invent_number():
    reasoning, rule = _result({}, {"ctr_status": "LOW", "roi_status": "LOW", "video_quality": "NORMAL"})
    result = build_diagnosis_result(reasoning, rule)
    assert result["confirmed_facts"] == []
    assert result["failure_hypotheses"] == []
    assert "证据不足" in result["problem_summary"]


def test_api_analysis_saves_diagnosis_without_overriding_decision(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'diagnosis.db').as_posix()}")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as db:
            result = analyze_text(db, "diagnosis-e2e", "A计划，成本3.5美元，一单没有。")
            saved = serialize_run(db.get(AIAnalysisRun, result["analysis_id"]))
            assert result["decision"] == saved["decision"] == "EMPTY_BURN"
            assert saved["diagnosis_result"] == result["diagnosis_result"]
            assert saved["reasoning_result"] == result["reasoning_result"]
    finally:
        engine.dispose()
