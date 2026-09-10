import os
from datetime import datetime, timedelta
from types import SimpleNamespace

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, SessionLocal, engine
from app.ad_models import AdPlan
from app.ad_services import evaluate_snapshot, parse_plan_name


client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    market = client.post("/api/markets", json={"name": "Indonesia", "country_code": "ID"}).json()
    product = client.post("/api/products", json={"name": "Sunscreen", "market_id": market["id"]}).json()
    yield {"market_id": market["id"], "product_id": product["id"]}


def test_health_and_asset_crud_and_search(clean_database):
    assert client.get("/api/health").json()["status"] == "ok"
    created = client.post("/api/assets", json={
        "name": "Demo clip", "asset_type": "demo", "source_platform": "TikTok",
        "market_id": clean_database["market_id"], "product_id": clean_database["product_id"],
    }).json()
    item_id = created["id"]
    assert client.get("/api/assets", params={"q": "Demo"}).json()[0]["id"] == item_id
    assert client.put(f"/api/assets/{item_id}", json={"description": "Updated"}).json()["description"] == "Updated"
    assert client.delete(f"/api/assets/{item_id}").status_code == 204
    assert client.get(f"/api/assets/{item_id}").status_code == 404


def test_validation_not_found_and_duplicate_constraint():
    assert client.post("/api/assets", json={}).status_code == 422
    assert client.post("/api/scripts", json={}).status_code == 422
    assert client.get("/api/assets/9999").status_code == 404
    assert client.post("/api/tags", json={"name": "hook"}).status_code == 201
    assert client.post("/api/tags", json={"name": "hook"}).status_code == 409


def test_tag_and_combined_filters(clean_database):
    tag = client.post("/api/tags", json={"name": "problem"}).json()
    asset = client.post("/api/assets", json={
        "name": "Indonesia sunscreen problem", "asset_type": "demo", "source_platform": "TikTok",
        "market_id": clean_database["market_id"], "product_id": clean_database["product_id"], "tag_ids": [tag["id"]],
    }).json()
    result = client.get("/api/assets", params={
        "market_id": clean_database["market_id"], "product_id": clean_database["product_id"],
        "asset_type": "demo", "source_platform": "TikTok", "tag_id": tag["id"], "q": "problem",
    }).json()
    assert [row["id"] for row in result] == [asset["id"]]
    searched = client.get("/api/search", params={
        "q": "sunscreen problem", "entity": "assets", "type": "demo",
        "market_id": clean_database["market_id"], "product_id": clean_database["product_id"], "tag_id": tag["id"],
    }).json()
    assert searched and searched[0]["id"] == asset["id"]


def test_recommendation_returns_four_sections(clean_database):
    common = {"market_id": clean_database["market_id"], "product_id": clean_database["product_id"]}
    client.post("/api/assets", json={"name": "Sunscreen demo", "asset_type": "pain_point", "duration": 20, **common})
    client.post("/api/scripts", json={"title": "Problem hook", "script_type": "pain_point", "duration": 20, **common})
    client.post("/api/templates", json={"name": "Pain point flow", "template_type": "pain_point", "recommended_duration": 20, **common})
    response = client.post("/api/assistant/recommend", json={"content_type": "pain_point", "duration": 20, "keywords": ["sunscreen", "problem"]})
    data = response.json()
    assert set(("assets", "scripts", "templates", "mix_plans")) <= data.keys()
    assert data["assets"][0]["reasons"]
    assert data["mix_plans"] and {"script_id", "template_id", "asset_ids", "reasons"} <= data["mix_plans"][0].keys()
    assert "score_breakdown" in data["mix_plans"][0]

