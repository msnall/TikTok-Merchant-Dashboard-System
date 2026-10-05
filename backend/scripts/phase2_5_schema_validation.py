"""Structural and data checks for the one-time Phase 2.5 SQLite repair."""

import hashlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

from sqlalchemy import create_engine, inspect


TARGET_TABLES = (
    "roi_policy_config",
    "campaign_video_metrics",
    "campaign_metric_timeseries",
    "ai_analysis_runs",
    "ai_analysis_snapshots",
    "ad_plan_snapshots",
)
PROTECTED_TABLES = ("ai_analysis_runs", "ai_analysis_snapshots", "ad_plan_snapshots")
SOURCE_CHECK = ("ck_campaign_timeseries_source",
                "source_type IN ('uploaded_source', 'manual_entry', 'synthetic_demo')")
MEASUREMENT_CHECK = ("ck_timeseries_measurement",
                     "measurement_type IN ('cumulative', 'interval')")


def schema_signature(database: Path) -> dict:
    engine = create_engine(f"sqlite:///{database.as_posix()}")
    inspector = inspect(engine)
    result = {}
    for table in TARGET_TABLES:
        if not inspector.has_table(table):
            raise ValueError(f"Missing table: {table}")
        result[table] = {
            "columns": {
                item["name"]: (
                    str(item["type"]).upper(), bool(item["nullable"]),
                    str(item["default"]) if item["default"] is not None else None,
                    bool(item.get("primary_key")),
                ) for item in inspector.get_columns(table)
            },
            "primary_key": tuple(inspector.get_pk_constraint(table)["constrained_columns"]),
            "foreign_keys": sorted((
                tuple(item["constrained_columns"]), item["referred_table"],
                tuple(item["referred_columns"]), item.get("options", {}).get("ondelete"),
            ) for item in inspector.get_foreign_keys(table)),
            "unique": sorted((
                item.get("name") or "", tuple(item["column_names"]),
            ) for item in inspector.get_unique_constraints(table)),
            "indexes": sorted((
                item["name"], tuple(item["column_names"]), bool(item["unique"]),
            ) for item in inspector.get_indexes(table)),
            "checks": sorted((
                item.get("name") or "", " ".join(item["sqltext"].split()),
            ) for item in inspector.get_check_constraints(table)),
        }
    engine.dispose()
    return result


def compare_schema(actual: Path, expected: Path) -> dict:
    left, right = schema_signature(actual), schema_signature(expected)
    return {
        table: {category: {"actual": left[table][category], "expected": right[table][category]}
                for category in right[table] if left[table][category] != right[table][category]}
        for table in TARGET_TABLES
        if left[table] != right[table]
    }


def assert_known_differences(actual: Path, expected: Path) -> None:
    left, right = schema_signature(actual), schema_signature(expected)
    for table in TARGET_TABLES:
        for category in right[table]:
            if table == "campaign_metric_timeseries" and category == "checks":
                checks = left[table][category]
                if checks != [SOURCE_CHECK] or right[table][category] != sorted((SOURCE_CHECK, MEASUREMENT_CHECK)):
                    raise ValueError(f"Unexpected timeseries CHECK constraints: {checks}")
            elif table == "ad_plan_snapshots" and category == "columns":
                current = left[table][category]
                target = right[table][category]
                if set(current) != set(target):
                    raise ValueError("Unexpected ad snapshot columns")
                for name, value in target.items():
                    if name == "snapshot_at":
                        allowed = (value[0], False, value[2], value[3])
                    elif name == "status":
                        allowed = (value[0], value[1], None, value[3])
                    else:
                        allowed = value
                    if current[name] != allowed:
                        raise ValueError(f"Unexpected ad snapshot column: {name}")
            elif left[table][category] != right[table][category]:
                raise ValueError(f"Unexpected {table} {category} difference")


def connect_readonly(database: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database.resolve().as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def version(database: Path) -> str:
    with closing(connect_readonly(database)) as connection:
        rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
    if len(rows) != 1:
        raise ValueError("alembic_version must contain exactly one row")
    return rows[0][0]


def table_fingerprint(database: Path, table: str) -> dict:
    if table not in PROTECTED_TABLES:
        raise ValueError("Table not permitted for fingerprinting")
    with closing(connect_readonly(database)) as connection:
        columns = [item["name"] for item in connection.execute(f'PRAGMA table_info("{table}")')]
        rows = connection.execute(f'SELECT * FROM "{table}" ORDER BY id').fetchall()
    records = {str(row["id"]): hashlib.sha256(json.dumps(
        {column: row[column] for column in columns}, ensure_ascii=False,
        sort_keys=True, default=str, separators=(",", ":"),
    ).encode("utf-8")).hexdigest() for row in rows}
    return {"count": len(records), "ids": sorted(records, key=int), "row_sha256": records}


def policy_rows(database: Path) -> list[tuple]:
    with closing(connect_readonly(database)) as connection:
        rows = connection.execute(
            "SELECT policy_code, policy_name, sort_order, description "
            "FROM roi_policy_config ORDER BY sort_order"
        ).fetchall()
    return [tuple(row) for row in rows]


def database_checks(database: Path) -> dict:
    with closing(connect_readonly(database)) as connection:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        foreign_keys = [tuple(item) for item in connection.execute("PRAGMA foreign_key_check")]
    return {"integrity": integrity, "foreign_key_violations": foreign_keys}
