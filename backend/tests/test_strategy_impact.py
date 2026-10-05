from copy import deepcopy

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import serialize_run
from app.ai.models import AIAnalysisRun
from app.ai.strategy_impact import analyze_strategy_impact
from app.db import Base, get_db
from app.main import app


@pytest.mark.parametrize("strategy_id", [f"S{number:03d}" for number in range(1, 8)])
def test_each_strategy_has_conditional_impact_with_risk_and_monitoring(strategy_id):
    reasoning = {"fact_summary": {"decision": "WAIT_OBSERVE", "state": "WAIT_OBSERVE"},
                 "metric_diagnosis": {"roi_status": "UNKNOWN", "video_quality": "UNKNOWN"}}
    original = deepcopy(reasoning)

    impact = analyze_strategy_impact(strategy_id, reasoning, "WAIT_OBSERVE")

    assert impact["strategy_id"] == strategy_id
    assert impact["expected_benefits"]
    assert impact["potential_risks"]
    assert impact["monitor_metrics"]
    assert impact["failure_conditions"]
    assert impact["confidence"] in {"LOW", "MEDIUM", "HIGH"}
    assert all("可能" in benefit or "未必" in benefit for benefit in impact["expected_benefits"])
    assert reasoning == original
    assert "decision" not in impact and "state" not in impact


def test_confidence_only_rises_when_strategy_evidence_matches():
    poor_video = {"fact_summary": {},
                  "metric_diagnosis": {"roi_status": "LOW", "video_quality": "LOW"}}
    normal_video = {"fact_summary": {},
                    "metric_diagnosis": {"roi_status": "LOW", "video_quality": "NORMAL"}}
    assert analyze_strategy_impact("S004", poor_video, None)["confidence"] == "MEDIUM"
    assert analyze_strategy_impact("S004", normal_video, None)["confidence"] == "LOW"
    assert analyze_strategy_impact("S001", {"fact_summary": {"spend": 2, "orders": 0}}, None)["confidence"] == "LOW"
    assert analyze_strategy_impact("S001", {"fact_summary": {"spend": 3.5, "orders": 0}}, None)["confidence"] == "MEDIUM"


def test_no_primary_strategy_has_no_impact():
    assert analyze_strategy_impact(None, {}, None) is None


def test_unknown_strategy_is_rejected():
    with pytest.raises(ValueError, match="Unknown strategy"):
        analyze_strategy_impact("S999", {}, None)


def test_analysis_api_persists_impact_without_changing_decision(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'impact_api.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def test_session():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = test_session
    try:
        with TestClient(app) as client:
            response = client.post("/api/ai/analyses", json={
                "campaign_id": "impact-test",
                "text": "A计划，成本3.5美元，一单没有。",
            })
            assert response.status_code == 200, response.text
            result = response.json()
            assert result["decision"] == "EMPTY_BURN"
            assert result["strategy_ranking"]["primary_strategy"] == "S001"
            assert result["strategy_impact"]["strategy_id"] == "S001"
            assert result["strategy_impact"]["potential_risks"]

            detail = client.get(f"/api/ai/analyses/{result['analysis_id']}")
            assert detail.status_code == 200
            assert detail.json()["strategy_impact"] == result["strategy_impact"]
            with Session(engine) as db:
                saved = serialize_run(db.get(AIAnalysisRun, result["analysis_id"]))
                assert saved["decision"] == "EMPTY_BURN"
                assert saved["strategy_impact"] == result["strategy_impact"]
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()
