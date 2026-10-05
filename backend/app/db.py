from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from pathlib import Path
import os
from .config import settings


def _database_path(url: str) -> Path | None:
    if not url.startswith("sqlite"):
        return None
    value = url.split("///", 1)[-1].split("?", 1)[0]
    return Path(value).resolve()


if os.getenv("TEST_ENVIRONMENT") == "1":
    configured = _database_path(settings.database_url)
    development = (Path(__file__).resolve().parents[1] / "content_system.db").resolve()
    if configured is None or configured == development:
        raise RuntimeError("Test environment cannot connect to development database.")

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=connect_args)
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _enable_sqlite_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
