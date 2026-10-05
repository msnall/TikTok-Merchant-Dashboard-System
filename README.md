# TikTok 东南亚跨境运营工作台

当前冻结版本：V2.5 Phase 1-4 + 填表助手。项目是一个面向 TikTok 东南亚跨境运营的本地 Web 工作台，覆盖内容生产、广告提醒、今日任务和运营留痕。系统不直接连接 TikTok，不自动发布内容、不自动操作广告账户，也不替代剪映。

## Stack

- Backend: Python 3.11, FastAPI, SQLAlchemy 2, Alembic
- Database: SQLite for local development, PostgreSQL via Docker Compose
- Frontend: Vue 3, TypeScript, Vite, Element Plus

## Local startup

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
alembic upgrade head
python seed.py
uvicorn app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Open http://localhost:5173. The API docs are at http://localhost:8000/docs.

If PowerShell blocks `npm.ps1`, use `npm.cmd run dev` and `npm.cmd run build`.

For PostgreSQL, run `docker compose up --build`; the database and services are exposed on ports 5432, 8000, and 5173.

## Modules

- 首页：运营总览、广告提醒、内容交付和最近运营记录
- 今日工作台：固定运营任务、广告异常任务、内容待办、自定义任务和状态跟踪
- 广告计划中心：TikTok Excel 导入、广告快照、目标 ROI、状态判断、计划详情和处理记录
- 内容生产中心：市场、产品、素材、脚本、模板、创作助手、MixProject、时间轴、VideoWork、版本和血缘
- 填表助手：全域消耗和预估赔付、精选联盟费用、销售数据汇总
- 运营记录：直接关停、重建并修改目标 ROI 等人工操作留痕

## API

CRUD endpoints are available under `/api/markets`, `/api/products`, `/api/assets`, `/api/scripts`, `/api/templates`, `/api/mix-projects`, `/api/videos`, and `/api/tags`. `GET` endpoints accept `q` and relevant relationship filters. `POST /api/assistant/recommend` provides an explainable hybrid recommendation with market, product, type, semantic, and duration signals. `GET /api/search?q=...&entity=assets` performs hybrid lexical + semantic retrieval and returns `keyword_score`, `semantic_score`, and `final_score`. `POST /api/assets/{id}/file` accepts guarded local media uploads. `POST /api/videos/{id}/versions` records version snapshots. `GET /api/dashboard` returns content asset counts.

V2.1 adds the end-to-end creation workflow. The assistant displays top templates, scripts, assets, and generated mix plans; choosing a plan opens `/mix-projects/create` with its real IDs. The workspace at `/mix-projects/create` and `/mix-projects/:id` saves a MixProject, validates and persists timeline entries through `PUT /api/mix-projects/{id}/timeline`, and can create an associated VideoWork. Asset and script CRUD accepts `tag_ids` for many-to-many filtering, while `/storage/<path>` serves uploaded local media for preview clients.

V2.5 adds the operations workspace. Ad imports create independent batches and snapshots; only the configured business rules produce reminders, while the operator remains responsible for checking TikTok and executing the actual action. The workbench task generator is date-based and idempotent. The fill assistant's sales feature persists product-code mappings in `product_code_mappings` but keeps each uploaded order analysis as a browser-session result.

To verify a clean schema locally:

```powershell
cd backend
alembic upgrade head
python seed.py
```

The V2 semantic index uses a deterministic local embedding fallback so it works with SQLite and no external AI service. Its `embed`/`cosine` contract is isolated in `backend/app/semantic.py` and can be replaced by an Embedding model plus PostgreSQL `pgvector` without changing the API.

## Database and migrations

The local database is SQLite by default. PostgreSQL remains available through Docker Compose. The current Alembic head is `0010_ai_decision_foundation`.

```powershell
cd backend
alembic upgrade head
alembic current
```

The standard seed creates baseline content data. For a full demonstration, add a small set of advertising plans, snapshots, operations, MixProjects and VideoWorks through the UI or API so both main business chains are visible.

Phase 0 adds a deterministic decision foundation under `backend/app/ai/`: independent campaign video metrics, ROI policy labels, campaign time-series storage, and append-only analysis runs with input snapshots. It does not call an LLM, retrieve knowledge with RAG, or operate a TikTok account. The AI-layer empty-burn criterion (`USD spend > 3` and zero orders) is separate from the existing advertising page's six-state rule; the advertising page remains unchanged. The active rule and data contracts are in `docs/ai/AI运营决策知识库_V0.1.md`, `docs/ai/data_contract.md`, and `docs/ai/ai_decision_contract.md`.

Before upgrading an existing local database, inspect its `alembic_version` and tables. A development database may contain empty, unversioned `campaign_video_metrics` / `campaign_metric_timeseries` tables left by earlier experiments. Migration `0010` stops instead of overwriting those tables. Back up and reconcile that database separately; the migration's upgrade/downgrade/upgrade test uses an isolated database.

## Tests

```powershell
cd backend
pytest

cd ..\frontend
npm.cmd run build
```

The freeze verification report is in `docs/V2.5_FREEZE_TEST_REPORT.md`.

## Scope boundaries

The current version intentionally does not include TikTok API access, automatic advertising actions, automatic video editing, ASR, video understanding, real embedding models or pgvector. Those are future possibilities, not prerequisites for the current application-system case.
