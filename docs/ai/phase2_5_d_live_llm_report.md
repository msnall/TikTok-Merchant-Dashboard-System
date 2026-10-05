# Phase 2.5-D Real LLM Integration Report

## Scope

本阶段实现并验证了 OpenAI-compatible LLM 适配层，但当前机器没有配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL`。因此没有伪造真实模型成功，live 结论为 **LIVE_LLM_NOT_CONFIGURED**，不进入 Phase 3。

## A-B. Configuration

| Item | Result |
| --- | --- |
| Model | 未配置 |
| Base URL | 未配置；未写入日志 |
| API key | 未配置、未打印、未写入数据库 |
| Interface | OpenAI-compatible `POST /chat/completions` with JSON response format |

配置后可执行：

```powershell
$env:LLM_API_KEY = "<secret>"
$env:LLM_BASE_URL = "https://<provider>/v1"
$env:LLM_MODEL = "<model>"
cd D:\xiangmuanli\backend
.\.venv\Scripts\python.exe -m pytest -m live_llm -q
```

## C-G. Controlled cases and pipeline

The five cases are in `backend/tests/fixtures/phase2_live_llm_cases.json`:

1. Empty burn: A link, spend 3.5, zero orders.
2. Video normal with ROI below target.
3. B link with ROI above target.
4. No immediate action evidence.
5. Two rounds for historical delta.

The live test asserts strict extraction fields, null handling, A/B and target ROI parsing, deterministic Rule Engine decision, RAG citations, persisted Analysis Run/Snapshot, and code-computed delta. The LLM cannot write `decision`, `rules_used`, `historical_delta`, thresholds, or target ROI policy.

When configured, each call records only `llm_status` (`live_success`, `llm_error`, `fallback_parser`, or `fallback_explanation`) and model name in the existing Snapshot JSON. API keys and request bodies are not persisted.

## H. Fallback

Offline failure tests cover extraction timeout and explanation/schema failure. They preserve the deterministic decision, save the Analysis Run, and expose the fallback status. `WAIT_OBSERVE` explanations are required to retain “先放着不动，等待下一次数据。” and are rejected if they recommend closing or rebuilding.

## I. Offline regression

`pytest` (with the repository default marker exclusion) completed **111 passed, 5 deselected, 0 failed**. The original 102 tests remain green; the additional 9 adapter/baseline tests pass. `pytest -m live_llm` collected five cases and reported **5 skipped** because the three required variables are absent. No live HTTP request was made.

Frontend `npm.cmd run build` completed successfully. The AI analysis page now displays whether the explanation came from a real model or local fallback, plus the model name when available.

## Test environment fix

The original `PermissionError [WinError 5]` came from pytest's default system `tmp_path` root (`C:\Users\woko\AppData\Local\Temp\pytest-of-woko`) and cache directory permissions. Test configuration now sets `--basetemp=.pytest_tmp` and `cache_dir=.pytest_cache_local` in `backend/pytest.ini`; both paths are ignored by Git. `backend/tests/conftest.py` creates the project-local test directory, sets `DATABASE_URL` to `D:\xiangmuanli\backend\.pytest_tmp\test.db`, prints the test/development paths, and rejects path equality before tests run. The live test prints only `LIVE_LLM_CASE_ENTERED=CASE_xxx` and, after configuration, `LLM_REQUEST_STARTED` plus the model name; it never prints a key.

After the fix, `pytest -m live_llm -q -s` entered all five test bodies and returned 5 safe skips with `LIVE_LLM_NOT_CONFIGURED`; there were no setup errors. The development database remained at `0010_ai_decision_foundation`, with 3 runs and 3 snapshots and unchanged SHA-256 `da86581eed556b65dc0b3c235b143354fc3235572fa7d2582528d9e15e996b5b`.

## Current configuration truth check

The installed pytest version does not support a `--showconfig` command-line option; it reported that option as unknown. The effective configuration was verified through pytest's actual run and a dedicated `tests/test_tmp_environment.py` assertion. `pytest --help` confirms the `--basetemp` option, and the test output recorded:

```text
TEST_DATABASE=D:\xiangmuanli\backend\.pytest_tmp\test.db
LIVE_LLM_TEST_DATABASE=D:\xiangmuanli\backend\.pytest_tmp\test.db
DEVELOPMENT_DATABASE=D:\xiangmuanli\backend\content_system.db
TMP_PATH=D:\xiangmuanli\backend\.pytest_tmp\test_tmp_path_uses_project_dir0
```

`pytest -m live_llm -q -s` recorded `LIVE_LLM_CASE_ENTERED=CASE_001` through `CASE_005`; it did not print `LLM_REQUEST_STARTED` because `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are all `MISSING`. The command result was `5 skipped, 112 deselected`, with no PermissionError. A subsequent default run completed **112 passed, 5 deselected, 0 failed**. The development database remained SHA-256 `da86581eed556b65dc0b3c235b143354fc3235572fa7d2582528d9e15e996b5b`, with 3 runs and 3 snapshots.

