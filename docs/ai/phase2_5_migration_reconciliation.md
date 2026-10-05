# Phase 2.5 SQLite migration reconciliation

## Scope and backup

- Source: `backend/content_system.db` (`sqlite:///./content_system.db` from the backend directory).
- Repository head: `0010_ai_decision_foundation`; source `alembic_version`: `0009_script_timeline`.
- Backup directory: `backup/phase2_5_before_migration/` (Git-ignored).
- `content_system.original.db` is a byte-for-byte copy; its SHA-256 matched the source immediately after copying. `content_system.consistent.db` was created with SQLite's online backup API. Both copies passed `PRAGMA integrity_check = ok`, recorded version `0009`, and contained 3 runs plus 3 snapshots.
- `manifest.json`, `alembic_version.json`, `schema_dump.sql`, `row_counts.json`, and `pragma_snapshot.json` preserve source path, hash, version, complete `sqlite_master` SQL, row counts, and exact `PRAGMA table_info` / `foreign_key_list` / `index_list` / `index_info` for all six objects. These backup artifacts may contain schema or local business identifiers; do not commit them.

No write, migration, stamp, or downgrade was executed against the source database.

## Expected by migration 0010

`0010` adds nullable `report_date DATE`, `report_start_at DATETIME`, and `report_end_at DATETIME` to `ad_plan_snapshots`; creates the five AI tables below; creates named non-unique indexes on video `(campaign_id, video_id, report_date, source_type)`, timeseries `(campaign_id, timestamp, source_type)`, and runs `(campaign_id, source_type)` as individual indexes; and inserts three ROI policies. There are no server defaults on the newly created AI tables. `created_at` columns are `NOT NULL` but are populated by application-side defaults, not database server defaults.

Notation: `!` means `NOT NULL`; unmarked columns are nullable. Every `id INTEGER!` is the primary key.

| Object | Expected columns from 0010 | Key, FK, unique and checks |
| --- | --- | --- |
| `roi_policy_config` | `id INTEGER!`, `policy_code VARCHAR(32)!`, `policy_name VARCHAR(80)!`, `sort_order INTEGER!`, `description TEXT!` | Unique `policy_code` and `sort_order`; no FK/check |
| `campaign_video_metrics` | `id INTEGER!`, `campaign_id VARCHAR(64)!`, `video_id VARCHAR(128)!`, `video_work_id INTEGER`, `report_date DATE!`, `impressions INTEGER`, `clicks INTEGER`, `ctr FLOAT`, `orders INTEGER`, `cvr FLOAT`, `spend FLOAT`, `revenue FLOAT`, `official_completion_rate FLOAT`, `source_field_name VARCHAR(128)`, `source_document VARCHAR(255)`, `source_type VARCHAR(30)!`, `created_at DATETIME!` | `video_work_id → video_works.id ON DELETE SET NULL`; `ck_campaign_video_source` |
| `campaign_metric_timeseries` | `id INTEGER!`, `campaign_id VARCHAR(64)!`, `timestamp DATETIME!`, `spend FLOAT!`, `orders INTEGER!`, `revenue FLOAT!`, `measurement_type VARCHAR(20)!`, `source_type VARCHAR(30)!`, `created_at DATETIME!` | `ck_campaign_timeseries_source`; `ck_timeseries_measurement` restricts measurement type to `cumulative` or `interval` |
| `ai_analysis_runs` | `id INTEGER!`, `campaign_id VARCHAR(64)!`, `analysis_time DATETIME!`, `input_spend FLOAT`, `input_orders INTEGER`, `input_revenue FLOAT`, `input_current_roi FLOAT`, `input_target_roi FLOAT`, `input_ctr FLOAT`, `input_cvr FLOAT`, `input_completion_rate FLOAT`, `decision VARCHAR(40)!`, `rules_used TEXT!`, `facts TEXT!`, `recommendations TEXT!`, `uncertainties TEXT!`, `source_type VARCHAR(30)!`, `created_at DATETIME!` | `ck_analysis_run_source`; no FK/unique |
| `ai_analysis_snapshots` | `id INTEGER!`, `run_id INTEGER!`, `campaign_data TEXT!`, `video_data TEXT!`, `source_information TEXT!`, `created_at DATETIME!` | `run_id → ai_analysis_runs.id ON DELETE CASCADE`; named unique `uq_analysis_snapshot_run(run_id)` |

