"""Keep application imports in tests away from the development database."""

import os
from pathlib import Path
import pytest
from uuid import uuid4

BACKEND_DIR = Path(__file__).resolve().parents[1]
TEST_TEMP_DIR = BACKEND_DIR / ".pytest_tmp"
TEST_DATABASE = TEST_TEMP_DIR / "test.db"
DEVELOPMENT_DATABASE = BACKEND_DIR / "content_system.db"

def pytest_configure(config):
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    os.environ["TEST_ENVIRONMENT"] = "1"
    os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DATABASE.as_posix()}"
    config._tiktok_test_database = TEST_DATABASE
    config.option.basetemp = str(TEST_TEMP_DIR / f"run_{uuid4().hex[:8]}")


@pytest.fixture(autouse=True)
def ensure_test_environment():
    TEST_TEMP_DIR.mkdir(parents=True, exist_ok=True)
    if TEST_DATABASE.resolve() == DEVELOPMENT_DATABASE.resolve():
        raise RuntimeError("测试数据库不能指向开发数据库")
    yield


def pytest_sessionstart(session):
    print(f"TEST_DATABASE={TEST_DATABASE.resolve()}", flush=True)
    print(f"LIVE_LLM_TEST_DATABASE={TEST_DATABASE.resolve()}", flush=True)
    print(f"DEVELOPMENT_DATABASE={DEVELOPMENT_DATABASE.resolve()}", flush=True)
    if TEST_DATABASE.resolve() == DEVELOPMENT_DATABASE.resolve():
        raise RuntimeError("测试数据库与开发数据库路径相同")
