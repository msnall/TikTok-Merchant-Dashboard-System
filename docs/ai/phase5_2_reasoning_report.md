# Phase 5.2 Deterministic Reasoning Report

## 1. New files

Added the deterministic reasoning package:

```text
backend/app/ai/reasoning/
├── __init__.py
├── reasoning.py
├── fact_summary.py
├── metric_diagnosis.py
├── pattern_matcher.py
├── strategy_generator.py
└── observation_planner.py
```

Added `backend/tests/test_reasoning.py`. The existing Phase 5.1 fixture remains `tests/fixtures/decision_reasoning_cases.json` with 30 unique cases.

`analysis_service.py` now invokes `build_reasoning_result()` only after deterministic decision, state, historical Delta, confidence, and knowledge references are already produced. The result is saved inside the existing Snapshot `source_information`; no migration or new table was added.

## 2. Reasoning flow

```text
existing normalized input
→ existing Rule Engine result
→ existing State / Delta / confidence
→ fact summary
→ metric diagnosis
→ campaign stage
→ Pattern matching
→ candidate strategies
→ observation plan
→ reasoning_result
```

The layer never parses natural language, imports `text_parser.py`, calls `rule_engine.py`, calls an LLM, or changes `decision`, `state`, `target_roi`, `rules_used`, or historical Delta.

## 3. Pattern coverage

The matcher supports P001-P010 from `decision_patterns_v1.md`:

- P001 normal video and low ROI
- P002 poor video quality
- P003 low CTR with normal CVR
- P004 normal CTR with low CVR
- P005 high ROI plus reliable time series and flat-spend signal
- P006 positive spend Delta without order growth
- P007 confirmed new-product scaling signals
- P008 repeated WAIT_OBSERVE
- P009 missing evidence or unavailable time series
- P010 explicitly conflicting signals or source definitions

P005 is never matched without reliable time series. P009 is used for missing evidence and adds `NO_KNOWLEDGE_EVIDENCE` when no knowledge chunks are supplied.

## 4. Tests

Reasoning tests verify:

- 30 fixture cases are present and structurally complete
- expected Pattern IDs are matched
- missing target ROI remains a missing ROI diagnosis
- no reliable time series means no SATURATING/P005 conclusion
- Rule decision and State remain unchanged
- candidate strategies are not action commands
- no knowledge references are fabricated

Result: **8 reasoning tests passed**, including a loop over all 30 design cases.

Full offline regression:

```text
160 passed, 5 deselected, 0 failed
```

Frontend build also passed. No LLM request was made in this phase.

## 5. Rule / State isolation

Rule Engine and State Machine source files were not changed. Reasoning output is explanatory only; it stores `pattern_refs`, possible causes, candidate strategies, and observation uncertainties separately from authoritative decision fields. Candidate strategies cannot execute ads, change budgets, or change ROI.

## 6. Database and test isolation

No database migration was added. Tests use `D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db`; the development database remains `D:\\xiangmuanli\\backend\\content_system.db`.

At the end of this phase the development database reports:

```text
Alembic = 0011_stateful_decisions
ai_analysis_runs = 5
ai_analysis_snapshots = 5
SHA-256 = e05c002a797676863c97412133d831e1da19ae8134cd951ba61b09c643cc511b
```

The database already contained 5 runs and 5 snapshots at the start of this regression, despite older Phase 4 reports recording 3/3. No rows were deleted or restored. The isolation assertion now compares development-row counts before and after the test instead of assuming a historical fixed count.

## 7. Phase boundary

Phase 5.2 deterministic reasoning is complete. Phase 5.3 LLM explanation integration was not started.