All three `source_type` checks use `IN ('uploaded_source', 'manual_entry', 'synthetic_demo')`. The expected policy seeds are:

| code | name | order | description |
| --- | --- | ---: | --- |
| `break_even` | 保本 ROI | 1 | 政策标签；具体目标数值由计划名或人工配置提供 |
| `profit_5pct` | 5% 利润 ROI | 2 | 政策标签；不在系统中推导利润公式 |
| `profit_10pct` | 10% 利润 ROI | 3 | 政策标签；具体目标数值待人工配置 |

## Actual schema and differences

The complete actual DDL and PRAGMA output are in the backup files named above. A clean temporary SQLite database migrated through 0009 and 0010 supplied the expected physical schema for comparison. Columns were compared by name, type, nullable, database default and primary key; foreign keys, unique constraints, named indexes and CHECK constraints were compared separately. Column order was not treated as a semantic difference.

| object | expected by 0010 | actual db | status |
| --- | --- | --- | --- |
| All five AI tables | Exist with the columns, types, nullability, PK/FK/unique/indexes listed above | All exist; those attributes match exactly | `schema_already_present` except below |
| `campaign_metric_timeseries` | Both `ck_campaign_timeseries_source` and `ck_timeseries_measurement` | Source-type CHECK exists; **measurement-type CHECK absent** | **MISSING CONSTRAINT** |
| `roi_policy_config` | Three policy seed rows | **0 rows** | **MISSING SEED** |
| `ad_plan_snapshots.report_date` | `DATE NULL`, no server default | `DATE NULL`, no server default | `schema_already_present` |
| `ad_plan_snapshots.report_start_at` / `report_end_at` | `DATETIME NULL`, no server default | Both `DATETIME NULL`, no server default | `schema_already_present` |
| `ad_plan_snapshots.snapshot_at` | Existing 0009 column remains `DATETIME NULL`, no server default | `DATETIME NOT NULL`, no server default | **PRE-EXISTING SCHEMA DRIFT** |
| `ad_plan_snapshots.status` | Existing 0009 column remains `VARCHAR(40) NOT NULL DEFAULT 'unknown'` | `VARCHAR(40) NOT NULL`, **no server default** | **PRE-EXISTING SCHEMA DRIFT** |
| `alembic_version` | `0010_ai_decision_foundation` after a successful migration | `0009_script_timeline` | **VERSION NOT RECONCILED** |

The actual AI tables closely match SQLAlchemy `Base.metadata.create_all()` output. The application startup and `seed.py` both call `create_all`; the current `ad_plan_snapshots` column order also follows the ORM model rather than 0010's append order. The missing seed and version prove 0010 did not finish. SQLite does not record DDL provenance, so the precise event creating each table or the three report columns cannot be proved from the database alone.

## Existing analysis data

| Run ID | Campaign ID | created_at (stored UTC, timezone-naive) | decision | Snapshot ID |
| ---: | --- | --- | --- | ---: |
| 1 | `01` | `2026-10-03 08:57:20.827940` | `INSUFFICIENT_DATA` | 1 |
| 2 | `01` | `2026-10-03 08:57:58.842250` | `INSUFFICIENT_DATA` | 2 |
| 3 | `02` | `2026-10-03 08:59:31.251779` | `INSUFFICIENT_DATA` | 3 |

All three snapshots reference an existing run; every run has one snapshot. `campaign_data`, `video_data`, and `source_information` are valid, nonempty JSON objects in every snapshot, so the inputs seen by each run remain recoverable. `PRAGMA foreign_key_check` returned no violations. No raw input or sensitive contents are reproduced here.

