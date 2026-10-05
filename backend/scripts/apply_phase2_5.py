"""Apply the verified Phase 2.5 reconciliation to the development SQLite DB.

This one-time operation requires the backend to be stopped. It does not run
historical migration 0010 or use Alembic stamp.
"""

import argparse
from contextlib import closing
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
from uuid import uuid4

from phase2_5_schema_validation import (
    PROTECTED_TABLES, assert_known_differences, compare_schema,
    connect_readonly, database_checks, policy_rows, table_fingerprint, version,
)
from reconcile_phase2_5 import (
    BACKEND, FROM_VERSION, TO_VERSION, WORKSPACE, _file_sha256,
    _reconcile_version, _reference_database, _repair_working_copy,
    _sqlite_backup,
)


def _inventory(database: Path) -> dict:
    with closing(connect_readonly(database)) as connection:
        table_names = [row[0] for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name NOT LIKE 'sqlite_%' ORDER BY name"
        )]
        counts = {name: connection.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]
                  for name in table_names}
        schema = "\n\n".join(row[0] + ";" for row in connection.execute(
            "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL ORDER BY type, name"
        )) + "\n"
    return {"row_counts": counts, "schema_dump": schema}


def _audit(database: Path) -> dict:
    inventory = _inventory(database)
    return {
        "database_path": str(database),
        "sha256": _file_sha256(database),
        "alembic_version": version(database),
        "row_counts": inventory["row_counts"],
        "protected_rows": {table: table_fingerprint(database, table)
                           for table in PROTECTED_TABLES},
        "roi_policies": policy_rows(database),
        "sqlite_checks": database_checks(database),
    }


def _save_audit(directory: Path, database: Path) -> dict:
    result = _audit(database)
    (directory / "audit.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    (directory / "schema_dump.sql").write_text(
        _inventory(database)["schema_dump"], encoding="utf-8")
    return result


def apply(source: Path, backup_root: Path) -> Path:
    source, backup_root = source.resolve(), backup_root.resolve()
    if source != (BACKEND / "content_system.db").resolve():
        raise ValueError("Only the confirmed development database may be reconciled")
    if not source.is_file() or version(source) != FROM_VERSION:
        raise ValueError("Development database must exist at revision 0009")

    run_dir = backup_root / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
                             + "_" + uuid4().hex[:8])
    before_dir, after_dir = run_dir / "before", run_dir / "after"
    before_dir.mkdir(parents=True, exist_ok=False)
    after_dir.mkdir()
    raw_backup = before_dir / "content_system.original.db"
    consistent_backup = before_dir / "content_system.consistent.db"
    shutil.copy2(source, raw_backup)
    _sqlite_backup(source, consistent_backup)
    before = _save_audit(before_dir, consistent_backup)
    if (_file_sha256(source) != _file_sha256(raw_backup) or
            before["alembic_version"] != FROM_VERSION or
            before["sqlite_checks"] != {"integrity": "ok", "foreign_key_violations": []} or
            before["row_counts"]["ai_analysis_runs"] != 3 or
            before["row_counts"]["ai_analysis_snapshots"] != 3 or
            before["row_counts"]["roi_policy_config"] != 0):
        raise RuntimeError("Pre-apply backup or data validation failed; source untouched")

    reference = run_dir / "reference_0010.db"
    _reference_database(reference)
    assert_known_differences(consistent_backup, reference)
    seeds = policy_rows(reference)
    if len(seeds) != 3 or _file_sha256(source) != _file_sha256(raw_backup):
        raise RuntimeError("Reference seed or source stability check failed; source untouched")

    _repair_working_copy(source, seeds)
    repaired = _audit(source)
    expected_counts = dict(before["row_counts"])
    expected_counts["roi_policy_config"] = 3
    if (compare_schema(source, reference) or repaired["roi_policies"] != seeds or
            repaired["protected_rows"] != before["protected_rows"] or
            repaired["row_counts"] != expected_counts or
            repaired["sqlite_checks"] != {"integrity": "ok", "foreign_key_violations": []}):
        raise RuntimeError("Schema, seed, data or SQLite checks failed; version remains at 0009. Restore the backup.")

    _reconcile_version(source)
    if (version(source) != TO_VERSION or compare_schema(source, reference) or
            policy_rows(source) != seeds or
            {table: table_fingerprint(source, table) for table in PROTECTED_TABLES}
            != before["protected_rows"]):
        raise RuntimeError("Post-version validation failed. Restore the backup.")

    after_backup = after_dir / "content_system.db"
    _sqlite_backup(source, after_backup)
    after = _save_audit(after_dir, after_backup)
    if (after["alembic_version"] != TO_VERSION or
            after["protected_rows"] != before["protected_rows"] or
            after["roi_policies"] != seeds or
            after["sqlite_checks"] != {"integrity": "ok", "foreign_key_violations": []}):
        raise RuntimeError("Final backup verification failed. Restore the pre-apply backup.")

    record = {
        "operation_time_utc": datetime.now(timezone.utc).isoformat(),
        "source_database": str(source), "backup_directory": str(run_dir),
        "previous_version": FROM_VERSION, "target_version": TO_VERSION,
        "description": "Existing schema was aligned to 0010, then Alembic version was reconciled; historical 0010 upgrade was not replayed.",
        "schema_equivalent": True, "seed_equivalent": True,
        "analysis_data_preserved": True, "all_table_row_counts_preserved_except_roi_seed": True,
        "ddl_executed_on_development_database": True,
        "version_bookkeeping": "UPDATE alembic_version from 0009 to 0010 after validation; no stamp",
        "before_sha256": before["sha256"], "after_backup_sha256": after["sha256"],
        "before_protected_rows": before["protected_rows"],
        "after_protected_rows": after["protected_rows"],
    }
    (run_dir / "version_reconciliation_record.json").write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return run_dir


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=BACKEND / "content_system.db")
    parser.add_argument("--backup-root", type=Path,
                        default=WORKSPACE / "backup" / "phase2_5_apply_0010")
    args = parser.parse_args()
    print("Applied Phase 2.5 reconciliation:", apply(args.source, args.backup_root))


if __name__ == "__main__":
    main()
