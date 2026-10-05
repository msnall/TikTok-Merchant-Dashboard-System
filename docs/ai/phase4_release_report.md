# Phase 4 Release Regression Report

## Offline regression

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -m "not live_llm" -q
```

Result: **152 passed, 5 deselected, 0 failed**.

## Stateful E2E regression

`tests/test_phase3_acceptance.py` passed: **1 passed**. It verified Round 1 and Round 2 using an isolated database, historical Snapshot lookup, code-computed Delta, State Transition persistence, ACCEPT/MODIFY Human Actions, and append-only records. Test output confirmed:

```text
TEST_DATABASE=D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db
DEVELOPMENT_DATABASE=D:\\xiangmuanli\\backend\\content_system.db
```

## Live LLM regression

Command:

```powershell
.\\.venv\\Scripts\\python.exe -m pytest -m live_llm -q -s
```

The current terminal does not have `LLM_API_KEY`, `LLM_BASE_URL`, or `LLM_MODEL`. All five live cases entered their test bodies and were safely skipped:

```text
5 skipped, 152 deselected
```

No live request was made and no success was fabricated. The accepted Phase 2.5-D DeepSeek baseline remains **5 passed** on `deepseek-flash`.

## Frontend build

`npm.cmd run build` completed successfully with Vite. Existing bundle-size/config warnings do not fail the build.

## Database integrity

Development database: `D:\\xiangmuanli\\backend\\content_system.db`
Test database: `D:\\xiangmuanli\\backend\\.pytest_tmp\\test.db`

Final development database verification:

```text
Alembic = 0011_stateful_decisions
ai_analysis_runs = 3
ai_analysis_snapshots = 3
SHA-256 = 461d392b626a48e74888ce3ad445c62470bdb0582eec9481eff93dc6ef268790
```

The SHA-256 matches the release baseline recorded before regression. Test output and the database isolation guard confirm tests used the project-local test database rather than the development database.

## Final baseline

- Phase 4 remains complete.
- No business logic, Rule Engine, ROI rules, State Machine rules, or LLM contract was changed during this release regression.
- No TikTok API, Agent, Tool Calling, automatic advertising operation, budget adjustment, or ROI adjustment was added.
- Do not enter Phase 5 in this release task.