def test_adopt_recommendation_creates_project_and_timeline(clean_database):
    common = {"market_id": clean_database["market_id"], "product_id": clean_database["product_id"]}
    for index in range(3):
        client.post("/api/assets", json={"name": f"Adopt clip {index}", "asset_type": "pain_point", "duration": 3, **common})
    client.post("/api/scripts", json={"title": "Adopt hook", "script_type": "pain_point", "duration": 20, **common})
    client.post("/api/templates", json={"name": "Adopt flow", "template_type": "pain_point", "recommended_duration": 20, **common})
    response = client.post("/api/assistant/adopt", json={"market_id": common["market_id"], "product_id": common["product_id"], "content_type": "pain_point", "duration": 20, "keywords": ["adopt"], "plan_index": 0})
    assert response.status_code == 201
    project = response.json()["project"]
    assert project["id"] and len(project["timeline"]) == 3 and response.json()["plan"]["score_breakdown"]
    assert response.json()["plan"]["timeline"][-1]["end_second"] == 20


def test_clone_duration_filters_and_video_upload(clean_database):
    short = client.post("/api/assets", json={"name": "Short", "duration": 5, **clean_database}).json()
    client.post("/api/assets", json={"name": "Long", "duration": 30, **clean_database})
    filtered = client.get("/api/assets", params={"duration_min": 4, "duration_max": 10}).json()
    assert [row["id"] for row in filtered] == [short["id"]]
    project = client.post("/api/mix-projects", json={"name": "Original", "target_duration": 10, **clean_database}).json()
    client.put(f"/api/mix-projects/{project['id']}/timeline", json=[{"mix_project_id": project["id"], "asset_id": short["id"], "start_second": 0, "end_second": 5}])
    clone = client.post(f"/api/mix-projects/{project['id']}/clone")
    assert clone.status_code == 201 and clone.json()["name"] == "Original - 副本" and len(clone.json()["timeline"]) == 1
    video = client.post("/api/videos", json={"title": "Uploaded", "mix_project_id": clone.json()["id"]}).json()
    uploaded = client.post(f"/api/videos/{video['id']}/file", files={"file": ("result.webm", b"test-video", "video/webm")})
    assert uploaded.status_code == 200 and uploaded.json()["file_path"].endswith(".webm")


def test_mix_project_timeline_and_video_lineage(clean_database):
    common = {"market_id": clean_database["market_id"], "product_id": clean_database["product_id"]}
    script = client.post("/api/scripts", json={"title": "Hook", **common}).json()
    template = client.post("/api/templates", json={"name": "Flow", **common}).json()
    asset_one = client.post("/api/assets", json={"name": "Hook clip", "duration": 3, **common}).json()
    asset_two = client.post("/api/assets", json={"name": "Demo clip", "duration": 5, **common}).json()
    project = client.post("/api/mix-projects", json={"name": "Sunscreen cut", "target_duration": 20, "script_id": script["id"], "template_id": template["id"], **common}).json()
    timeline = [
        {"mix_project_id": project["id"], "asset_id": asset_one["id"], "start_second": 0, "end_second": 3, "usage_type": "hook"},
        {"mix_project_id": project["id"], "asset_id": asset_two["id"], "start_second": 3, "end_second": 8, "usage_type": "product"},
    ]
    saved = client.put(f"/api/mix-projects/{project['id']}/timeline", json=timeline)
    assert saved.status_code == 200 and [x["asset"]["id"] for x in saved.json()["timeline"]] == [asset_one["id"], asset_two["id"]]
    assert client.put(f"/api/mix-projects/{project['id']}/timeline", json=[{**timeline[0], "end_second": 0}]).status_code == 422
    assert client.put(f"/api/mix-projects/{project['id']}/timeline", json=[{**timeline[0], "end_second": 21}]).status_code == 422
    assert client.put(f"/api/mix-projects/{project['id']}/timeline", json=[timeline[0], {**timeline[1], "start_second": 2}]).status_code == 422
    video = client.post("/api/videos", json={"title": "Sunscreen cut", "mix_project_id": project["id"], **common}).json()
    version = client.post(f"/api/videos/{video['id']}/versions", json={"change_note": "initial", "snapshot": {"project_id": project["id"]}}).json()
    assert version["version"] == 1 and version["is_latest"] is True
    assert client.get("/api/videos", params={"mix_project_id": project["id"]}).json()[0]["id"] == video["id"]
    assert client.get(f"/api/videos/{video['id']}/lineage").json()["mix_project"]["id"] == project["id"]


