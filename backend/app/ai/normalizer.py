"""Deterministic normalization for campaign identity fields.

LLM extraction is treated as a candidate source only. Business identity and
target ROI are resolved from the operator text and campaign naming convention.
"""

from __future__ import annotations

import re
from typing import Any

from .text_parser import parse_operator_text


_LINK_POLICY = {"A": "break_even", "B": "profit_5pct"}
CANONICAL_ANALYSIS_FIELDS = (
    "campaign_id", "campaign_name", "link_type", "target_roi", "spend", "orders", "revenue",
    "current_roi", "ctr", "cvr", "official_completion_rate", "spend_pattern", "report_time",
    "currency", "roi_policy",
)
_CAMPAIGN_NAME = re.compile(r"(?<![A-Za-z0-9])([AB])\*\s*([^，。；;\n]+)", re.I)
_EXPLICIT_LINK = re.compile(r"(?<![A-Za-z0-9])([AB])\s*(?:计划投流|计划|链接|链)(?![A-Za-z0-9])", re.I)


def _campaign_name_from_text(text: str) -> str | None:
    match = _CAMPAIGN_NAME.search(text or "")
    return match.group(0).strip() if match else None


def normalize_campaign_identity(text: str, campaign_name: Any = None) -> str | None:
    deterministic = _campaign_name_from_text(text)
    if deterministic:
        return deterministic
    if isinstance(campaign_name, str) and campaign_name.strip():
        candidate = campaign_name.strip()
        if _CAMPAIGN_NAME.search(candidate) and candidate in (text or ""):
            return candidate
    return None


def normalize_link_type(text: str, campaign_name: str | None = None,
                        candidate: Any = None) -> str | None:
    if not campaign_name:
        campaign_name = _campaign_name_from_text(text)
    if campaign_name:
        match = re.match(r"\s*([AB])\s*\*", campaign_name, re.I)
        if match:
            return match.group(1).upper()
    value = text or ""
    if re.search(r"(?:AB\s*测试|产品\s*A\s*/\s*B|A\s*/\s*B)", value, re.I):
        return None
    explicit = _EXPLICIT_LINK.search(value)
    if explicit:
        return explicit.group(1).upper()
    if re.fullmatch(r"\s*([AB])\s*", value, re.I):
        return value.strip().upper()
    if candidate in ("A", "B"):
        # Candidate values are accepted only when the surrounding text has a
        # clear plan/link marker; a bare model guess cannot establish identity.
        if re.search(rf"(?<![A-Za-z0-9]){candidate}\s*(?:计划投流|计划|链接|链)(?![A-Za-z0-9])", value, re.I):
            return str(candidate).upper()
    return None


def normalize_target_roi(campaign_name: str | None, candidate: Any = None,
                         explicit: Any = None) -> float | None:
    deterministic = extract_target_roi_from_campaign_name(campaign_name)
    if deterministic is not None:
        return deterministic
    # Explicit text parsed by our deterministic parser is preferred to an LLM
    # candidate when no usable campaign-name suffix exists.
    for value in (explicit, candidate):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            return float(value)
    return None


def extract_target_roi_from_campaign_name(campaign_name: str | None) -> float | None:
    if not isinstance(campaign_name, str):
        return None
    match = re.match(r"\s*[AB]\s*\*\s*(.+?)\s*$", campaign_name, re.I)
    if not match:
        return None
    remainder = match.group(1)
    number = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", remainder)
    if not number or not re.search(r"[A-Za-z\u4e00-\u9fff]", remainder[:number.start()]):
        return None
    return float(number.group(1))


def normalize_analysis_input(text: str, deterministic: dict[str, Any],
                            llm_extraction: dict[str, Any] | None = None) -> dict[str, Any]:
    """Merge deterministic parser and LLM candidates into Rule Engine input."""
    llm = llm_extraction or {}
    # Always keep the deterministic parser as the first fallback source. This
    # matters when a live model omits an otherwise explicit numeric fact.
    source = dict(deterministic or parse_operator_text(text))
    normalized = {field: source.get(field) for field in CANONICAL_ANALYSIS_FIELDS}
    campaign_name = normalize_campaign_identity(text, normalized.get("campaign_name") or llm.get("campaign_name"))
    link_type = normalize_link_type(text, campaign_name, llm.get("link_type"))
    explicit_target = normalized.get("target_roi")
    if explicit_target is None and not re.search(r"目标\s*(?:ROI)?\s*[:：=为是]?\s*[0-9]", text or ""):
        explicit_target = None
        candidate = None
    else:
        candidate = llm.get("target_roi")
    target_roi = normalize_target_roi(campaign_name, candidate, explicit_target)
    normalized["campaign_name"] = campaign_name
    normalized["link_type"] = link_type
    normalized["target_roi"] = target_roi
    normalized["roi_policy"] = _LINK_POLICY.get(link_type)
    for key in ("spend", "orders", "revenue", "current_roi", "ctr", "cvr",
                "official_completion_rate", "spend_pattern", "report_time"):
        if normalized.get(key) is None and llm.get(key) is not None:
            normalized[key] = llm[key]
    return normalized
