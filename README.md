# TikTok Content System

Phase 0 and Phase 1 implementation for managing reusable short-video content assets across Southeast Asian markets. The project deliberately does not connect to TikTok, publish content, call AI services, or perform automatic editing.

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

For PostgreSQL, run `docker compose up --build`; the database and services are exposed on ports 5432, 8000, and 5173.

## API

CRUD endpoints are available under `/api/markets`, `/api/products`, `/api/assets`, `/api/scripts`, `/api/templates`, `/api/mix-projects`, `/api/videos`, and `/api/tags`. `GET` endpoints accept `q` and relevant relationship filters. `POST /api/assistant/recommend` provides an explainable hybrid recommendation with market, product, type, semantic, and duration signals. `GET /api/search?q=...&entity=assets` performs hybrid lexical + semantic retrieval and returns `keyword_score`, `semantic_score`, and `final_score`. `POST /api/assets/{id}/file` accepts guarded local media uploads. `POST /api/videos/{id}/versions` records version snapshots. `GET /api/dashboard` returns content asset counts.

The V2 semantic index uses a deterministic local embedding fallback so it works with SQLite and no external AI service. Its `embed`/`cosine` contract is isolated in `backend/app/semantic.py` and can be replaced by an Embedding model plus PostgreSQL `pgvector` without changing the API.

## Tests

```powershell
cd backend
pytest
```