## J-K. Verdict

`REAL_LLM_CONTROLLED_INTEGRATION = NOT RUN` / `LIVE_LLM_NOT_CONFIGURED`.

This is **not PASS** because the acceptance standard requires at least five successful real-model cases. The deterministic and fallback portions are ready for a configured environment.

## L. Phase 3 recommendation

Do not begin Phase 3 yet. First configure an approved OpenAI-compatible endpoint, run `pytest -m live_llm`, review all five structured outputs and persisted statuses, then separately approve the next phase. Tool Calling, Agent behavior, TikTok account access and automatic advertising actions remain out of scope.

## Phase 2.5-D Fix 1: deterministic normalization

The first DeepSeek run reached the API but returned `link_type=null` for four cases. This is now handled by `backend/app/ai/normalizer.py`; the raw model result is a candidate, while campaign identity is resolved deterministically:

- `campaign_name` naming (`A*...` / `B*...`) has highest priority.
- Explicit `A计划`, `A链接`, `A链` and corresponding B forms are recognized with boundary checks; `AB测试` and `产品A/B` are rejected as ambiguous.
- A campaign-name trailing number supplies `target_roi`; an explicitly written target remains usable when no campaign name exists, while an LLM-only target candidate is ignored.
- Rule Engine receives only `normalized_input`. Snapshot JSON retains both `raw_llm_extraction` and `normalized_input` for audit.

The live fixture's `expected_extract` assertions now validate normalized output, while diagnostic output prints both raw and normalized link/ROI values without secrets. New unit coverage includes A/B plan/link/name variants, ambiguity, precedence, and candidate override protection.

Post-fix verification: **128 passed, 5 deselected, 0 failed**. The current local environment has all three LLM variables missing, so the latest live command entered CASE_001 through CASE_005 and safely returned `5 skipped` with `LIVE_LLM_NOT_CONFIGURED`; it did not send requests. Once the DeepSeek variables are present, rerun `pytest -m live_llm -q -s`; acceptance requires all five cases to pass normalized assertions.

## Phase 2.5-D Fix 3: canonical extraction and explanation handling

`normalize_analysis_input()` now always returns the fixed `CANONICAL_ANALYSIS_FIELDS` schema (including `campaign_id`, the requested metric fields, `currency`, and `roi_policy`), with unresolved values represented by `None`. Missing LLM fields are accepted as candidates with `allow_missing=True` and remain `None` unless deterministic text parsing supplies a value.

Target ROI resolution is now centralized in `extract_target_roi_from_campaign_name()`: a valid campaign-name suffix wins; an explicit deterministic target can be used when no usable name suffix exists; an LLM target candidate is used only when the text contains an explicit target expression; otherwise the result is `None`. No profit formula or inferred numeric value is introduced.

The explanation adapter now emits `LLM_EXPLANATION_STARTED`, model, HTTP status, and raw schema errors without secrets. Explanation numeric grounding includes system-provided snapshots and deltas rather than only the original sentence, preventing valid historical values from incorrectly forcing `fallback_explanation`. Rule Engine output, normalized facts and code-computed delta remain authoritative.

Offline verification after Fix 3: **132 passed, 5 deselected, 0 failed**. The current environment has no DeepSeek variables, so no live request was made in this turn. Development DB remains SHA-256 `2d5e3c4bba32558951ed7db166b3b50e025717f2bb4ee5f7ee3b7d0aa9d4eb9a`, Alembic `0010_ai_decision_foundation`, with 3 runs and 3 snapshots. A configured environment must rerun the five live cases before declaring Real LLM Integration PASS.