def test_asset_delete_cascades_mix_relation(clean_database):
    asset = client.post("/api/assets", json={"name": "Disposable clip", **clean_database}).json()
    project = client.post("/api/mix-projects", json={"name": "Project", "target_duration": 10, **clean_database}).json()
    relation = client.post("/api/mix-project-assets", json={"mix_project_id": project["id"], "asset_id": asset["id"]})
    assert relation.status_code == 201
    assert client.delete(f"/api/assets/{asset['id']}").status_code == 204
    assert client.get("/api/mix-project-assets").json() == []


def test_asset_lineage_endpoint(clean_database):
    asset = client.post("/api/assets", json={"name": "Lineage clip", **clean_database}).json()
    project = client.post("/api/mix-projects", json={"name": "Lineage project", **clean_database}).json()
    client.post("/api/mix-project-assets", json={"mix_project_id": project["id"], "asset_id": asset["id"]})
    video = client.post("/api/videos", json={"title": "Lineage video", "mix_project_id": project["id"]}).json()
    result = client.get(f"/api/assets/{asset['id']}/lineage")
    assert result.status_code == 200 and result.json()["mix_projects"][0]["videos"][0]["id"] == video["id"]


def test_hybrid_search_and_version_lineage(clean_database):
    client.post("/api/assets", json={"name": "Indonesia sunscreen texture", "description": "lightweight SPF demo", **clean_database})
    result = client.get("/api/search", params={"q": "lightweight sunscreen", "entity": "assets"}).json()
    assert result and "semantic_score" in result[0] and "final_score" in result[0]


def _csv_file(rows):
    header = "广告计划,市场,产品,消耗,订单,销售额,实际ROI,预算,策略,客单价,目标ROI\n"
    return (header + "\n".join(",".join(str(value) for value in row) for row in rows)).encode("utf-8-sig")


def test_ad_import_creates_snapshots_and_classifies_alerts(clean_database):
    rows = [
        ("Burn plan", "Indonesia", "Sunscreen", 120, 0, 0, 0, 200, "A", 50, 1.5),
        ("Low ROI plan", "Indonesia", "Sunscreen", 10, 1, 10, 0.5, 200, "A", 50, 1.5),
        ("Idle plan", "Indonesia", "Sunscreen", 0, 0, 0, "", 200, "A", 50, 1.5),
    ]
    response = client.post("/api/ads/import", files={"file": ("ads.csv", _csv_file(rows), "text/csv")})
    assert response.status_code == 201
    assert response.json()["snapshots"] == 3
    plans = {item["plan_name"]: item for item in client.get("/api/ads/plans").json()}
    assert plans["Burn plan"]["current_status"] == "empty_burn"
    assert plans["Low ROI plan"]["current_status"] == "target_roi_pending"
    assert plans["Idle plan"]["current_status"] == "insufficient_data"
    updated = client.patch(f"/api/ads/plans/{plans['Low ROI plan']['id']}/target-roi", json={"target_roi": 1.5})
    assert updated.status_code == 200 and updated.json()["current_status"] == "low_roi"
    client.patch(f"/api/ads/plans/{plans['Burn plan']['id']}/target-roi", json={"target_roi": 2.7})
    second = client.post("/api/ads/import", files={"file": ("ads.csv", _csv_file([( "Burn plan", "Indonesia", "Sunscreen", 5, 1, 10, 2, 200, "A", 50, 1.5)]), "text/csv")})
    assert second.status_code == 201
    assert len(client.get("/api/ads/snapshots", params={"ad_plan_id": plans["Burn plan"]["id"]}).json()) == 2
    assert len(client.get("/api/ads/import-batches").json()) == 2
    assert client.get(f"/api/ads/plans/{plans['Burn plan']['id']}").json()["target_roi"] == 2.7


