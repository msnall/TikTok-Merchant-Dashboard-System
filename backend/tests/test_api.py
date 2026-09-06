import os
os.environ["DATABASE_URL"] = "sqlite:///./test.db"
from fastapi.testclient import TestClient
from app.main import app
from app.db import Base, engine

Base.metadata.drop_all(engine); Base.metadata.create_all(engine)
client = TestClient(app)

def test_health():
    assert client.get("/api/health").json()["status"] == "ok"

def test_asset_crud_and_search():
    created = client.post("/api/assets", json={"name":"Demo clip", "asset_type":"demo", "source_platform":"TikTok"}).json()
    assert created["name"] == "Demo clip"
    item_id = created["id"]
    assert client.get("/api/assets", params={"q":"Demo"}).json()[0]["id"] == item_id
    assert client.put(f"/api/assets/{item_id}", json={"description":"Updated"}).json()["description"] == "Updated"
    assert client.delete(f"/api/assets/{item_id}").status_code == 204

def test_recommendation():
    client.post("/api/assets", json={"name":"Sunscreen demo", "asset_type":"demo", "market_id":1, "product_id":1, "duration":20})
    response = client.post("/api/assistant/recommend", json={"market_id":1,"product_id":1,"content_type":"demo","duration":20,"keywords":["sunscreen"]})
    assert "assets" in response.json()
    assert "reasons" in response.json()["assets"][0]

def test_hybrid_search_and_version_lineage():
    asset = client.post("/api/assets", json={"name":"Indonesia sunscreen texture", "description":"lightweight SPF demo", "market_id":1, "product_id":1}).json()
    result = client.get("/api/search", params={"q":"lightweight sunscreen", "entity":"assets"}).json()
    assert result and "semantic_score" in result[0] and "final_score" in result[0]
    video = client.post("/api/videos", json={"title":"Sunscreen cut v1"}).json()
    version = client.post(f"/api/videos/{video['id']}/versions", json={"change_note":"initial cut", "snapshot":{"asset_id":asset["id"]}}).json()
    assert version["version"] == 1 and version["is_latest"] is True
