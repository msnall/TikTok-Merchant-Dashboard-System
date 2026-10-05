"""Phase 6.5 evaluates workflow coverage, not strategy effectiveness."""

from sqlalchemy.orm import Session

from app.ai.history import save_analysis
from app.ai.models import AIRecommendation
from app.db import get_db
from app.main import app
from test_phase6_2_models import _analysis, _client


def _post(client, path, payload):
    response = client.post(path, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_evaluation_empty_and_read_only(tmp_path):
    engine, client = _client(tmp_path)
    try:
        response = client.get("/api/ai/feedback/evaluation")
        assert response.status_code == 200
        data = response.json()
        assert data["unit"] == "recommendation_id"
        assert data["scope"] == "real_operator_case"
        assert all(item["count"] == 0 for item in data["funnel"].values())
        assert data["observed_changes"] == []
        assert data["causal_assessment"] == "UNKNOWN"
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_funnel_counts_distinct_recommendations_and_latest_records(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        analysis_id = _analysis(client)
        ids = [item["id"] for item in client.get(
            f"/api/ai/analyses/{analysis_id}/recommendations").json()]
        assert len(ids) >= 2
        first, second = ids[:2]
        _post(client, f"/api/ai/recommendations/{first}/feedback", {"feedback_type": "REJECT"})
        _post(client, f"/api/ai/recommendations/{first}/feedback", {"feedback_type": "ACCEPT"})
        _post(client, f"/api/ai/recommendations/{second}/feedback", {"feedback_type": "MODIFY"})
        _post(client, f"/api/ai/recommendations/{first}/execution", {
            "execution_status": "PENDING", "actual_action": "准备测试"})
        execution = _post(client, f"/api/ai/recommendations/{first}/execution", {
            "execution_status": "CONFIRMED", "actual_action": "已人工核验调整",
            "execution_source": "operator_verified", "evidence": "截图登记 12"})
        observation = _post(client, f"/api/ai/executions/{execution['id']}/observation", {
            "observation_window": {"start": "2026-10-05", "end": "2026-10-12",
                                   "source": "operator_input"},
            "data_source": "manual", "before_metrics": {"roi": 0.71, "orders": 3},
            "after_metrics": {"roi": 0.86, "orders": 8}})
        assert observation["causal_assessment"] == "UNKNOWN"
        before = client.get("/api/ai/feedback/evaluation").json()
        assert {key: value["count"] for key, value in before["funnel"].items()} == {
            "generated": len(ids), "feedback_received": 2, "accepted": 1,
            "confirmed_execution": 1, "with_observation": 1}
        assert before["funnel"]["accepted"]["denominator"] == 2
        assert before["funnel"]["confirmed_execution"]["denominator"] == 1
        assert before["execution_summary"]["CONFIRMED"] == 1
        assert before["execution_summary"]["PENDING"] == 0
        assert before["observation_summary"]["with_window"] == {"count": 1, "denominator": 1}
        assert before["observation_summary"]["with_paired_metrics"] == {"count": 1, "denominator": 1}
        assert before["data_completeness"]["HIGH"] == 1
        change = before["observed_changes"][0]
        assert change["recommendation_id"] == first
        assert change["observed_roi_change"] == 0.15
        assert change["causal_assessment"] == "UNKNOWN"
        assert client.get("/api/ai/feedback/evaluation").json() == before
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_synthetic_excluded_even_with_complete_loop(tmp_path):
    engine, client = _client(tmp_path)
    try:
        with Session(engine) as db:
            run = save_analysis(db,
                {"campaign_id": "synthetic-evaluation", "source_type": "synthetic_demo",
                 "spend": 8, "orders": 0}, None, {},
                {"source_type": "synthetic_demo", "campaign_id": "synthetic-evaluation",
                 "decision": "EMPTY_BURN", "rules_used": [], "facts": [],
                 "recommendations": ["CLOSE_REBUILD_KEEP_ROI"], "uncertainties": []},
                recommendation_snapshots=[{"strategy_id": "S001", "content": "模拟建议"}])
            recommendation_id = run.recommendation_records[0].id
        _post(client, f"/api/ai/recommendations/{recommendation_id}/feedback", {
            "feedback_type": "ACCEPT"})
        execution = _post(client, f"/api/ai/recommendations/{recommendation_id}/execution", {
            "execution_status": "CONFIRMED", "actual_action": "模拟执行",
            "execution_source": "operator_verified", "evidence": "模拟凭证"})
        _post(client, f"/api/ai/executions/{execution['id']}/observation", {
            "observation_window": {"value": 5, "unit": "days", "source": "operator_input"},
            "data_source": "manual", "before_metrics": {"roi": 0.7},
            "after_metrics": {"roi": 1.0}})
        assert client.get("/api/ai/feedback/evaluation").json()["funnel"]["generated"]["count"] == 0
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()


def test_observation_completeness_requires_window_and_paired_metrics(tmp_path, monkeypatch):
    for key in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(key, raising=False)
    engine, client = _client(tmp_path)
    try:
        recommendation_id = client.get(
            f"/api/ai/analyses/{_analysis(client)}/recommendations").json()[0]["id"]
        _post(client, f"/api/ai/recommendations/{recommendation_id}/feedback", {
            "feedback_type": "ACCEPT"})
        execution = _post(client, f"/api/ai/recommendations/{recommendation_id}/execution", {
            "execution_status": "CONFIRMED", "actual_action": "已人工核验",
            "execution_source": "operator_verified", "evidence": "登记号 8"})
        _post(client, f"/api/ai/executions/{execution['id']}/observation", {
            "observation_window": {"source": "UNKNOWN"}, "data_source": "manual",
            "before_metrics": {"roi": 0.7}, "after_metrics": {"orders": 8}})
        data = client.get("/api/ai/feedback/evaluation").json()
        assert data["funnel"]["with_observation"]["count"] == 1
        assert data["observation_summary"]["with_window"]["count"] == 0
        assert data["observation_summary"]["with_paired_metrics"]["count"] == 0
        assert data["data_completeness"]["MEDIUM"] == 1
        assert data["observed_changes"] == []
    finally:
        app.dependency_overrides.pop(get_db, None)
        client.close()
        engine.dispose()