def test_ad_rule_priority_missing_values_and_plan_name_parser():
    now = datetime.utcnow()
    plan = SimpleNamespace(target_roi=2.0, created_at=now - timedelta(hours=25))
    assert evaluate_snapshot(plan, 0, 0, 0, now)[0] == "no_spend"
    assert evaluate_snapshot(plan, 2.5, 0, 0, now)[0] == "empty_burn"
    assert evaluate_snapshot(plan, 1.5, 1, 2.2, now)[0] == "roi_reached"
    assert evaluate_snapshot(plan, 1.5, 1, 1.6, now)[0] == "low_roi"
    assert evaluate_snapshot(plan, 1.5, 0, 0, now)[0] != "empty_burn"
    assert evaluate_snapshot(plan, 3, 0, 0, now)[0] == "empty_burn"
    assert evaluate_snapshot(plan, None, 0, 0, now)[0] == "insufficient_data"
    assert evaluate_snapshot(plan, 1, None, 0, now)[0] == "insufficient_data"
    assert evaluate_snapshot(SimpleNamespace(target_roi=None, created_at=now), 1, 1, 0, now)[0] == "target_roi_pending"
    assert parse_plan_name("A*9.7微波炉蒸蛋器0.82") == ("A", "微波炉蒸蛋器")
    assert parse_plan_name("B*9.7接线端子0.36 0.47") == ("B", "接线端子")
    assert parse_plan_name("C*9.8微波炉蒸蛋器1.23")[0] is None


def test_each_ad_plan_keeps_its_own_target_roi(clean_database):
    rows = [
        ("A*9.7微波炉蒸蛋器0.82", "Indonesia", "", 1.5, 1, 3, 2.0, 10, "A", "", 99),
        ("B*9.7微波炉蒸蛋器0.82", "Indonesia", "", 1.5, 1, 3, 2.0, 10, "B", "", 88),
    ]
    assert client.post("/api/ads/import", files={"file": ("ads.csv", _csv_file(rows), "text/csv")}).status_code == 201
    plans = {item["strategy_code"]: item for item in client.get("/api/ads/plans").json()}
    assert plans["A"]["target_roi"] is None and plans["B"]["target_roi"] is None
    assert client.patch(f"/api/ads/plans/{plans['A']['id']}/target-roi", json={"target_roi": 2.0}).status_code == 200
    assert client.patch(f"/api/ads/plans/{plans['B']['id']}/target-roi", json={"target_roi": 2.4}).status_code == 200
    reloaded = {item["strategy_code"]: item for item in client.get("/api/ads/plans").json()}
    assert reloaded["A"]["target_roi"] == 2.0
    assert reloaded["B"]["target_roi"] == 2.4
    assert reloaded["A"]["current_status"] == "roi_reached"
    assert reloaded["B"]["current_status"] == "low_roi"
    assert client.patch(f"/api/ads/plans/{plans['A']['id']}/variant", json={"strategy_code": "B"}).json()["strategy_code"] == "B"
    assert client.patch(f"/api/ads/plans/{plans['A']['id']}/variant", json={"strategy_code": "C"}).status_code == 422