## Isolated simulation

- Fresh temporary database `simulation_clean.db`: `0009 → 0010 → 0009 → 0010` succeeded; final integrity check `ok`, version `0010`, three policy seeds present, and all three report columns present. This test database never contained analysis records.
- Data-bearing `simulation_existing.db` copied from the consistent backup: attempting original 0010 stopped at its explicit five-table conflict check. It remained at `0009`, passed integrity check, and retained 3 runs plus 3 snapshots.
- Data-bearing `simulation_repaired.db`, derived separately from the consistent backup: an isolated Alembic batch rebuild added only the missing timeseries CHECK and reconciled the two `ad_plan_snapshots` column properties; the three seed rows were inserted verbatim from 0010. A structured comparison against `simulation_clean.db` found the same columns, types, nullability, database defaults, primary keys, foreign keys, unique constraints, named indexes and CHECK constraints for all six objects. The three seed rows also matched 0010 byte-for-byte as database values. A SHA-256 over every column of all 3 runs and 3 snapshots was unchanged before/after repair; `PRAGMA integrity_check = ok`, `PRAGMA foreign_key_check` had no violations. This copy intentionally **remains at 0009**; no version bookkeeping was performed.
- A data-bearing `downgrade -1` was **not** attempted: the original 0010 downgrade explicitly drops both analysis tables and would delete the protected records. A successful empty-database cycle does not prove a lossless data-bearing cycle.
- A final read-only source check found the original database SHA-256 still equal to its initial backup, version still `0009`, and counts still 3+3.

## Reconciliation decision

**Option B: partially present schema. Do not run original 0010 or stamp the source.** The current schema is not equivalent to 0010 because one CHECK, three seed rows, two inherited snapshot-column properties, and the version entry differ. Direct `alembic upgrade head` fails before changes; direct `stamp head` would conceal unresolved differences. A new revision after 0010 cannot be reached from this 0009 database because Alembic must run the conflicting 0010 first; a parallel branch would not produce the requested exact 0010 version. The historical 0010 file must remain unchanged.

Proposed controlled repair, subject to separate approval:

1. Quiesce application writers; re-check source hash/version/counts and take a fresh SQLite online backup. Preserve the 3 runs and 3 snapshots by ID and JSON hash.
2. Apply the **tested-on-copy** one-off reconciliation procedure (not a change to historical 0010): add the missing CHECK by rebuilding the currently empty `campaign_metric_timeseries` table; reconcile `ad_plan_snapshots.snapshot_at` nullability and `status` server default by a data-preserving SQLite table rebuild; insert exactly the three original 0010 policy rows. Re-run the full schema comparison, protected-row hashes, foreign-key and integrity checks. The isolated copy proves the repair is feasible but does not authorize applying it to the source.
3. Only after complete structural and seed equivalence is proved, present the exact version-bookkeeping step for approval. Neither `alembic stamp head` nor a direct `alembic_version` update is authorized by this report. A later migration must not replay 0010 against the reconciled schema.
4. Do **not** rely on original 0010's downgrade for a data-bearing database. A lossless rollback requires restoring a verified pre-repair backup or a separately approved data-preserving rollback procedure.

**Current decision:** the schema, seed, and version reconciliation have passed on an isolated data-bearing copy, but have **not** been applied to the development database. Separate human confirmation is required before any development-database write. A lossless data-bearing `0009 → 0010 → 0009 → 0010` cycle is impossible with the original 0010 downgrade because it drops both analysis tables.

## Version Reconciliation Record

This record describes a **working-copy-only** reconciliation, not a normal execution of historical migration 0010 against the data-bearing database. The machine-readable audit, including per-row SHA-256 values, is at `backup/phase2_5_reconcile/20261003T092700Z_6811e6bf/version_reconciliation_record.json`.

