# Phase 5.3 Text Explanation Layer Report

## Scope

This phase adds pure text-input operational reporting after the existing parser, normalizer, Rule Engine, State Machine, Delta, confidence, and deterministic reasoning layers. Excel, TikTok API, scraping, Agent, Tool Calling, and automatic advertising actions remain out of scope.

## New implementation

Added `backend/app/ai/explanation/formatter.py` and package initializer. `build_operation_report()` converts the existing `reasoning_result` into a report containing:

- current campaign stage
- current situation summary
- video quality judgment
- ROI problem judgment
- possible causes with evidence and confidence
- candidate recommended actions
- recommendation reasons
- next observation metrics
- uncertainties
- decision and state
- Pattern and knowledge references

The report is persisted in the existing Snapshot `source_information` and returned by `POST /api/ai/analyses` and serialized history records. No database migration was added.

## LLM boundary and fallback

The existing optional `LLMClient.explain()` remains a prose adapter only. Deterministic report fields are generated first. Any LLM summary is stored separately as `llm_summary`; it cannot overwrite decision, state, facts, target ROI, Delta, references, candidate actions, or observation metrics. Without LLM configuration, the complete template report is returned with `mode=template_fallback`.

## Frontend

`/ads/analysis` now displays an “AI运营建议” section with campaign stage, situation summary, video and ROI judgments, possible causes, candidate actions, reasons, next metrics, uncertainties, and human-confirmation status. Candidate strategies are explicitly labeled as not executed actions.

## Tests

Added `backend/tests/test_explanation.py` covering:

- empty-burn plan
- low ROI with normal video
- poor video and low ROI
- new-product report
- WAIT_OBSERVE
- missing target ROI
- LLM prose attempting to change deterministic fields

Result: **7 explanation tests passed**.

Full offline regression:

```text
167 passed, 5 deselected, 0 failed
```

Frontend build passed. No Excel, TikTok API, Agent, Tool Calling, or automatic action was introduced.

## Database integrity

No migration was added. Development database remains:

```text
Alembic = 0011_stateful_decisions
ai_analysis_runs = 5
ai_analysis_snapshots = 5
SHA-256 = e05c002a797676863c97412133d831e1da19ae8134cd951ba61b09c643cc511b
```

Tests continue to use the isolated `.pytest_tmp/test.db`; the development database was not modified.

## Boundary

Phase 5.3 is complete. Agent behavior and further automation were not started.
