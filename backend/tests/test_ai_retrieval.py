from fastapi.testclient import TestClient
import pytest
import json
from pathlib import Path

from app.ai.knowledge import KNOWLEDGE_PATH, load_knowledge, parse_knowledge
from app.ai.retrieval import search_knowledge
from app.main import app

CASES = json.loads((Path(__file__).parent / "fixtures" / "ai_retrieval_cases.json").read_text(encoding="utf-8"))


client = TestClient(app)


def test_loads_existing_versioned_rules():
    assert KNOWLEDGE_PATH.name == "AI运营决策知识库_V0.1.md"
    chunks = load_knowledge()
    ids = {chunk.rule_id for chunk in chunks}
    assert set(f"R{i:03}" for i in range(1, 9)) <= ids
    assert "EMPTY_BURN_USD_3" in ids
    assert len(ids) == len(chunks)
    for chunk in chunks:
        assert chunk.knowledge_id and chunk.title and chunk.content
        assert chunk.version == "V0.1"
        assert chunk.source_type == "operator_experience"
        assert chunk.business_scope and chunk.conditions and chunk.action and chunk.uncertainty


@pytest.mark.parametrize(("query", "expected"), [
    ("空烧怎么判断？", "EMPTY_BURN_USD_3"),
    ("视频正常但是ROI低怎么办？", "R003"),
    ("ROI高于目标怎么办？", "R004"),
    ("消耗突然增加然后不再消耗怎么办？", "R005"),
    ("新品跑起来之后怎么办？", "R007"),
])
def test_business_queries_recall_rule(query, expected):
    assert expected in {item["rule_id"] for item in search_knowledge(query)}


def test_long_query_recalls_both_relevant_rules():
    ids = {item["rule_id"] for item in search_knowledge("视频数据正常，但是当前ROI低于目标ROI应该怎么办？")}
    assert {"R003", "R006"} <= ids


def test_source_filter_top_k_and_no_match():
    assert search_knowledge("ROI", top_k=2) and len(search_knowledge("ROI", top_k=2)) == 2
    assert search_knowledge("ROI", source_type="synthetic_demo") == []
    assert search_knowledge("ROI", source_type="official_platform_definition") == []
    assert search_knowledge("量子纠缠和星系形成有什么关系？") == []
    assert search_knowledge("", top_k=5) == []


def test_structured_parser_rejects_duplicate_rule_ids():
    text = KNOWLEDGE_PATH.read_text(encoding="utf-8")
    first = text[text.index("## R001 "):text.index("## R002 ")]
    with pytest.raises(ValueError, match="重复"):
        parse_knowledge(text + "\n" + first)


def test_get_and_post_api_include_citations():
    for response in (
        client.get("/api/ai/knowledge/search", params={"query": "空烧", "top_k": 1}),
        client.post("/api/ai/knowledge/search", json={"query": "空烧", "top_k": 1}),
    ):
        assert response.status_code == 200
        body = response.json()
        assert body["query"] == "空烧"
        assert len(body["results"]) == 1
        result = body["results"][0]
        assert result["rule_id"] == "EMPTY_BURN_USD_3"
        assert result["source_type"] == "operator_experience"
        assert result["version"] == "V0.1"
        assert 0 < result["score"] <= 1


def test_api_invalid_parameters_and_empty_results():
    assert client.get("/api/ai/knowledge/search", params={"query": ""}).status_code == 422
    assert client.get("/api/ai/knowledge/search", params={"query": "ROI", "top_k": 0}).status_code == 422
    assert client.post("/api/ai/knowledge/search", json={"query": "ROI", "source_type": "invented"}).status_code == 422
    response = client.post("/api/ai/knowledge/search", json={"query": "量子纠缠和星系形成有什么关系？"})
    assert response.status_code == 200 and response.json()["results"] == []


def test_real_world_evaluation_dataset_is_valid_and_unknown_stays_empty():
    assert len(CASES) >= 20
    for case in CASES:
        assert case["source_type"] == "operator_experience"
        assert set(case["expected_rule_ids"]) <= set(case["acceptable_rule_ids"])
        result_ids = {item["rule_id"] for item in search_knowledge(case["query"], top_k=5)}
        if not case["expected_rule_ids"]:
            assert result_ids == set()