## Phase 2.5-D Fix 2: forced test-database isolation

The confirmed call chain is:

```text
pytest -> tests/conftest.py -> TEST_ENVIRONMENT=1 + DATABASE_URL
       -> app.config.Settings -> app.db.engine/SessionLocal
       -> FastAPI get_db dependency -> Analysis API/history writes
```

FastAPI startup uses the same imported test `engine` when loaded by pytest, so `create_all()` and TestClient API calls are also isolated. A running `uvicorn` process is a separate development service and is not used by `test_live_llm.py`; the live test uses a direct SQLAlchemy engine under its `tmp_path`.

`backend/app/db.py` now has a hard fail-fast guard: when `TEST_ENVIRONMENT=1`, any SQLite URL resolving to `backend/content_system.db` raises `RuntimeError("Test environment cannot connect to development database.")` during import. `backend/tests/conftest.py` sets the test mode and fixed URL `D:\xiangmuanli\backend\.pytest_tmp\test.db`, prints both paths, and rejects equality. `backend/tests/test_database_isolation.py` verifies engine path separation and posts `/api/ai/analyses`, asserting the new run is in the test DB while the development DB remains at 3 runs and unchanged SHA-256.

The test environment fix was validated without starting live LLM: **130 passed, 5 deselected, 0 failed**. Development database after the run: SHA-256 `2d5e3c4bba32558951ed7db166b3b50e025717f2bb4ee5f7ee3b7d0aa9d4eb9a`, Alembic `0010_ai_decision_foundation`, 3 Analysis Runs and 3 Snapshots. `pytest -m live_llm` was intentionally not run in this Fix 2 phase.

## Current Fix 3 verification (2026-10-03)

The latest offline regression command, `python -m pytest -m "not live_llm" -q`, completed with **132 passed, 5 deselected, 0 failed**.

The live command was also run with the current configuration. All five cases entered their test bodies (`CASE_001` through `CASE_005`) and were safely skipped because `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` are missing. No `LLM_REQUEST_STARTED` event was emitted, so no model request was made and no live success is claimed.

The development database remained isolated and unchanged:

- Alembic: `0010_ai_decision_foundation`
- `ai_analysis_runs`: 3
- `ai_analysis_snapshots`: 3
- SHA-256: `2d5e3c4bba32558951ed7db166b3b50e025717f2bb4ee5f7ee3b7d0aa9d4eb9a`

The test database remains `D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db`, distinct from `D:\\xiangmuanli\\backend\\content_system.db`.

## Live run follow-up

A configured DeepSeek run reached the API successfully for CASE_001 through CASE_004. CASE_005 failed only on its second-round analysis persistence assertion because a sequential extraction request ended with `llm_status=llm_error`; the first-round extraction and normalization were correct. This was not treated as a successful five-case evaluation.

The adapter now retries one time for transient HTTP/transport failures (`408`, `429`, `5xx`, timeout, and connection errors). Non-transient JSON/schema errors still go through the existing fallback path, and extraction failures emit only a type/message diagnostic without secrets. Offline regression after this change remains **132 passed, 5 deselected, 0 failed**.

The configured environment should rerun `pytest -m live_llm -q -s` to verify CASE_005. The development database must still be checked for 3 runs, 3 snapshots, and an unchanged SHA-256 after that run.

## Live run follow-up 2

The next configured run passed CASE_001, CASE_004, and CASE_005, while exposing two additional provider-variance cases: CASE_002 omitted the explicit `spend` value in one extraction response, and CASE_003 returned an undeclared JSON key. The normalizer now invokes the conservative text parser whenever deterministic input is absent, so explicit facts such as `成本8.6美元` remain available even when the model omits them. In `allow_missing=True` mode, the adapter now drops undeclared provider keys while preserving the fixed extraction schema; strict mode still rejects them. Offline regression after this change remains **132 passed, 5 deselected, 0 failed**.

## Phase 3 entry gate

Phase 2.5-D was subsequently rerun in the configured environment with **5 passed, 132 deselected** on `deepseek-flash`. Extraction, normalization, canonical schema, deterministic Rule Engine decisions, explanations, and CASE_005 historical delta all passed. Phase 3 therefore starts from an accepted live integration baseline.
