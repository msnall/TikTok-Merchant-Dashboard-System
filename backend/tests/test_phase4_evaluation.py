import json
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app import ad_models, models, work_models
from app.ai.analysis_service import analyze_text
from app.db import Base


CASES = json.loads((Path(__file__).resolve().parents[2] / "tests" / "fixtures" /
                    "ai_decision_eval_cases.json").read_text(encoding="utf-8"))


def test_evaluation_dataset_has_at_least_thirty_cases():
    assert len(CASES) >= 30
    assert len({case["id"] for case in CASES}) == len(CASES)
    assert all(case.get("expected_decision") for case in CASES)


def test_deterministic_decision_metrics_and_rule_grouping(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'phase4_eval.db').as_posix()}")
    Base.metadata.create_all(engine)
    passed = 0
    by_rule = {}
    with Session(engine) as db:
        for case in CASES:
            result = analyze_text(db, f"phase4_{case['id']}", case["text"])
            decision_ok = result["decision"] == case["expected_decision"]
            rules_ok = set(case.get("rule_ids", [])).issubset(set(result["rules_used"]))
            assert decision_ok and rules_ok, case["id"]
            passed += 1
            for rule_id in case.get("rule_ids", []) or ["NO_RULE"]:
                by_rule.setdefault(rule_id, {"total": 0, "passed": 0})
                by_rule[rule_id]["total"] += 1
                by_rule[rule_id]["passed"] += 1
    assert passed == len(CASES)
    assert all(item["passed"] == item["total"] for item in by_rule.values())
    engine.dispose()
