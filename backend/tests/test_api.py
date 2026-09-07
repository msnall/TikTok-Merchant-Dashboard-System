import os

os.environ["DATABASE_URL"] = "sqlite:///./test.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db import Base, engine


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
    client.post("/api/assets", json={"name": "Adopt clip", "asset_type": "pain_point", "duration": 3, **common})
    client.post("/api/scripts", json={"title": "Adopt hook", "script_type": "pain_point", "duration": 20, **common})
    client.post("/api/templates", json={"name": "Adopt flow", "template_type": "pain_point", "recommended_duration": 20, **common})
    response = client.post("/api/assistant/adopt", json={"market_id": common["market_id"], "product_id": common["product_id"], "content_type": "pain_point", "duration": 20, "keywords": ["adopt"], "plan_index": 0})
    assert response.status_code == 201
    project = response.json()["project"]
    assert project["id"] and project["timeline"] and response.json()["plan"]["score_breakdown"]


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
