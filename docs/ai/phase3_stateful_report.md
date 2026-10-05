# Phase 3 Stateful Decision Engine

## Implemented

- Deterministic state mapping in `backend/app/ai/state_machine.py`.
- Append-only `ai_state_transitions` and `decision_actions` tables in migration `0011_stateful_decisions`.
- Every analysis stores state, transition, and (for WAIT_OBSERVE) an observation plan in its immutable snapshot source information.
- Historical Delta continues to be computed by Python from the previous Run; LLM output cannot change it.
- `POST /api/ai/analyses/{analysis_id}/actions` records ACCEPT, REJECT, or MODIFY plus the actual operator action.
- Campaign history returns state transitions; `/ads/analysis` displays current state, transition, observation plan, timeline, and human-action controls.

## Evaluation

`backend/tests/test_phase3_stateful.py` contains 17 deterministic cases covering first observation, repeated observation, improvement/degradation transitions, close/rebuild, confirmation, repeated WAIT_OBSERVE, invalid/missing previous state, and observation-plan contents.

Offline result: **149 passed, 5 deselected, 0 failed**.

Frontend build: passed with Vite.

## Database

The development database was backed up at `backend/backup/phase3_before_0011/` before applying 0011. It now reports `0011_stateful_decisions`; both new tables exist. Existing data remains `ai_analysis_runs = 3` and `ai_analysis_snapshots = 3`.

The live LLM baseline remains **5 passed** on `deepseek-flash`; it should be rerun after any deployment change. No TikTok API, Tool Calling, Agent, automatic budget change, ROI change, or ad operation was added.