def test_product_variant_target_setting_applies_across_campaign_dates(clean_database):
    a_setting = client.post("/api/ads/target-roi-settings", json={
        "product_name": "微波炉蒸蛋器", "strategy_code": "A", "target_roi": 2.0,
    })
    b_setting = client.post("/api/ads/target-roi-settings", json={
        "product_name": "微波炉蒸蛋器", "strategy_code": "B", "target_roi": 2.4,
    })
    assert a_setting.status_code == 201 and b_setting.status_code == 201
    assert client.post("/api/ads/target-roi-settings", json={
        "product_name": " 微波炉蒸蛋器 ", "strategy_code": "A", "target_roi": 3,
    }).status_code == 409
    rows = [
        ("A*9.5微波炉蒸蛋器0.76", "", "", 1.5, 1, 3, 2.1, 10, "", "", ""),
        ("A*9.7微波炉蒸蛋器0.82", "", "", 1.5, 1, 3, 2.1, 10, "", "", ""),
        ("B*9.6微波炉蒸蛋器0.76", "", "", 1.5, 1, 3, 2.1, 10, "", "", ""),
        ("B*9.8微波炉蒸蛋器0.82", "", "", 1.5, 1, 3, 2.1, 10, "", "", ""),
    ]
    assert client.post("/api/ads/import", files={"file": ("ads.csv", _csv_file(rows), "text/csv")}).status_code == 201
    plans = client.get("/api/ads/plans").json()
    assert {item["target_roi"] for item in plans if item["strategy_code"] == "A"} == {2.0}
    assert {item["target_roi"] for item in plans if item["strategy_code"] == "B"} == {2.4}
    assert {item["current_status"] for item in plans if item["strategy_code"] == "A"} == {"roi_reached"}
    assert {item["current_status"] for item in plans if item["strategy_code"] == "B"} == {"low_roi"}
    updated = client.put(f"/api/ads/target-roi-settings/{a_setting.json()['id']}", json={
        "product_name": "微波炉蒸蛋器", "strategy_code": "A", "target_roi": 2.2,
    })
    assert updated.status_code == 200 and updated.json()["affected_plans"] == 2
    reloaded = client.get("/api/ads/plans").json()
    assert {item["target_roi"] for item in reloaded if item["strategy_code"] == "A"} == {2.2}


def test_zero_spend_becomes_alert_only_after_24_hours(clean_database):
    rows = [("A*9.7课桌挂钩0.23", "Indonesia", "", 0, 0, 0, 0, 10, "A", "", "")]
    imported = client.post("/api/ads/import", files={"file": ("ads.csv", _csv_file(rows), "text/csv")}).json()
    plan_id = client.get("/api/ads/plans").json()[0]["id"]
    assert client.get(f"/api/ads/plans/{plan_id}").json()["current_status"] == "insufficient_data"
    with SessionLocal() as db:
        db.get(AdPlan, plan_id).created_at = datetime.utcnow() - timedelta(hours=25)
        db.commit()
    assert client.get(f"/api/ads/plans/{plan_id}").json()["current_status"] == "no_spend"
    workbench = client.get("/api/workbench/today").json()
    assert any(item["id"] == plan_id for item in workbench["ad_alerts"])
    assert imported["snapshots"] == 1


