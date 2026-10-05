import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
import subprocess
import sys

import pytest
from sqlalchemy import create_engine, inspect, select, text
from sqlalchemy.orm import Session

from app.db import Base
from app import models, ad_models, work_models
from app.ai.models import AIAnalysisRun, CampaignMetricTimeseries, CampaignVideoMetric, RoiPolicyConfig
from app.ai.excel_adapter import normalize_campaign_row, normalize_video_row, read_sheet_rows
from app.ai.history import list_analysis_history, save_analysis
from app.ai.rule_engine import (
    Decision, OrderStatus, ROIStatus, VideoStatus, build_decision,
    classify_order_status, classify_roi_status, classify_video_status,
    get_roi_policy, parse_campaign_name_roi,
)


ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "fixtures" / "ai_decision_cases.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["case_id"])
def test_evaluation_case(case):
    assert case["source_type"] == case["campaign"]["source_type"] == "synthetic_demo"
    if case["video"]:
        assert case["video"]["source_type"] == "synthetic_demo"
    result = build_decision(case["campaign"], case["video"])
    for key, expected in case["expected"].items():
        if key == "not_decision":
            assert result["decision"] != expected
        else:
            assert result[key] == expected
    assert result["requires_human_confirmation"] is True
    assert result == build_decision(case["campaign"], case["video"])


def test_name_roi_and_policy_are_not_profit_formulas():
    assert parse_campaign_name_roi("A*9.10某产品0.82") == {"link_type": "A", "target_roi": 0.82}
    assert parse_campaign_name_roi("B*9.10某产品1.02") == {"link_type": "B", "target_roi": 1.02}
    assert parse_campaign_name_roi("A*9.8地板清洁片 0.48 0.66")["target_roi"] == 0.66
    assert parse_campaign_name_roi("A*9.10")["target_roi"] is None
    assert get_roi_policy("A") == "break_even"
    assert get_roi_policy("B") == "profit_5pct"
    assert get_roi_policy("C") is None


def test_rule_boundaries_and_unknowns():
    assert classify_order_status(0) == OrderStatus.ZERO_ORDER
    assert classify_order_status(1) == classify_order_status(9) == OrderStatus.FEW_ORDERS
    assert classify_order_status(10) == OrderStatus.NORMAL_ORDERS
    assert classify_order_status(None) == OrderStatus.UNKNOWN
    video = {"source_type": "synthetic_demo", "ctr": 0.0201, "cvr": 0.1001,
             "official_completion_rate": 0.3001}
    assert classify_video_status(video) == VideoStatus.VIDEO_NORMAL
    for key, boundary in (("ctr", 0.02), ("cvr", 0.10), ("official_completion_rate", 0.30)):
        assert classify_video_status({**video, key: boundary}) == VideoStatus.VIDEO_POOR
    assert classify_video_status({**video, "official_completion_rate": None}) == VideoStatus.UNKNOWN
    assert classify_video_status({**video, "source_type": "uploaded_source"}) == VideoStatus.UNKNOWN
    assert classify_roi_status(0.71, 0.82) == ROIStatus.BELOW_TARGET
    assert classify_roi_status(0.91, 0.82) == ROIStatus.ABOVE_TARGET
    assert classify_roi_status(0.82, 0.82) == ROIStatus.NEAR_TARGET
    assert classify_roi_status(0.80, 0.82, roi_near_threshold=0.03) == ROIStatus.NEAR_TARGET
    assert classify_roi_status(None, 0.82) == ROIStatus.UNKNOWN


def test_empty_burn_is_separate_from_legacy_status():
    case = CASES[0]["campaign"]
    assert build_decision({**case, "spend": 3.0})["decision"] != Decision.EMPTY_BURN
    result = build_decision(case)
    assert result["decision"] == Decision.EMPTY_BURN
    assert result["recommended_action"] == Decision.CLOSE_REBUILD_KEEP_ROI
    assert "EMPTY_BURN_USD_3" in result["rules_used"]
    assert build_decision({**case, "currency": "IDR"})["decision"] != Decision.EMPTY_BURN
    assert build_decision({**case, "currency": None})["decision"] != Decision.EMPTY_BURN


def test_missing_policy_value_is_never_invented():
    case = CASES[3]
    result = build_decision(case["campaign"], case["video"])
    assert result["roi_policy_change"] == {"from": "profit_5pct", "to": "profit_10pct"}
    assert result["target_roi_value"] is None
    assert any("未配置" in item for item in result["uncertainties"])
    configured = build_decision(case["campaign"], case["video"],
                                policy_target_roi_values={"profit_10pct": 1.22})
    assert configured["target_roi_value"] == 1.22


def test_mismatched_or_unverified_video_is_unknown():
    case = CASES[2]
    mismatched = build_decision(case["campaign"], {**case["video"], "campaign_id": "other"})
    assert mismatched["video_status"] == VideoStatus.UNKNOWN
    assert mismatched["decision"] == Decision.INSUFFICIENT_DATA
    unverified = build_decision(
        {**case["campaign"], "source_type": "uploaded_source"},
        {**case["video"], "source_type": "uploaded_source", "source_field_name": None},
    )
    assert unverified["video_status"] == VideoStatus.UNKNOWN


