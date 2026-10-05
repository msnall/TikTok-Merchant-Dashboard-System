"""Database-backed Phase 3 acceptance smoke test; no chat context or live LLM."""

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app import ad_models, models, work_models  # register all metadata tables
from app.ai import models as ai_models
from app.ai.analysis_service import analyze_text, serialize_run
from app.db import Base
from app.db import get_db
from app.main import app


def test_phase3_stateful_end_to_end(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase3_e2e.db').as_posix()}")
    Base.metadata.create_all(engine)
    campaign_id = "phase3_e2e_campaign"
    first_text = "A\u8ba1\u5212\u6210\u672c8.6\u7f8e\u5143\uff0c3\u5355\uff0cROI0.71\uff0cCTR2.6%\uff0cCVR11.3%\uff0c\u5b8c\u64ad\u738736%."
    second_text = "A\u8ba1\u5212\u73b0\u5728\u6210\u672c11.4\u7f8e\u5143\uff0c5\u5355\uff0cROI0.86\uff0cCTR2.8%\uff0cCVR12%\uff0c\u5b8c\u64ad\u738737%."
    with Session(engine) as db:
        first = analyze_text(db, campaign_id, first_text)
        assert first["analysis_id"]
        # The supplied smoke text intentionally omits target ROI, so the
        # deterministic engine reports insufficient data rather than guessing.
        assert first["decision"] == "INSUFFICIENT_DATA"
        assert first["state"] == "ACTIONABLE"
        first_run = db.get(ai_models.AIAnalysisRun, first["analysis_id"])
        assert first_run.snapshot is not None
        assert first["observation_plan"] is None

        second = analyze_text(db, campaign_id, second_text)
        assert second["historical_comparison"]["previous_analysis_id"] == first["analysis_id"]
        assert second["historical_comparison"]["delta"] == {
            "delta_spend": 2.8, "delta_orders": 2, "delta_roi": 0.15,
            "delta_ctr": 0.002, "delta_cvr": 0.007, "delta_completion_rate": 0.01,
        }
        assert second["state"] == "ACTIONABLE"
        assert second["state_transition"]["from_state"] == "ACTIONABLE"
        assert second["state_transition"]["to_state"] == "ACTIONABLE"

        transitions = db.scalars(select(ai_models.AIStateTransition)
                                 .where(ai_models.AIStateTransition.campaign_id == campaign_id)
                                 .order_by(ai_models.AIStateTransition.id)).all()
        assert len(transitions) == 2
        assert transitions[-1].analysis_run_id == second["analysis_id"]
        assert transitions[-1].to_state == second["state"]

        # Human actions are append-only and independent of the AI recommendation.
        def session_override():
            with Session(engine) as session:
                yield session
        app.dependency_overrides[get_db] = session_override
        try:
            with TestClient(app) as client:
                accepted_response = client.post(
                    f"/api/ai/analyses/{second['analysis_id']}/actions",
                    json={"action_type": "ACCEPT", "actual_action": "按建议复核计划"})
                modified_response = client.post(
                    f"/api/ai/analyses/{second['analysis_id']}/actions",
                    json={"action_type": "MODIFY", "actual_action": "暂不调整，继续观察2小时"})
                assert accepted_response.status_code == 200
                assert modified_response.status_code == 200
                action_response = client.get(f"/api/ai/analyses/{second['analysis_id']}/actions")
                assert action_response.status_code == 200
                assert [item["action_type"] for item in action_response.json()["items"]] == ["ACCEPT", "MODIFY"]
        finally:
            app.dependency_overrides.pop(get_db, None)
        db.expire_all()
        actions = db.scalars(select(ai_models.DecisionAction)
                             .where(ai_models.DecisionAction.analysis_run_id == second["analysis_id"])
                             .order_by(ai_models.DecisionAction.id)).all()
        assert [item.action_type for item in actions] == ["ACCEPT", "MODIFY"]
        assert actions[1].actual_action != second["decision"]
        assert len(db.query(ai_models.AIAnalysisRun).all()) == 2
        assert len(db.query(ai_models.AIAnalysisSnapshot).all()) == 2
        assert serialize_run(first_run)["analysis_id"] == first["analysis_id"]
    engine.dispose()
