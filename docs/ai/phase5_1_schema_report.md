# Phase 5.1 Schema and Pattern Design Report

## 1. Reasoning Schema

`decision_reasoning_schema.md` defines a deterministic `reasoning_result` containing campaign stage, fact-only summary, metric diagnosis, possible causes, candidate strategies, observation plan, and traceable Pattern/knowledge references. It explicitly separates facts, inferences, candidate strategies, and human actions. Missing values are represented as missing/unknown; no observation duration is invented.

## 2. Pattern library

`decision_patterns_v1.md` defines P001-P010:

| ID | Title | Source |
|---|---|---|
| P001 | 视频正常但 ROI 低 | operator_experience |
| P002 | 视频质量差导致转化不足 | operator_experience |
| P003 | CTR 低但 CVR 正常 | operator_experience |
| P004 | CTR 正常但 CVR 低 | operator_experience |
| P005 | ROI 高但消耗趋平 | operator_experience |
| P006 | 消耗增长但订单没有同步增长 | operator_experience |
| P007 | 新品快速起量 | operator_experience |
| P008 | 多轮 WAIT_OBSERVE | operator_experience |
| P009 | 数据缺失无法判断 | operator_experience |
| P010 | 指标互相矛盾 | operator_experience |

Each Pattern documents conditions, why it matches, possible causes, candidate strategies, required and missing evidence, uncertainty, priority, version, and source type. No operator experience is represented as an official TikTok rule.

## 3. Rule and Pattern boundary

Rule Engine remains authoritative for `decision`, `rules_used`, facts and thresholds. State Machine remains authoritative for state and transitions. Historical Delta remains code-generated. Patterns only provide uncertain explanations and candidate strategies. LLM, when used in a later phase, may verbalize the structured result but cannot create or modify Rule IDs, Pattern IDs, facts, decision, state, target ROI, Delta, or executed actions.

## 4. Case coverage

`tests/fixtures/decision_reasoning_cases.json` contains **30 uniquely identified design cases**. Coverage includes:

- P001/P002 video and ROI combinations
- low CTR and low CVR diagnostics
- missing target ROI, CTR, CVR, and official completion rate
- missing and present historical Delta
- saturation language without reliable time series
- Rule/Pattern conflict and Rule priority
- A/B and campaign-stage scenarios
- repeated WAIT_OBSERVE
- new-product scaling
- contradictory metric definitions
- missing evidence and uncertainty requirements

The fixture is design data only and is not wired into pytest in Phase 5.1.

## 5. Phase 5.2 recommendation

Implement deterministic modules under `backend/app/ai/reasoning/` in the following order: fact summary, metric diagnosis, campaign-stage classification, Pattern matcher, candidate strategy generator, and observation planner. Persist the first result inside existing Snapshot `source_information`; do not add a migration. Add tests against this fixture before adding any LLM explanation adapter. Stop after deterministic reasoning verification and rerun the existing 152-test baseline.

## Acceptance

- No business code modified in Phase 5.1.
- No database migration or API/frontend change.
- No LLM invocation.
- Reasoning Schema complete.
- Pattern sources traceable.
- 30 evaluation cases designed.
- Rule/Reasoning authority boundary documented.