def test_excel_adapter_keeps_unconfirmed_completion_unknown():
    raw = {"Video ID": "V1", "Campaign ID": "C1", "报告日期": "2026-09-10",
           "CTR": 0.026, "CVR": 0.113, "官方完播率": 0.36}
    unknown = normalize_video_row(raw, "uploaded_source", "unverified-template.xlsx")
    assert unknown["official_completion_rate"] is None
    assert unknown["source_field_name"] is None
    synthetic = normalize_video_row(raw, "synthetic_demo", "demo-fixture.xlsx")
    assert synthetic["official_completion_rate"] == 0.36
    assert synthetic["source_type"] == "synthetic_demo"
    with pytest.raises(ValueError, match="source_type"):
        normalize_video_row({**raw, "source_type": "uploaded_source"}, "synthetic_demo", "demo.xlsx")
    workbook = ROOT / "data" / "demo" / "TikTok_AI跨境运营Agent_统一输入与建议模板_v2.xlsx"
    campaign_rows = read_sheet_rows(workbook, "Campaign_Analysis", 1, 2)
    assert campaign_rows
    parsed = normalize_campaign_row(campaign_rows[1], "synthetic_demo")
    assert parsed["link_type"] == "A" and parsed["target_roi"] == 0.82


def test_analysis_runs_append_and_snapshot_inputs(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'analysis.db').as_posix()}")
    Base.metadata.create_all(engine)
    campaign = dict(CASES[2]["campaign"])
    video = dict(CASES[2]["video"])
    result = build_decision(campaign, video)
    with Session(engine) as db:
        first = save_analysis(db, campaign, video, {"file": "synthetic-case.json"}, result)
        first_id = first.id
        campaign["spend"] = 9
        second = save_analysis(db, campaign, video, {"file": "synthetic-case-v2.json"},
                               build_decision(campaign, video))
        assert first_id != second.id
        old = db.get(AIAnalysisRun, first_id)
        assert json.loads(old.snapshot.campaign_data)["spend"] == 6
        assert json.loads(old.snapshot.video_data)["official_completion_rate"] == 0.36
        assert json.loads(old.snapshot.source_information)["file"] == "synthetic-case.json"
        assert list_analysis_history(db) == []
        assert len(list_analysis_history(db, include_synthetic=True)) == 2
        assert db.scalar(select(CampaignVideoMetric)) is None
        assert db.scalar(select(CampaignMetricTimeseries)) is None
    engine.dispose()


def test_independent_video_metrics_and_synthetic_timeseries(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'metrics.db').as_posix()}")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        metric = CampaignVideoMetric(
            campaign_id="synthetic-C001", video_id="synthetic-V001", video_work_id=None,
            report_date=date(2026, 9, 10), impressions=1000, clicks=26, ctr=0.026,
            orders=3, cvr=0.113, spend=2.1, revenue=3.2,
            official_completion_rate=0.36, source_field_name="synthetic_fixed",
            source_document="ai_decision_cases.json", source_type="synthetic_demo",
        )
        db.add(metric)
        for hour, spend in enumerate((2.1, 4.2, 7.8, 9.7, 9.9, 10.0)):
            db.add(CampaignMetricTimeseries(
                campaign_id="synthetic-C001", timestamp=datetime(2026, 9, 10, 9) + timedelta(hours=hour),
                spend=spend, orders=hour, revenue=float(hour), measurement_type="cumulative",
                source_type="synthetic_demo",
            ))
        db.commit()
        assert db.scalar(select(CampaignVideoMetric)).video_work_id is None
        samples = db.scalars(select(CampaignMetricTimeseries).order_by(CampaignMetricTimeseries.timestamp)).all()
        assert [row.spend for row in samples] == [2.1, 4.2, 7.8, 9.7, 9.9, 10.0]
        assert all(row.source_type == "synthetic_demo" for row in samples)
        assert "R005" not in build_decision(CASES[2]["campaign"], CASES[2]["video"])["rules_used"]
    engine.dispose()


def test_migration_round_trip_on_isolated_database(tmp_path):
    database = tmp_path / "migration.db"
    env = {**os.environ, "DATABASE_URL": f"sqlite:///{database.as_posix()}"}
    backend = ROOT / "backend"

    def alembic(*args):
        completed = subprocess.run([sys.executable, "-m", "alembic", *args], cwd=backend,
                                   env=env, capture_output=True, text=True)
        assert completed.returncode == 0, completed.stdout + completed.stderr

    alembic("upgrade", "0009_script_timeline")
    engine = create_engine(env["DATABASE_URL"])
    with engine.begin() as connection:
        connection.execute(text("INSERT INTO markets (name, country_code) VALUES ('MigrationMarker', 'ZZ')"))
    alembic("upgrade", "head")
    with engine.connect() as connection:
        policies = connection.execute(text("SELECT policy_code FROM roi_policy_config ORDER BY sort_order")).scalars().all()
        assert policies == ["break_even", "profit_5pct", "profit_10pct"]
        assert connection.execute(text("SELECT count(*) FROM markets WHERE name='MigrationMarker'")).scalar() == 1
    alembic("downgrade", "0010_ai_decision_foundation")
    table_names = inspect(engine).get_table_names()
    assert "ai_state_transitions" not in table_names
    assert "decision_actions" not in table_names
    assert "ai_analysis_runs" in table_names
    assert "report_date" in {column["name"] for column in inspect(engine).get_columns("ad_plan_snapshots")}
    alembic("upgrade", "head")
    with engine.connect() as connection:
        assert connection.execute(text("SELECT count(*) FROM markets WHERE name='MigrationMarker'")).scalar() == 1
        assert connection.execute(text("SELECT count(*) FROM ai_analysis_runs")).scalar() == 0
    engine.dispose()
