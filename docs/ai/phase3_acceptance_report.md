# Phase 3 Stateful AI Decision Engine Acceptance Report

## 1. Stateful E2E test

Added `backend/tests/test_phase3_acceptance.py`. It uses an isolated SQLite database and two independent calls to `analyze_text` with the same `campaign_id`; no chat history is used. The test then calls the real FastAPI action endpoints for ACCEPT and MODIFY.

## 2. Round 1

Input: `A计划成本8.6美元，3单，ROI0.71，CTR2.6%，CVR11.3%，完播率36%。`

The text intentionally has no target ROI. The deterministic result is `INSUFFICIENT_DATA` and state `ACTIONABLE`; the system does not guess a target ROI. Run #1 and Snapshot #1 are persisted. No observation plan is created because the decision is not WAIT_OBSERVE.

## 3. Round 2

Input: `A计划现在成本11.4美元，5单，ROI0.86，CTR2.8%，CVR12%，完播率37%。`

The service queried the previous Run/Snapshot by `campaign_id`, normalized the second input, calculated Delta in Python, and appended Run #2/Snapshot #2. The decision remains deterministic `INSUFFICIENT_DATA`, with state transition `ACTIONABLE -> ACTIONABLE` because target ROI is still absent.

## 4. Delta verification

The E2E assertion confirmed:

```text
delta_spend = 2.8
delta_orders = 2
delta_roi = 0.15
delta_ctr = 0.002
delta_cvr = 0.007
delta_completion_rate = 0.01
```

These values come from `_delta(previous, current)` and not from the LLM.

## 5. State transition

Two append-only `ai_state_transitions` rows were created. The second row references Round 2's `analysis_run_id`, and its `to_state` matches the deterministic result. No historical transition is overwritten.

## 6. Observation plan

The state machine creates an observation plan whenever the deterministic decision is `WAIT_OBSERVE`, including campaign ID, previous analysis ID, reason, and the six comparison metrics. The supplied smoke text lacks target ROI, so this specific run correctly reports insufficient data instead of fabricating WAIT_OBSERVE.

## 7. Human actions

The test called the real `POST /api/ai/analyses/{round2_id}/actions` endpoint for ACCEPT and MODIFY, then queried `GET /api/ai/analyses/{round2_id}/actions`. Both actions were persisted with the correct `analysis_run_id`, timestamps, and independent `actual_action` values. MODIFY did not overwrite the AI recommendation.

## 8. Frontend data verification

`frontend/src/views/AIAnalysis.vue` renders state, decision, previous decision, Delta, state transition, observation plan, AI explanation, human action controls, and the decision timeline from the analysis/history/action APIs. No mock data was added. `npm.cmd run build` passed.

## 9. Database verification

Tests used `D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db`; the development database is `D:\\xiangmuanli\\backend\\content_system.db`. The development database was not touched by tests. After the acceptance run:

```text
Alembic = 0011_stateful_decisions
ai_analysis_runs = 3
ai_analysis_snapshots = 3
ai_state_transitions = 0
decision_actions = 0
SHA-256 = 461d392b626a48e74888ce3ad445c62470bdb0582eec9481eff93dc6ef268790
```

The zero counts are expected because E2E rows were written to the isolated test database.

## 10. Test results

Offline: `pytest -m "not live_llm" -q` -> **150 passed, 5 deselected, 0 failed**.

The configured DeepSeek regression supplied for the Phase 2.5-D gate remains **5 passed, 132 deselected** on `deepseek-flash`. In this shell the live credentials are absent, so the post-Phase-3 command safely entered all five cases and returned **5 skipped, 150 deselected** without making requests. No Phase 3 code changes the LLM extraction or explanation contract; rerun with the approved credentials for a fresh live check.

## 11. Final verdict

**Phase 3 Stateful AI Decision Engine = PASS**

No Phase 4 functionality, Tool Calling, Agent behavior, TikTok API integration, automatic ad operation, budget changes, or ROI changes were added.
