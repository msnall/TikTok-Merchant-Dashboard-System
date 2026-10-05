import hashlib
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Column, Date, DateTime, String, create_engine
from sqlalchemy.orm import Session

from app.db import Base
from app import models, ad_models, work_models
from app.ai.models import AIAnalysisRun, AIAnalysisSnapshot


BACKEND = Path(__file__).resolve().parents[1]


def _version(path):
    with sqlite3.connect(path) as connection:
        return connection.execute("SELECT version_num FROM alembic_version").fetchone()[0]


def _ids(path, table):
    with sqlite3.connect(path) as connection:
        return connection.execute(f'SELECT id FROM "{table}" ORDER BY id').fetchall()


def test_reconciliation_runs_only_on_copy_and_preserves_analysis(tmp_path):
    source = tmp_path / "unversioned_ai.db"
    backup_root = tmp_path / "reconcile_backup"
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{source.as_posix()}"}
    baseline = subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0009_script_timeline"],
                              cwd=BACKEND, env=environment, capture_output=True, text=True)
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr

    engine = create_engine(f"sqlite:///{source.as_posix()}")
    Base.metadata.create_all(engine)
    with engine.begin() as connection:
        operations = Operations(MigrationContext.configure(connection))
        with operations.batch_alter_table("ad_plan_snapshots", recreate="always") as batch:
            batch.add_column(Column("report_date", Date()))
            batch.add_column(Column("report_start_at", DateTime()))
            batch.add_column(Column("report_end_at", DateTime()))
            batch.alter_column("snapshot_at", existing_type=DateTime(), nullable=False)
            batch.alter_column("status", existing_type=String(40), server_default=None)
    with Session(engine) as session:
        for number in range(3):
            run = AIAnalysisRun(
                campaign_id=f"test-{number}", decision="INSUFFICIENT_DATA",
                rules_used="[]", facts="[]", recommendations="[]",
                uncertainties="[]", source_type="synthetic_demo",
            )
            run.snapshot = AIAnalysisSnapshot(
                campaign_data="{}", video_data="{}",
                source_information=f'{{"case":{number}}}',
            )
            session.add(run)
        session.commit()
    engine.dispose()
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()

    result = subprocess.run([
        sys.executable, "scripts/reconcile_phase2_5.py",
        "--source", str(source), "--backup-root", str(backup_root),
    ], cwd=BACKEND, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    working_dirs = list(backup_root.iterdir())
    assert len(working_dirs) == 1
    working = working_dirs[0] / "reconciled_working.db"
    assert hashlib.sha256(source.read_bytes()).hexdigest() == source_hash
    assert _version(source) == "0009_script_timeline"
    assert _version(working) == "0010_ai_decision_foundation"
    for table in ("ai_analysis_runs", "ai_analysis_snapshots"):
        assert _ids(source, table) == _ids(working, table) == [(1,), (2,), (3,)]
    with sqlite3.connect(working) as connection:
        assert connection.execute("SELECT count(*) FROM roi_policy_config").fetchone()[0] == 3
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