def test_ad_import_rejects_invalid_file(clean_database):
    response = client.post("/api/ads/import", files={"file": ("ads.pdf", b"not supported", "application/pdf")})
    assert response.status_code == 400
    broken = client.post("/api/ads/import", files={"file": ("ads.xlsx", b"not a workbook", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert broken.status_code == 400


def test_non_alert_ad_statuses_do_not_enter_workbench(clean_database):
    pending = client.post("/api/ads/plans", json={"plan_name": "Pending target", "current_status": "target_roi_pending"}).json()
    reached = client.post("/api/ads/plans", json={"plan_name": "Reached target", "current_status": "roi_reached"}).json()
    workbench = client.get("/api/workbench/today").json()
    alert_ids = {item["id"] for item in workbench["ad_alerts"]}
    assert pending["id"] not in alert_ids and reached["id"] not in alert_ids
    task_ids = {item["related_id"] for item in workbench["tasks"] if item["task_type"] == "ad_alert"}
    assert pending["id"] not in task_ids and reached["id"] not in task_ids


def test_workbench_and_operation_record_validation(clean_database):
    plan = client.post("/api/ads/plans", json={"plan_name": "Review plan", "current_status": "low_roi"}).json()
    workbench = client.get("/api/workbench/today")
    assert workbench.status_code == 200
    assert any(item["id"] == plan["id"] for item in workbench.json()["ad_alerts"])
    invalid = client.post("/api/operations", json={"ad_plan_id": plan["id"], "operation_type": "unknown"})
    assert invalid.status_code == 422
    missing = client.post("/api/operations", json={"ad_plan_id": 9999, "operation_type": "direct_stop"})
    assert missing.status_code == 404
    created = client.post("/api/operations", json={"ad_plan_id": plan["id"], "operation_type": "direct_stop", "reason": "empty burn"})
    assert created.status_code == 201
    assert client.get("/api/operations", params={"ad_plan_id": plan["id"]}).json()[0]["operation_type"] == "direct_stop"
    updated = client.put(f"/api/operations/{created.json()['id']}", json={"ad_plan_id": plan["id"], "operation_type": "rebuild_target_roi", "old_target_roi": 2, "new_target_roi": 2.4, "reason": "updated"})
    assert updated.status_code == 200 and updated.json()["new_target_roi"] == 2.4


def test_daily_work_tasks_are_persisted_and_idempotent(clean_database):
    plan = client.post("/api/ads/plans", json={"plan_name": "Alert plan", "current_status": "low_roi"}).json()
    first = client.get("/api/work-tasks", params={"task_date": "2026-09-09"})
    assert first.status_code == 200
    tasks = first.json()
    assert len([item for item in tasks if item["source"] == "sop"]) == 13
    assert len([item for item in tasks if item["task_type"] == "ad_alert" and item["related_id"] == plan["id"]]) == 1
    second = client.post("/api/work-tasks/generate", params={"task_date": "2026-09-09"})
    assert second.status_code == 200 and len(second.json()) == len(tasks)
    morning_customer = [item for item in tasks if item["title"] == "客服消息"]
    evening_customer = [item for item in tasks if item["title"] == "客服消息复查"]
    assert morning_customer and evening_customer
    task_id = morning_customer[0]["id"]
    updated = client.patch(f"/api/work-tasks/{task_id}/status", json={"status": "completed", "notes": "已完成检查"})
    assert updated.status_code == 200 and updated.json()["completed_at"]
    assert client.get(f"/api/work-tasks/{task_id}").json()["status"] == "completed"
    assert client.patch(f"/api/work-tasks/{task_id}/status", json={"status": "bad"}).status_code == 422
    summary = client.get("/api/workbench/today", params={"task_date": "2026-09-09"}).json()["task_summary"]
    assert summary["total"] >= 13 and summary["completion_rate"] == round(100 / summary["total"], 2)

    assert client.delete(f"/api/work-tasks/{task_id}").status_code == 204
    regenerated = client.get("/api/work-tasks", params={"task_date": "2026-09-09"}).json()
    assert not any(item["id"] == task_id for item in regenerated)
    assert len([item for item in regenerated if item["source"] == "sop"]) == 12

    manual = client.post("/api/work-tasks", json={"title": "Temporary task", "task_type": "content_task", "task_date": "2026-09-09", "source": "manual"}).json()
    assert client.delete(f"/api/work-tasks/{manual['id']}").status_code == 204
    assert client.get(f"/api/work-tasks/{manual['id']}").status_code == 404


def test_workbench_returns_persisted_tasks_for_requested_date(clean_database):
    response = client.get("/api/workbench/today", params={"task_date": "2026-09-10"})
    assert response.status_code == 200
    data = response.json()
    assert data["date"] == "2026-09-10"
    assert len(data["tasks"]) >= 13
    assert all("id" in item and "priority" in item for item in data["tasks"])
    assert "completion_rate" in data["task_summary"]
