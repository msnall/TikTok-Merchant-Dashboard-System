"""Execution and observation are recorded separately from operator feedback."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai.models import AIExecutionRecord, AIOutcomeObservation, AIRecommendationFeedback
from app.db import get_db
from app.main import app
from test_phase6_2_models import _analysis, _client


def test_feedback_does_not_create_execution(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        recommendation = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]
        response = client.post(f"/api/ai/recommendations/{recommendation['id']}/feedback", json={
            "feedback_type": "ACCEPT", "operator_note": "考虑测试，但尚未执行"})
        assert response.status_code == 201
        latest = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]
        assert latest["status"] == "ACCEPTED"
        assert latest["execution_status"] == "UNKNOWN"
        assert latest["execution"] is None
        assert latest["observations"] == []
        with Session(engine) as db:
            assert db.query(AIRecommendationFeedback).count() == 1
            assert db.query(AIExecutionRecord).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_confirmed_execution_and_observations_survive_reload(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        recommendation = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]
        recommendation_id = recommendation["id"]
        client.post(f"/api/ai/recommendations/{recommendation_id}/feedback", json={
            "feedback_type": "ACCEPT"})
        response = client.post(f"/api/ai/recommendations/{recommendation_id}/execution", json={
            "execution_status": "CONFIRMED", "actual_action": "人工核验已调整计划",
            "execution_source": "operator_verified", "evidence": "操作截图登记号 42",
            "executed_at": "2026-10-05T10:00:00"})
        assert response.status_code == 201, response.text
        execution_id = response.json()["id"]
        assert response.json()["executed_at"].startswith("2026-10-05")
        for window in ((5, "days"), (2, "hours")):
            observation = client.post(f"/api/ai/executions/{execution_id}/observation", json={
                "observation_window": {"value": window[0], "unit": window[1], "source": "operator_input"},
                "data_source": "manual", "before_metrics": {"roi": 0.7},
                "after_metrics": {"roi": 1.0}})
            assert observation.status_code == 201, observation.text
            assert observation.json()["causal_assessment"] == "UNKNOWN"
        dated = client.post(f"/api/ai/executions/{execution_id}/observation", json={
            "observation_window": {"start": "2026-10-05", "end": "2026-10-12", "source": "operator_input"},
            "data_source": "manual", "before_metrics": {"roi": 0.7},
            "after_metrics": {"roi": 1.0}})
        assert dated.status_code == 201
        assert dated.json()["observation_window"]["start"] == "2026-10-05"
        assert client.post(f"/api/ai/executions/{execution_id}/observation", json={
            "observation_window": {"start": "2026-10-12", "end": "2026-10-05", "source": "operator_input"},
            "data_source": "manual"}).status_code == 422
        latest = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]
        assert latest["execution_status"] == "CONFIRMED"
        assert latest["execution"]["id"] == execution_id
        assert latest["execution"]["execution_source"] == "operator_verified"
        assert [item["observation_window"]["unit"] for item in latest["observations"]] == ["days", "hours", None]
        assert all(item["causal_assessment"] == "UNKNOWN" for item in latest["observations"])
        next_record = client.post(f"/api/ai/recommendations/{recommendation_id}/execution", json={
            "execution_status": "PENDING", "actual_action": "计划复核执行效果",
            "execution_source": "operator_input"})
        assert next_record.status_code == 201
        reloaded = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]
        assert reloaded["execution"]["id"] == next_record.json()["id"]
        assert reloaded["observations"] == []
        assert reloaded["execution_history"][1]["id"] == execution_id
        assert len(reloaded["execution_history"][1]["observations"]) == 3
        with Session(engine) as db:
            assert db.scalars(select(AIExecutionRecord)).first().recommendation_id == recommendation_id
            assert db.query(AIOutcomeObservation).count() == 3
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()
