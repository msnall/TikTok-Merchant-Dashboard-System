"""Reconcile an isolated SQLite copy; never mutate the source database.

Run from the backend directory:
    .venv/Scripts/python scripts/reconcile_phase2_5.py

The only version update is performed on the working copy after the complete
schema, seed, and protected-row checks pass. Applying this to the development
database is a separate, manually approved operation.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
from uuid import uuid4

from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, DateTime, String, create_engine, text

from phase2_5_schema_validation import (
    PROTECTED_TABLES, assert_known_differences, compare_schema, database_checks,
    policy_rows, table_fingerprint, version,
)


BACKEND = Path(__file__).resolve().parents[1]
WORKSPACE = BACKEND.parent
FROM_VERSION = "0009_script_timeline"
TO_VERSION = "0010_ai_decision_foundation"


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sqlite_backup(source: Path, destination: Path) -> None:
    with closing(sqlite3.connect(source.resolve().as_uri() + "?mode=ro", uri=True)) as original:
        with closing(sqlite3.connect(destination)) as target:
            original.backup(target)


def _reference_database(path: Path) -> None:
    environment = {**os.environ, "DATABASE_URL": f"sqlite:///{path.as_posix()}"}
    completed = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", TO_VERSION],
        cwd=BACKEND, env=environment, capture_output=True, text=True,
    )
    if completed.returncode:
        raise RuntimeError("Could not build clean 0010 reference: " + completed.stderr[-2000:])
    if version(path) != TO_VERSION:
        raise RuntimeError("Clean reference did not reach 0010")


def _repair_working_copy(path: Path, seeds: list[tuple]) -> None:
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with engine.begin() as connection:
            operations = Operations(MigrationContext.configure(connection))
            with operations.batch_alter_table(
                "campaign_metric_timeseries", recreate="always",
                table_args=(CheckConstraint(
                    "measurement_type IN ('cumulative', 'interval')",
                    name="ck_timeseries_measurement",
                ),),
            ):
                pass
            with operations.batch_alter_table("ad_plan_snapshots", recreate="always") as batch:
                batch.alter_column("snapshot_at", existing_type=DateTime(), nullable=True)
                batch.alter_column("status", existing_type=String(40), server_default="unknown")
            for code, name, order, description in seeds:
                connection.execute(text(
                    "INSERT INTO roi_policy_config "
                    "(policy_code, policy_name, sort_order, description) "
                    "VALUES (:code, :name, :sort_order, :description)"
                ), {"code": code, "name": name, "sort_order": order,
                    "description": description})
    finally:
        engine.dispose()


def _reconcile_version(path: Path) -> None:
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with engine.begin() as connection:
            current = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
            if current != [FROM_VERSION]:
                raise ValueError(f"Unexpected version immediately before bookkeeping: {current}")
            changed = connection.execute(text(
                "UPDATE alembic_version SET version_num = :target "
                "WHERE version_num = :source"
            ), {"target": TO_VERSION, "source": FROM_VERSION})
            if changed.rowcount != 1:
                raise RuntimeError("Version bookkeeping did not update exactly one row")
    finally:
        engine.dispose()


def reconcile_copy(source: Path, backup_root: Path) -> Path:
    source, backup_root = source.resolve(), backup_root.resolve()
    if not source.is_file() or source.suffix.lower() != ".db":
        raise ValueError("Source must be an existing SQLite .db file")
    if version(source) != FROM_VERSION:
        raise ValueError("Source is not at the expected 0009 revision")
    source_sha256_before = _file_sha256(source)

    backup_root.mkdir(parents=True, exist_ok=True)
    run_dir = backup_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                             + "_" + uuid4().hex[:8])
    run_dir.mkdir(exist_ok=False)
    source_backup = run_dir / "source_backup.db"
    working = run_dir / "reconciled_working.db"
    reference = run_dir / "reference_0010.db"
    _sqlite_backup(source, source_backup)
    shutil.copy2(source_backup, working)
    _reference_database(reference)

    if version(source_backup) != FROM_VERSION or version(working) != FROM_VERSION:
        raise RuntimeError("Backup version changed during copy")
    if database_checks(source_backup) != {"integrity": "ok", "foreign_key_violations": []}:
        raise RuntimeError("Source backup failed SQLite integrity or FK checks")
    before = {table: table_fingerprint(source_backup, table) for table in PROTECTED_TABLES}
    if before["ai_analysis_runs"]["count"] != 3 or before["ai_analysis_snapshots"]["count"] != 3:
        raise ValueError("Expected 3 analysis runs and 3 snapshots; source changed")
    if policy_rows(working):
        raise ValueError("ROI policies are not empty; refusing to insert seed rows")
    assert_known_differences(working, reference)
    seeds = policy_rows(reference)
    if len(seeds) != 3:
        raise RuntimeError("0010 reference did not produce exactly three ROI policies")

    _repair_working_copy(working, seeds)
    after = {table: table_fingerprint(working, table) for table in PROTECTED_TABLES}
    schema_equivalent = not compare_schema(working, reference)
    seed_equivalent = policy_rows(working) == seeds
    data_preserved = before == after
    checks = database_checks(working)
    if not (schema_equivalent and seed_equivalent and data_preserved and
            checks == {"integrity": "ok", "foreign_key_violations": []}):
        raise RuntimeError("Working copy failed schema, seed, data or integrity validation; version left at 0009")

    _reconcile_version(working)
    if version(working) != TO_VERSION or compare_schema(working, reference) or \
            policy_rows(working) != seeds or \
            {table: table_fingerprint(working, table) for table in PROTECTED_TABLES} != before:
        raise RuntimeError("Post-version validation failed; source remains untouched")
    source_sha256_after = _file_sha256(source)
    if source_sha256_before != source_sha256_after:
        raise RuntimeError("Source database changed during reconciliation; do not apply this working copy")

    audit = {
        "operation_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": str(source), "source_backup": str(source_backup),
        "working_copy": str(working), "reference_database": str(reference),
        "previous_version": FROM_VERSION, "target_version": TO_VERSION,
        "working_copy_version": version(working),
        "source_sha256_before": source_sha256_before,
        "source_sha256_after": source_sha256_after,
        "source_backup_sha256": _file_sha256(source_backup),
        "description": "Schema was repaired to match 0010, then the working copy's version was reconciled; historical 0010 was not replayed on the data-bearing copy.",
        "schema_equivalent": True, "seed_equivalent": True,
        "analysis_data_preserved": True,
        "protected_rows_before": before, "protected_rows_after": after,
        "sqlite_checks": checks,
        "executor": "backend/scripts/reconcile_phase2_5.py",
        "ddl_executed_on_working_copy": True,
        "ddl_executed_on_source": False,
        "version_bookkeeping": "UPDATE alembic_version SET version_num = :target WHERE version_num = :source (working copy only, after validation)",
    }
    (run_dir / "version_reconciliation_record.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BACKEND / "content_system.db")
    parser.add_argument("--backup-root", type=Path,
                        default=WORKSPACE / "backup" / "phase2_5_reconcile")
    args = parser.parse_args()
    location = reconcile_copy(args.source, args.backup_root)
    print(f"Working-copy reconciliation passed: {location}")
    print("Source database was not modified. Development-library application requires separate human confirmation.")


if __name__ == "__main__":
    main()
