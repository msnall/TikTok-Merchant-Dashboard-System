"""Phase 6.2 keeps recommendation, feedback, execution and outcome separate."""

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, select
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text
from app.ai.history import save_analysis
from app.ai.models import (AIAnalysisRun, AIExecutionRecord, AIOutcomeObservation,
                           AIRecommendation, AIRecommendationFeedback, DecisionAction)
from app.db import Base, get_db
from app.main import app


def _client(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'feedback_loop.db').as_posix()}",
                           connect_args={"check_same_thread": False})

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(engine)

    def session_override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = session_override
    return engine, TestClient(app)


def _analysis(client):
    response = client.post("/api/ai/analyses", json={
        "campaign_id": "phase6-real",
        "text": "A*9.10产品0.82，成本8美元，3单，ROI0.71，目标ROI0.82，CTR2.6%，CVR11.3%，完播率36%。",
    })
    assert response.status_code == 200, response.text
    return response.json()["analysis_id"]


def test_recommendations_are_distinct_immutable_snapshots(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        response = client.get(f"/api/ai/analyses/{analysis_id}/recommendations")
        assert response.status_code == 200
        items = response.json()
        assert len(items) >= 2
        assert len({item["id"] for item in items}) == len(items)
        assert {item["strategy_id"] for item in items} >= {"S002", "S003"}
        assert all(item["analysis_id"] == analysis_id and item["case_source"] == "real_operator_case" for item in items)
        assert all(item["status"] == "UNREVIEWED" and item["execution_status"] == "UNKNOWN" for item in items)
        assert all("execution_status" not in item["reasoning_snapshot"] for item in items)
        with Session(engine) as db:
            assert db.query(AIAnalysisRun).count() == 1
            assert db.query(AIRecommendation).count() == len(items)
            assert db.query(AIExecutionRecord).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_accept_and_action_text_do_not_confirm_execution(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        recommendations = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()
        selected = recommendations[0]["id"]
        feedback = client.post(f"/api/ai/recommendations/{selected}/feedback", json={
            "feedback_type": "ACCEPT", "operator_note": "准备调整 ROI",
        })
        assert feedback.status_code == 201
        assert feedback.json()["recommendation_id"] == selected
        assert feedback.json()["execution_status"] == "UNKNOWN"
        listed = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()
        assert next(item for item in listed if item["id"] == selected)["status"] == "ACCEPTED"
        assert next(item for item in listed if item["id"] == selected)["execution_status"] == "UNKNOWN"
        assert all(item["status"] == "UNREVIEWED" for item in listed if item["id"] != selected)
        assert client.post(f"/api/ai/recommendations/{selected}/execution", json={
            "actual_action": "调整 ROI 到 0.9",
        }).json()["execution_status"] == "UNKNOWN"
        with Session(engine) as db:
            assert db.query(AIRecommendationFeedback).count() == 1
            assert db.query(AIExecutionRecord).count() == 1
            assert db.scalars(select(AIExecutionRecord)).first().executed_at is None
        assert client.post("/api/ai/recommendations/99999/feedback", json={
            "feedback_type": "ACCEPT"}).status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_legacy_analysis_has_no_assignable_recommendation(tmp_path):
    engine, client = _client(tmp_path)
    try:
        with Session(engine) as db:
            run = save_analysis(
                db, {"campaign_id": "legacy", "source_type": "manual_entry"}, None, {},
                {"source_type": "manual_entry", "campaign_id": "legacy",
                 "decision": "INSUFFICIENT_DATA", "rules_used": [], "facts": [],
                 "recommendations": [], "uncertainties": []},
            )
            analysis_id = run.id
        response = client.get(f"/api/ai/analyses/{analysis_id}/recommendations")
        assert response.status_code == 200
        assert response.json() == []
        assert client.post("/api/ai/recommendations/99999/feedback", json={
            "feedback_type": "ACCEPT", "operator_note": "旧分析反馈"}).status_code == 404
        with Session(engine) as db:
            assert db.query(AIRecommendationFeedback).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_note_claiming_roi_change_does_not_create_execution(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        recommendation_id = client.get(
            f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]["id"]
        response = client.post(f"/api/ai/recommendations/{recommendation_id}/feedback", json={
            "feedback_type": "ACCEPT", "operator_note": "已修改 ROI 到 0.9"})
        assert response.status_code == 201
        assert response.json()["execution_status"] == "UNKNOWN"
        with Session(engine) as db:
            assert db.query(AIRecommendationFeedback).count() == 1
            assert db.query(AIExecutionRecord).count() == 0
            assert db.query(DecisionAction).count() == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_confirm_requires_source_and_evidence(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        selected = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]["id"]
        base = {"execution_status": "CONFIRMED", "actual_action": "重建计划"}
        assert client.post(f"/api/ai/recommendations/{selected}/execution", json=base).status_code == 422
        assert client.post(f"/api/ai/recommendations/{selected}/execution", json={
            **base, "execution_source": "operator_input", "evidence": "我准备执行",
        }).status_code == 422
        assert client.post(f"/api/ai/recommendations/{selected}/execution", json={
            **base, "execution_source": "operator_verified",
        }).status_code == 422
        confirmed = client.post(f"/api/ai/recommendations/{selected}/execution", json={
            **base, "execution_source": "operator_verified", "evidence": "运营人工核验记录 #1",
        })
        assert confirmed.status_code == 201, confirmed.text
        assert confirmed.json()["execution_status"] == "CONFIRMED"
        assert client.post(f"/api/ai/recommendations/{selected}/execution", json={
            "execution_status": "FAILED", "actual_action": "尝试重建",
        }).status_code == 422
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_observation_windows_and_roi_gain_do_not_claim_causality(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        selected = client.get(f"/api/ai/analyses/{analysis_id}/recommendations").json()[0]["id"]
        execution = client.post(f"/api/ai/recommendations/{selected}/execution", json={
            "actual_action": "准备测试新计划"}).json()
        for value, unit in ((5, "days"), (2, "hours")):
            payload = {"observation_window": {"value": value, "unit": unit, "source": "operator_input"},
                       "data_source": "manual", "before_metrics": {"roi": 0.8},
                       "after_metrics": {"roi": 1.1}}
            response = client.post(f"/api/ai/executions/{execution['id']}/observation", json=payload)
            assert response.status_code == 201, response.text
            assert response.json()["observation_window"]["value"] == value
            assert response.json()["causal_assessment"] == "UNKNOWN"
            assert response.json()["validation_status"] == "UNVERIFIED"
            assert client.post(f"/api/ai/executions/{execution['id']}/observation", json={
                **payload, "causal_assessment": "SUPPORTED"}).status_code == 422
        with Session(engine) as db:
            assert db.query(AIOutcomeObservation).count() == 2
            assert all(item.causal_assessment == "UNKNOWN" for item in db.scalars(select(AIOutcomeObservation)))
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_synthetic_records_keep_source_and_leave_real_stats(tmp_path):
    engine, client = _client(tmp_path)
    try:
        with Session(engine) as db:
            run = save_analysis(
                db,
                {"campaign_id": "synthetic-6", "source_type": "synthetic_demo", "spend": 4, "orders": 0},
                None, {},
                {"source_type": "synthetic_demo", "campaign_id": "synthetic-6",
                 "decision": "EMPTY_BURN", "rules_used": [], "facts": [],
                 "recommendations": ["CLOSE_REBUILD_KEEP_ROI"], "uncertainties": []},
                recommendation_snapshots=[{"strategy_id": "S001", "content": "候选：人工评估重建"}],
            )
            recommendation_id = run.recommendation_records[0].id
            db.add(DecisionAction(analysis_run_id=run.id, action_type="ACCEPT",
                                  actual_action="仅测试反馈统计"))
            db.commit()
        feedback = client.post(f"/api/ai/recommendations/{recommendation_id}/feedback", json={
            "feedback_type": "ACCEPT"})
        assert feedback.json()["case_source"] == "synthetic_demo"
        execution = client.post(f"/api/ai/recommendations/{recommendation_id}/execution", json={
            "actual_action": "模拟动作"})
        assert execution.json()["case_source"] == "synthetic_demo"
        observation = client.post(f"/api/ai/executions/{execution.json()['id']}/observation", json={
            "observation_window": {"source": "UNKNOWN"}, "data_source": "manual",
            "before_metrics": {}, "after_metrics": {}})
        assert observation.json()["case_source"] == "synthetic_demo"
        assert client.get("/api/ai/feedback/stats").json()["total"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()