| Item | Recorded result |
| --- | --- |
| Operation time | 2026-10-03 09:27:02 UTC |
| Original / target version | `0009_script_timeline` / `0010_ai_decision_foundation` |
| Backup and working copy | `backup/phase2_5_reconcile/20261003T092700Z_6811e6bf/source_backup.db`; `reconciled_working.db` in the same directory |
| Executor / tool | `backend/scripts/reconcile_phase2_5.py`, using SQLAlchemy/Alembic batch operations and SQLite online backup |
| SchemaEquivalent | TRUE, compared with a separately migrated clean 0010 reference across columns, types, nullability, defaults, PK, FK, unique, indexes, and CHECKs for all six target tables |
| SeedEquivalent | TRUE; exactly the three 0010 ROI policy rows match the clean reference |
| AnalysisDataPreserved | TRUE; run IDs 1-3 and snapshot IDs 1-3 retain identical per-record SHA-256 values before and after repair |
| SQLite checks | `PRAGMA integrity_check = ok`; no foreign-key violations |
| DDL / version bookkeeping | DDL executed **only on the working copy**; its `alembic_version` was updated from 0009 to 0010 only after all checks passed. No DDL or version update was executed on the source. |
| Source status | Source SHA-256 before/after this copy run: `f2fd3532cfa972ee124388628d9929a5eb49b7d0c4ca4c6174aa60143495b551`; `alembic current` remained `0009_script_timeline` |

The working-copy repair added `ck_timeseries_measurement`, restored the 0010-equivalent `snapshot_at` nullability and `status` server default, and inserted the three historical 0010 seeds. It did not edit `0010_ai_decision_foundation.py`, replay 0010 on the populated copy, or use `alembic stamp`. The source still has the schema and seed differences listed above. The original backup under `backup/phase2_5_before_migration/` is retained. If a later, separately approved source reconciliation fails verification, restore a verified pre-repair backup rather than running the destructive 0010 downgrade on populated AI tables.

Regression verification: the isolated migration test in `backend/tests/test_ai_phase0.py` exercises `0009 → 0010 → 0009 → 0010` on a fresh database; the copy-only preservation test in `backend/tests/test_phase2_5_reconciliation.py` passed; after adding test-database isolation, the full backend suite passed with **102 passed, 0 failed**. The source database is **not yet at 0010**. Do not begin live LLM integration until the development-database reconciliation has been separately approved and verified.

### Test-isolation incident and recovery

The first full-suite run in this phase exposed a pre-existing test isolation defect: `test_ai_analysis.py` imported the application before `test_api.py` set `DATABASE_URL`, so `app.db.engine` pointed at `backend/content_system.db`. Later autouse fixtures in `test_api.py` and `test_fill_assistant.py` called `Base.metadata.drop_all(engine)`, clearing the 3 runs and 3 snapshots. This was an unintended development-database write, **not** part of the reconciliation script. The copy-only audit above reflects the database **before** that test run; it must not be read as proof that the first full-suite run left the source unchanged.

After explicit user approval, the backend server was stopped. The cleared database was preserved at `backup/phase2_5_reconcile/incident_20261003_test_isolation/cleared_development.db` (SHA-256 `92d1524d9f46d19c511166fa6b3416859b14d41f90d32a8f12f82551acd41330`). The development database was restored from the verified `source_backup.db` in the working-copy run (SHA-256 `8917ba0d8930f436e8e56e604679048fa3e053994a4b6d0efee687cf2ff045b4`). Post-restoration, its version is `0009_script_timeline`; all 3 runs and 3 snapshots have the same IDs and per-row hashes as the pre-test audit; `PRAGMA integrity_check = ok` and `PRAGMA foreign_key_check` is empty. The backend health endpoint returned `ok` after restart.

`backend/tests/conftest.py` now sets an isolated temporary SQLite URL before test modules import the application; the late environment override in `test_api.py` was removed. A second full-suite run passed **102 tests**, and the development-database SHA-256 did not change during that rerun. No 0010 repair, seed insertion, or version bookkeeping has been applied to the development database.

