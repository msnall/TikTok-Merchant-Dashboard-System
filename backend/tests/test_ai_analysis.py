from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient
import json
from pathlib import Path
import pytest

from app.db import Base
from app import models, ad_models, work_models
from app.ai.models import AIAnalysisRun
from app.ai.analysis_service import analyze_text, serialize_run
from app.ai.text_parser import parse_operator_text
from app.db import get_db
from app.main import app

EVALUATION_CASES = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "ai_analysis_cases.json").read_text(encoding="utf-8"))


def test_text_parser_keeps_missing_fields_null():
    data = parse_operator_text("A计划，成本3.5刀，0订单。", "phase2")
    assert data["spend"] == 3.5 and data["orders"] == 0
    assert data["target_roi"] is None and data["official_completion_rate"] is None
    assert data["roi_policy"] == "break_even"
    assert parse_operator_text("A计划目标ROI 0.82")["current_roi"] is None


def test_append_only_analysis_and_delta(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase2.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        first = analyze_text(db, "phase2", "A计划，成本8.6刀，3单，当前ROI 0.71，目标ROI 0.82，CTR 2.6%，CVR 11.3%，官方完播率36%。")
        second = analyze_text(db, "phase2", "A计划，成本11.4刀，5单，当前ROI 0.86，目标ROI 0.82，CTR 2.8%，CVR 11.5%，官方完播率37%。")
        third = analyze_text(db, "phase2", "A计划，成本12刀，5单，当前ROI 0.86，目标ROI 0.82。")
        assert first["analysis_id"] < second["analysis_id"] < third["analysis_id"]
        assert second["historical_comparison"]["delta"]["delta_spend"] == 2.8
        assert second["historical_comparison"]["delta"]["delta_orders"] == 2
        assert second["historical_comparison"]["delta"]["delta_roi"] == 0.15
        assert second["historical_comparison"]["delta"]["delta_ctr"] == 0.002
        assert third["video_status"] == "UNKNOWN"
        assert len(db.query(AIAnalysisRun).all()) == 3
        saved = serialize_run(db.get(AIAnalysisRun, first["analysis_id"]))
        assert saved["raw_input_text"].startswith("A计划")
        assert saved["current_analysis"]["campaign_id"] == "phase2"
        assert saved["knowledge_refs"]


def test_empty_burn_and_no_saturation_without_timeseries(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase2_rules.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        burn = analyze_text(db, "burn", "A计划，成本3.5刀，0订单。")
        assert burn["decision"] == "EMPTY_BURN"
        assert burn["recommendations"] == ["CLOSE_REBUILD_KEEP_ROI"]
        flat = analyze_text(db, "flat", "前面花得很快，后面基本不花了。")
        assert flat["decision"] == "INSUFFICIENT_DATA"
        assert any("时序" in item for item in flat["uncertainties"])


def test_analysis_api_history_and_latest(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase2_api.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    def session_override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = session_override
    try:
        with TestClient(app) as client:
            payload = {"campaign_id": "api-1", "text": "A计划，成本3.5刀，0订单。"}
            first = client.post("/api/ai/analyses", json=payload)
            assert first.status_code == 200, first.text
            body = first.json()
            assert body["decision"] == "EMPTY_BURN"
            analysis_id = body["analysis_id"]
            assert client.get(f"/api/ai/analyses/{analysis_id}").json()["raw_input_text"] == payload["text"]
            assert client.get("/api/ai/campaigns/api-1/latest").json()["analysis_id"] == analysis_id
            assert len(client.get("/api/ai/campaigns/api-1/history").json()["items"]) == 1
            assert client.get("/api/ai/analyses/99999").status_code == 404
            assert client.post("/api/ai/analyses", json={"campaign_id": "", "text": ""}).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.mark.parametrize("case", EVALUATION_CASES, ids=lambda case: case["id"])
def test_natural_language_evaluation(case):
    data = parse_operator_text(case["text"], case["id"])
    assert data["spend"] == case["spend"]
    assert data["orders"] == case["orders"]
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = analyze_text(db, case["id"], case["text"])
    assert result["decision"] == case["decision"]
    if case["decision"] == "WAIT_OBSERVE":
        assert "先放着不动" in result["next_observation"]


def test_fake_llm_cannot_override_rules_or_invent_number(tmp_path, monkeypatch):
    class FakeLLM:
        def extract(self, text): return {"spend": 999, "orders": 0}
        def explain(self, evidence): return {"summary": "请人工确认。", "diagnosis": ["需要复核视频指标"],
            "recommendations": ["已关停广告", "建议人工检查"], "next_observation": [], "uncertainties": []}
    monkeypatch.setenv("LLM_API_KEY", "test-only")
    monkeypatch.setenv("LLM_BASE_URL", "http://invalid.local/v1")
    monkeypatch.setenv("LLM_MODEL", "fake")
    monkeypatch.setattr("app.ai.analysis_service.LLMClient", lambda: FakeLLM())
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase2_fake_llm.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = analyze_text(db, "fake", "A计划，成本3.5刀，0订单。")
    assert result["current_analysis"]["spend"] == 3.5
    assert result["decision"] == "EMPTY_BURN"
    assert result["summary"] == "请人工确认。"
    assert result["explanation"]["recommendations"] == ["建议人工检查"]
