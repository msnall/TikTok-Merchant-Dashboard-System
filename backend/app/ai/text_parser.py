"""Conservative extraction of numeric facts from an operator report.

This parser intentionally returns None when a value is not present. It is the
offline fallback for the optional LLM adapter and never makes a business
decision.
"""
from dataclasses import asdict, dataclass
import re

@dataclass
class AnalysisInput:
    campaign_id: str | None = None
    campaign_name: str | None = None
    spend: float | None = None
    orders: int | None = None
    revenue: float | None = None
    current_roi: float | None = None
    target_roi: float | None = None
    ctr: float | None = None
    cvr: float | None = None
    official_completion_rate: float | None = None
    spend_pattern: str | None = None
    report_time: str | None = None
    link_type: str | None = None
    roi_policy: str | None = None
    source_type: str = "manual_entry"
    currency: str | None = None

def _number(text: str, patterns: tuple[str, ...], integer=False):
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            value = float(match.group(1))
            return int(value) if integer else value
    return None

def parse_operator_text(text: str, campaign_id: str | None = None) -> dict:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("text 不能为空")
    value = text.strip()
    link = re.search(r"([AB])\s*(?:计划|链接)", value, re.I)
    name_match = re.search(r"([AB]\*[^，。；;]+)", value, re.I)
    campaign_name = name_match.group(1).strip() if name_match else None
    link_type = link.group(1).upper() if link else (campaign_name[0].upper() if campaign_name else None)
    report_time_match = re.search(r"\b(20\d{2}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?)\b", value)
    target = _number(value, (r"目标\s*(?:ROI)?\s*[:：=为是]?\s*([0-9]+(?:\.[0-9]+)?)",))
    # Preserve the established plan-name convention when a full name is given.
    if campaign_name:
        tail = re.search(r"([0-9]+(?:\.[0-9]+)?)\s*$", campaign_name)
        if tail and re.search(r"[A-Za-z\u4e00-\u9fff]", campaign_name[2:tail.start()]):
            target = float(tail.group(1))
    result = AnalysisInput(
        campaign_id=campaign_id, campaign_name=campaign_name,
        spend=_number(value, (r"(?:成本|消耗|花了|花费|spend)\s*(?:是|为|=)?\s*\$?\s*([0-9]+(?:\.[0-9]+)?)", r"([0-9]+(?:\.[0-9]+)?)\s*(?:刀|美金|美元)")),
        orders=_number(value, (r"(?:订单|订单数|出了|有)\s*(?:是|为|=)?\s*([0-9]+)", r"([0-9]+)\s*(?:单|订单)"), integer=True),
        revenue=_number(value, (r"(?:收入|营收|revenue)\s*(?:是|为|=)?\s*([0-9]+(?:\.[0-9]+)?)",)),
        current_roi=_number(value, (r"(?<!目标)(?:当前|现有)?\s*ROI\s*(?:是|为|=)?\s*([0-9]+(?:\.[0-9]+)?)",)),
        target_roi=target,
        ctr=_number(value, (r"CTR\s*(?:是|为|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",)),
        cvr=_number(value, (r"CVR\s*(?:是|为|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",)),
        official_completion_rate=_number(value, (r"(?:官方)?完播率\s*(?:是|为|=)?\s*([0-9]+(?:\.[0-9]+)?)\s*%?",)),
        spend_pattern="increase_then_flat" if re.search(r"(前面|开始).{0,12}(快|涨).{0,20}(后面|后来).{0,12}(平|不怎么花|不消耗|不动)", value) else None,
        report_time=report_time_match.group(1) if report_time_match else None,
        link_type=link_type,
        roi_policy={"A":"break_even", "B":"profit_5pct"}.get(link_type),
        currency="USD" if re.search(r"刀|美金|美元|\bUSD\b|\$", value, re.I) else None,
    )
    if result.orders is None and re.search(r"一单(?:都)?(?:没|没有)|没有订单|没出单|零单|0\s*单", value):
        result.orders = 0
    return asdict(result)
