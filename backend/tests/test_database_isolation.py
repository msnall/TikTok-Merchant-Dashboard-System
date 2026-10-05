import hashlib
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.db import engine
from app.main import app


def _count(path: Path, table: str) -> int:
    connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
    try:
        return connection.execute(f'SELECT count(*) FROM "{table}"').fetchone()[0]
    finally:
        connection.close()


def test_test_engine_isolated_from_development_database():
    test_path = Path(engine.url.database).resolve()
    development_path = (Path(__file__).resolve().parents[1] / "content_system.db").resolve()
    assert_test_database_isolated()
    assert test_path != development_path


def assert_test_database_isolated():
    test_path = Path(engine.url.database).resolve()
    development_path = (Path(__file__).resolve().parents[1] / "content_system.db").resolve()
    assert test_path == (Path(__file__).resolve().parents[1] / ".pytest_tmp" / "test.db").resolve()
    assert test_path != development_path
    assert test_path.name == "test.db"


def test_analysis_api_writes_only_to_test_database():
    test_path = Path(engine.url.database).resolve()
    development_path = (Path(__file__).resolve().parents[1] / "content_system.db").resolve()
    before_sha = hashlib.sha256(development_path.read_bytes()).hexdigest()
    before_runs = _count(development_path, "ai_analysis_runs")
    with TestClient(app) as client:
        response = client.post("/api/ai/analyses", json={
            "campaign_id": "isolation-demo", "text": "A计划，成本3.5美元，一单没有。",
        })
    assert response.status_code == 200, response.text
    assert _count(test_path, "ai_analysis_runs") >= 1
    assert _count(development_path, "ai_analysis_runs") == before_runs
    assert hashlib.sha256(development_path.read_bytes()).hexdigest() == before_sha