## Phase 2.5-C: development-database application

The user explicitly approved applying the previously verified reconciliation to the development database. This section supersedes the earlier working-copy-only status above; the earlier entries remain as an audit trail. Historical migration `0010_ai_decision_foundation.py` was not edited or replayed against the populated database. No `alembic stamp` was used.

Before any development-database write, pytest collection showed `app.db.engine` using `C:\Users\woko\AppData\Local\Temp\tiktok-backend-tests-w_3i6x4s\test.db`, distinct from `D:\xiangmuanli\backend\content_system.db`. The backend server was stopped for the operation. The one-time executor was `backend/scripts/apply_phase2_5.py`, reusing the schema repair and validation functions proven on the data-bearing copy. Its complete machine-readable record is `backup/phase2_5_apply_0010/20261003T093857Z_3259d39e/version_reconciliation_record.json`.

| Item | Development-database result |
| --- | --- |
| Operation time | 2026-10-03 09:38:58 UTC |
| Version before / after | `0009_script_timeline` / `0010_ai_decision_foundation`; both `alembic current` and `alembic heads` report 0010 afterward |
| Dedicated pre-apply backup | `backup/phase2_5_apply_0010/20261003T093857Z_3259d39e/before/` contains the byte-for-byte original, SQLite-consistent copy, SHA-256, version, Schema dump, all table row counts, ROI count, and per-record 3+3 hashes |
| Schema repair | Added `ck_timeseries_measurement`; aligned `ad_plan_snapshots.snapshot_at` nullability and `status` server default. The other five AI-table structures and three report-time columns were already present. All six target-table schemas compare equal to a clean 0010 reference, including types, defaults, keys, constraints and indexes. |
| ROI seed | Inserted exactly the three historical policies: `break_even`, `profit_5pct`, `profit_10pct`; all four seed fields match the clean 0010 reference |
| Analysis data | 3 runs and 3 snapshots before and after; IDs and per-record SHA-256 hashes match exactly. All other table row counts are unchanged except `roi_policy_config` from 0 to 3. |
| Version bookkeeping | After SchemaEquivalent, SeedEquivalent, AnalysisDataPreserved and SQLite checks all passed, updated the single `alembic_version` row from 0009 to 0010. This was a **version reconciliation after schema alignment**, not normal execution of the historical 0010 upgrade. |
| Dedicated post-apply backup | `backup/phase2_5_apply_0010/20261003T093857Z_3259d39e/after/` contains the migrated SQLite copy, SHA-256, version, Schema dump, counts, hashes and the three seed rows |
| Database integrity | `PRAGMA integrity_check = ok`; `PRAGMA foreign_key_check` returned no violations |

After restarting the backend, `/api/health`, `/api/ads/plans`, `/api/ai/knowledge/search`, and read-only access to an existing analysis record succeeded. The frontend server returned HTTP 200 for `/`, `/ads`, `/ads/analysis`, and `/ads/knowledge`; this verifies route availability, not a visual browser acceptance test. The ads tables contained no plan or snapshot records before or after reconciliation, so there was no existing ad row to exercise interactively.

The isolated full suite passed **102 passed, 0 failed** after applying the reconciliation. The test database for that run was `C:\Users\woko\AppData\Local\Temp\tiktok-backend-tests-11bafzi8\test.db`, separate from the development database. The development-database SHA-256 was `da86581eed556b65dc0b3c235b143354fc3235572fa7d2582528d9e15e996b5b` both before and after the full test run; protected-row hashes, Schema equivalence, ROI seeds and SQLite integrity remained valid. The backend service was restored and its health endpoint returned `ok`.

**Phase 2.5-C database reconciliation is complete.** The original 0009 backup is retained for recovery. The historical 0010 downgrade still drops the AI analysis tables and must not be used as a lossless rollback on this populated database. No live LLM, Agent, Tool Calling or TikTok operation was performed.
