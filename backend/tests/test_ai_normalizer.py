import pytest

from app.ai.normalizer import (
    CANONICAL_ANALYSIS_FIELDS, extract_target_roi_from_campaign_name,
    normalize_analysis_input, normalize_link_type, normalize_target_roi,
)


@pytest.mark.parametrize("text,expected", [
    ("A计划", "A"), ("B计划", "B"), ("A链接", "A"), ("B链接", "B"),
    ("A计划投流", "A"), ("B链", "B"), ("A", "A"), ("B", "B"),
    ("A*9.10产品0.82", "A"), ("B*9.10产品1.02", "B"),
])
def test_normalize_link_type(text, expected):
    assert normalize_link_type(text) == expected


@pytest.mark.parametrize("text", ["AB测试", "产品A/B", "A/B产品描述"])
def test_ambiguous_product_text_does_not_infer_link(text):
    assert normalize_link_type(text) is None


def test_campaign_name_has_priority_and_derives_target_roi():
    text = "A*9.10测试产品0.82，成本8.6美元"
    normalized = normalize_analysis_input(text, {"campaign_name": None}, {"link_type": None, "target_roi": None})
    assert normalized["campaign_name"] == "A*9.10测试产品0.82"
    assert normalized["link_type"] == "A"
    assert normalized["target_roi"] == pytest.approx(0.82)


def test_explicit_plan_works_without_campaign_name_but_target_stays_null():
    normalized = normalize_analysis_input("A计划，成本3.5美元", {}, {"link_type": None, "target_roi": 9.9})
    assert normalized["link_type"] == "A"
    assert normalized["target_roi"] is None


def test_llm_candidate_cannot_override_deterministic_identity():
    normalized = normalize_analysis_input(
        "B*9.10产品1.02", {"campaign_name": None, "link_type": None, "target_roi": None},
        {"campaign_name": "B*9.10产品1.02", "link_type": "A", "target_roi": 0.4},
    )
    assert normalized["link_type"] == "B"
    assert normalized["target_roi"] == pytest.approx(1.02)


def test_normalized_schema_is_canonical_and_missing_values_are_none():
    normalized = normalize_analysis_input("A计划", {}, {"spend": None})
    assert tuple(normalized) == CANONICAL_ANALYSIS_FIELDS
    assert normalized["spend"] is None
    assert normalized["revenue"] is None
    assert normalized["report_time"] is None


def test_target_roi_suffix_and_fallback_candidate():
    assert extract_target_roi_from_campaign_name("A*9.10测试产品0.82") == pytest.approx(0.82)
    assert extract_target_roi_from_campaign_name("B*9.10产品1.02") == pytest.approx(1.02)
    assert normalize_target_roi("A*9.10产品", candidate=0.82) == pytest.approx(0.82)
    assert normalize_target_roi(None, candidate=0.82) == pytest.approx(0.82)
    assert normalize_target_roi(None) is None
