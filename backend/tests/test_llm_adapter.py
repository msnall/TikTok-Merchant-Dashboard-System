import json
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app import models, ad_models, work_models
from app.ai import models as ai_models
from app.ai.analysis_service import analyze_text, serialize_run
from app.ai.llm import FIELDS, LLMClient


CASES = json.loads((Path(__file__).parent / "fixtures" / "phase2_live_llm_cases.json")
                   .read_text(encoding="utf-8"))


def test_extraction_rejects_missing_fields_and_invalid_types(monkeypatch):
    client = object.__new__(LLMClient)
    valid = dict.fromkeys(FIELDS)
    valid.update(link_type="A", spend=3.5, orders=0)
    monkeypatch.setattr(client, "_json", lambda *_: valid)
    assert client.extract("A计划花了3.5美元，一单没有") == valid
    monkeypatch.setattr(client, "_json", lambda *_: {"spend": 3.5})
    with pytest.raises(ValueError, match="字段"):
        client.extract("成本3.5")
    monkeypatch.setattr(client, "_json", lambda *_: {**valid, "orders": "0"})
    with pytest.raises(ValueError, match="类型"):
        client.extract("一单没有")


def test_explanation_rejects_schema_mismatch(monkeypatch):
    client = object.__new__(LLMClient)
    monkeypatch.setattr(client, "_json", lambda *_: {"summary": "建议观察"})
    with pytest.raises(ValueError, match="结构"):
        client.explain({"rule_result": {"decision": "WAIT_OBSERVE"}})


@pytest.mark.parametrize("failure_stage,expected_status", [
    ("extract", "llm_error"), ("explain", "fallback_explanation"),
])
def test_llm_failure_keeps_rule_decision_and_persists_status(tmp_path, monkeypatch,
                                                               failure_stage, expected_status):
    class FailingLLM:
        model = "offline-test-model"

        def extract(self, text):
            if failure_stage == "extract":
                raise TimeoutError("offline simulated timeout")
            return dict.fromkeys(FIELDS)

        def explain(self, evidence):
            raise ValueError("offline simulated malformed JSON")

    monkeypatch.setenv("LLM_API_KEY", "offline-test-key")
    monkeypatch.setenv("LLM_BASE_URL", "http://invalid.local/v1")
    monkeypatch.setenv("LLM_MODEL", "offline-test-model")
    monkeypatch.setattr("app.ai.analysis_service.LLMClient", FailingLLM)
    engine = create_engine(f"sqlite:///{(tmp_path / 'fallback.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        result = analyze_text(db, "demo_fallback", "A计划，成本3.5美元，一单没有。")
        saved = serialize_run(db.get(ai_models.AIAnalysisRun, result["analysis_id"]))
        assert result["decision"] == saved["decision"] == "EMPTY_BURN"
        assert result["recommendations"] == ["CLOSE_REBUILD_KEEP_ROI"]
        assert result["llm_status"] == saved["llm_status"] == expected_status
        assert saved["llm_model"] == "offline-test-model"
    engine.dispose()


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_live_cases_have_deterministic_baseline(case, monkeypatch):
    for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    texts = case.get("texts", [case.get("text")])
    with Session(engine) as db:
        results = [analyze_text(db, case["campaign_id"], text) for text in texts]
        last = results[-1]
        assert all(result["llm_status"] == "fallback_parser" for result in results)
        if "expected_decision" in case:
            assert last["decision"] == case["expected_decision"]
            assert set(case.get("expected_rules", [])) <= set(last["rules_used"])
            assert set(case.get("expected_citations", [])) <= {
                ref["rule_id"] for ref in last["knowledge_refs"]}
            if "expected_recommendation" in case:
                assert case["expected_recommendation"] in last["recommendations"]
        if "expected_delta" in case:
            for field, expected in case["expected_delta"].items():
                assert last["historical_comparison"]["delta"][field] == pytest.approx(expected)
    engine.dispose()
