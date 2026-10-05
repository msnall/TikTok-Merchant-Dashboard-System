# Phase 4 AI Decision Productization & Evaluation Report

## Dataset

`tests/fixtures/ai_decision_eval_cases.json` contains **33 deterministic cases**. It covers empty burn, poor/normal video, ROI below/above/near target, missing target ROI and video fields, A/B links, campaign-name target ROI, saturation data insufficiency, and independent historical-analysis inputs. No LLM output is used as an oracle.

## Metrics

The deterministic evaluation command verifies every case's expected decision and required Rule IDs:

| Metric | Result | Basis |
|---|---:|---|
| Extraction schema quality | 33/33 cases usable | canonical parser input and null-preserving analysis |
| Normalization quality | 33/33 cases | A/B and campaign-name parsing checks in existing normalizer tests |
| Rule decision accuracy | 33/33 (100%) | expected deterministic decisions |
| State transition accuracy | 17/17 (100%) | Phase 3 state-machine cases |
| Missing-data detection | covered and passed | target ROI, CTR, CVR, completion and saturation cases |
| WAIT_OBSERVE behavior | covered and passed | WAIT cases require deterministic observation behavior |
| RAG evidence coverage | runtime field | real knowledge refs are returned; no refs emit `NO_KNOWLEDGE_EVIDENCE` |
| Explanation quality | contract guarded | grounding and WAIT_OBSERVE safety checks remain active |

These are separate metrics; they are not combined into a single AI accuracy number.

## Data quality and confidence

`backend/app/ai/confidence.py` computes `HIGH`, `MEDIUM`, or `INSUFFICIENT` from business-field completeness, video metrics, and historical availability. It never reads an LLM confidence value. Missing target ROI, spend, or orders is explicitly `INSUFFICIENT`.

## Decision audit and feedback

`GET /api/ai/analyses/{analysis_id}/audit` returns the normalized input, facts, rules, decision, state, historical delta, observation plan, explanation, and human actions. `GET /api/ai/feedback/stats` computes ACCEPT/REJECT/MODIFY totals, ACCEPT agreement, and modification rate from persisted records. Human actions remain separate from recommendations; no subjective correctness label is generated.

## Frontend

`/ads/analysis` now displays confidence and confidence reasons alongside decision, evidence, rules, history, transitions, observation plan, explanation, and human-action controls. All values come from API responses; no mock data was added. Vite build passed.

## Test results

```text
pytest -m "not live_llm" -q
152 passed, 5 deselected, 0 failed
```

The current shell has no LLM credentials. Therefore:

```text
pytest -m live_llm -q -s
5 skipped, 152 deselected
```

All five cases entered their test bodies without requests. The approved Phase 2.5-D DeepSeek baseline remains `5 passed` on `deepseek-flash`; rerun it after configuring credentials to obtain a fresh Phase 4 live regression result.

## Database integrity

Tests used `D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db`; development DB is `D:\\xiangmuanli\\backend\\content_system.db`. Development DB after testing:

```text
Alembic = 0011_stateful_decisions
ai_analysis_runs = 3
ai_analysis_snapshots = 3
SHA-256 = 461d392b626a48e74888ce3ad445c62470bdb0582eec9481eff93dc6ef268790
```

No TikTok API, Agent, Tool Calling, automatic ad operation, budget adjustment, or ROI adjustment was added.
