"""Opt-in real-model evaluation; no case writes to the development database."""

import json
import os
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app import models, ad_models, work_models
from app.ai import models as ai_models
from app.ai.analysis_service import analyze_text, serialize_run
from app.ai.llm import LLMClient
from app.ai.normalizer import normalize_analysis_input


CASES = json.loads((Path(__file__).parent / "fixtures" / "phase2_live_llm_cases.json")
                   .read_text(encoding="utf-8"))


@pytest.mark.live_llm
@pytest.mark.parametrize("case", CASES, ids=lambda case: case["id"])
def test_real_model_controlled_analysis(case, tmp_path):
    print(f"LIVE_LLM_CASE_ENTERED={case['id']}", flush=True)
    if not all(os.getenv(name) for name in ("LLM_API_KEY", "LLM_BASE_URL", "LLM_MODEL")):
        pytest.skip("LIVE_LLM_NOT_CONFIGURED")

    client = LLMClient()
    print("LLM_REQUEST_STARTED", flush=True)
    print(f"LLM_MODEL={client.model}", flush=True)
    texts = case.get("texts", [case.get("text")])
    for text in texts:
        extracted = client.extract(text, allow_missing=True)
        normalized = normalize_analysis_input(text, {}, extracted)
        print(f"LLM_RAW_LINK_TYPE={extracted.get('link_type')}", flush=True)
        print(f"NORMALIZED_LINK_TYPE={normalized.get('link_type')}", flush=True)
        print(f"LLM_RAW_TARGET_ROI={extracted.get('target_roi')}", flush=True)
        print(f"NORMALIZED_TARGET_ROI={normalized.get('target_roi')}", flush=True)
        assert set(extracted) == {
            "campaign_name", "link_type", "target_roi", "spend", "orders", "revenue",
            "current_roi", "ctr", "cvr", "official_completion_rate", "spend_pattern", "report_time",
        }
        assert extracted["revenue"] is None and extracted["report_time"] is None
        for field, expected in case.get("expected_extract", {}).items():
            assert normalized[field] == expected

    engine = create_engine(f"sqlite:///{(tmp_path / 'live_eval.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        results = [analyze_text(db, case["campaign_id"], text) for text in texts]
        assert db.query(ai_models.AIAnalysisRun).count() == len(texts)
        assert db.query(ai_models.AIAnalysisSnapshot).count() == len(texts)
        for result in results:
            saved = serialize_run(db.get(ai_models.AIAnalysisRun, result["analysis_id"]))
            assert result["llm_status"] == saved["llm_status"] == "live_success"
            assert result["llm_model"] == saved["llm_model"] == client.model
            assert result["decision"] == saved["decision"]
            assert saved["raw_llm_extraction"] is not None
            assert saved["normalized_input"] == result["current_analysis"]
            assert result["historical_comparison"]["delta"] == saved["historical_delta"]
            assert all(ref["rule_id"] and ref["source_type"] and ref["version"]
                       for ref in result["knowledge_refs"])
        last = results[-1]
        if "expected_decision" in case:
            assert last["decision"] == case["expected_decision"]
            assert set(case.get("expected_rules", [])) <= set(last["rules_used"])
            assert set(case.get("expected_citations", [])) <= {
                ref["rule_id"] for ref in last["knowledge_refs"]}
            if "expected_recommendation" in case:
                assert case["expected_recommendation"] in last["recommendations"]
        if "expected_delta" in case:
            assert last["historical_comparison"]["previous_analysis_id"] == results[0]["analysis_id"]
            for field, expected in case["expected_delta"].items():
                assert last["historical_comparison"]["delta"][field] == pytest.approx(expected)
    engine.dispose()
