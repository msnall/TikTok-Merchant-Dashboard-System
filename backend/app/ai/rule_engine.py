"""Deterministic operator-experience rules. Nothing here performs account actions."""

from enum import StrEnum
import re


class OrderStatus(StrEnum):
    ZERO_ORDER = "ZERO_ORDER"
    FEW_ORDERS = "FEW_ORDERS"
    NORMAL_ORDERS = "NORMAL_ORDERS"
    UNKNOWN = "UNKNOWN"


class VideoStatus(StrEnum):
    VIDEO_NORMAL = "VIDEO_NORMAL"
    VIDEO_POOR = "VIDEO_POOR"
    UNKNOWN = "UNKNOWN"


class ROIStatus(StrEnum):
    BELOW_TARGET = "BELOW_TARGET"
    NEAR_TARGET = "NEAR_TARGET"
    ABOVE_TARGET = "ABOVE_TARGET"
    UNKNOWN = "UNKNOWN"


class Decision(StrEnum):
    EMPTY_BURN = "EMPTY_BURN"
    CLOSE_REBUILD_KEEP_ROI = "CLOSE_REBUILD_KEEP_ROI"
    CLOSE_REBUILD = "CLOSE_REBUILD"
    CLOSE_REBUILD_LOWER_ROI = "CLOSE_REBUILD_LOWER_ROI"
    CLOSE_REBUILD_RAISE_ROI = "CLOSE_REBUILD_RAISE_ROI"
    WAIT_OBSERVE = "WAIT_OBSERVE"
    SCALE_NEW_PRODUCT = "SCALE_NEW_PRODUCT"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    NEEDS_CONFIRMATION = "NEEDS_CONFIRMATION"


ROI_POLICIES = ("break_even", "profit_5pct", "profit_10pct")


def parse_campaign_name_roi(name: str) -> dict:
    match = re.match(r"^\s*([AB])\*\s*(.+?)\s*$", name or "", re.IGNORECASE)
    if not match:
        return {"link_type": None, "target_roi": None}
    remainder = re.sub(r"^\d{1,2}\.\d{1,2}\s*", "", match.group(2))
    number = re.search(r"(\d+(?:\.\d+)?)\s*$", remainder)
    if not number or not any(character.isalpha() for character in remainder[:number.start()]):
        return {"link_type": match.group(1).upper(), "target_roi": None}
    return {"link_type": match.group(1).upper(), "target_roi": float(number.group(1))}


def get_roi_policy(link_type: str | None) -> str | None:
    return {"A": "break_even", "B": "profit_5pct"}.get((link_type or "").upper())


def classify_order_status(orders: int | None) -> OrderStatus:
    if orders is None or orders < 0:
        return OrderStatus.UNKNOWN
    if orders == 0:
        return OrderStatus.ZERO_ORDER
    return OrderStatus.FEW_ORDERS if orders <= 9 else OrderStatus.NORMAL_ORDERS


def classify_video_status(video: dict | None) -> VideoStatus:
    if not video:
        return VideoStatus.UNKNOWN
    if video.get("source_type") not in {"uploaded_source", "manual_entry", "synthetic_demo"}:
        return VideoStatus.UNKNOWN
    values = (video.get("ctr"), video.get("cvr"), video.get("official_completion_rate"))
    if any(value is None for value in values):
        return VideoStatus.UNKNOWN
    if any(not isinstance(value, (int, float)) or not 0 <= value <= 1 for value in values):
        return VideoStatus.UNKNOWN
    if video.get("source_type") != "synthetic_demo" and (
            not video.get("source_field_name") or not video.get("source_document")):
        return VideoStatus.UNKNOWN
    return (VideoStatus.VIDEO_NORMAL if values[0] > 0.02 and values[1] > 0.10 and values[2] > 0.30
            else VideoStatus.VIDEO_POOR)


def classify_roi_status(current_roi: float | None, target_roi: float | None,
                        roi_near_threshold: float | None = None) -> ROIStatus:
    if current_roi is None or target_roi is None or current_roi < 0 or target_roi < 0:
        return ROIStatus.UNKNOWN
    if roi_near_threshold is not None and roi_near_threshold < 0:
        raise ValueError("roi_near_threshold 不能为负")
    if current_roi == target_roi or (roi_near_threshold is not None and
                                     abs(current_roi - target_roi) <= roi_near_threshold):
        return ROIStatus.NEAR_TARGET
    return ROIStatus.BELOW_TARGET if current_roi < target_roi else ROIStatus.ABOVE_TARGET


def _adjacent_policy(policy: str | None, direction: int) -> str | None:
    if policy not in ROI_POLICIES:
        return None
    index = ROI_POLICIES.index(policy) + direction
    return ROI_POLICIES[index] if 0 <= index < len(ROI_POLICIES) else None


def build_decision(campaign: dict, video: dict | None = None, *,
                   roi_near_threshold: float | None = None,
                   policy_target_roi_values: dict[str, float] | None = None) -> dict:
    source_type = campaign.get("source_type")
    if source_type not in {"uploaded_source", "manual_entry", "synthetic_demo"}:
        raise ValueError("campaign.source_type 必须明确")
    parsed = parse_campaign_name_roi(str(campaign.get("campaign_name") or ""))
    link_type = parsed["link_type"] or campaign.get("link_type")
    policy = get_roi_policy(link_type) or campaign.get("roi_policy")
    target = parsed["target_roi"] if parsed["target_roi"] is not None else campaign.get("target_roi")
    spend, orders, current_roi = (campaign.get(key) for key in ("spend", "orders", "current_roi"))
    order_status = classify_order_status(orders)
    video_status = (VideoStatus.UNKNOWN if video and video.get("source_type") == "synthetic_demo"
                    and source_type != "synthetic_demo" else classify_video_status(video))
    if video and (video.get("campaign_id") != campaign.get("campaign_id") or not video.get("report_date")):
        video_status = VideoStatus.UNKNOWN
    roi_status = classify_roi_status(current_roi, target, roi_near_threshold)
    units = {"currency": "code", "spend": "source_currency", "orders": "count",
             "revenue": "source_currency", "current_roi": "multiple", "target_roi": "multiple"}
    facts = [{"field": key, "value": value, "unit": units[key], "source_type": source_type,
              "report_date": campaign.get("report_date")} for key, value in (
        ("currency", campaign.get("currency")),
        ("spend", spend), ("orders", orders), ("revenue", campaign.get("revenue")),
        ("current_roi", current_roi), ("target_roi", target))]
    if video:
        facts += [{"field": key, "value": video.get(key), "unit": "ratio",
                   "source_type": video.get("source_type"), "report_date": video.get("report_date"),
                   "source_field_name": video.get("source_field_name") if key == "official_completion_rate" else None,
                   "source_document": video.get("source_document")}
                  for key in ("ctr", "cvr", "official_completion_rate")]
    rules = ["R008"] if policy in ROI_POLICIES[:2] and link_type in {"A", "B"} else []
    if video_status == VideoStatus.VIDEO_NORMAL:
        rules.append("R001")
    elif video_status == VideoStatus.VIDEO_POOR:
        rules.append("R002")
    uncertainties = []
    if video_status == VideoStatus.UNKNOWN:
        uncertainties.append("缺失可信视频指标或官方完播率，不能判断视频正常/差")
    if parsed["target_roi"] is not None and campaign.get("target_roi") is not None and campaign["target_roi"] != parsed["target_roi"]:
        uncertainties.append("计划名称目标 ROI 与输入配置不同；本次按计划名称解析值，需人工核对")
    if roi_near_threshold is None:
        uncertainties.append("roi_near_threshold 尚未确认；仅完全相等视为接近")
    if campaign.get("currency") != "USD":
        uncertainties.append("币种不是已确认的 USD，不能套用 3 美元空烧阈值")
    uncertainties.append("缺少已确认的连续时序判定阈值，不能判断消耗趋平")
    decision = Decision.INSUFFICIENT_DATA
    recommendations = []
    policy_change = None
    target_roi_value = None

    if (campaign.get("currency") == "USD" and spend is not None and spend > 3
            and order_status == OrderStatus.ZERO_ORDER):
        rules.append("EMPTY_BURN_USD_3")
        decision = Decision.EMPTY_BURN
        recommendations = [Decision.CLOSE_REBUILD_KEEP_ROI]
    elif order_status == OrderStatus.UNKNOWN or spend is None:
        decision = Decision.INSUFFICIENT_DATA
    elif video_status == VideoStatus.VIDEO_POOR:
        decision = Decision.CLOSE_REBUILD
        recommendations = [Decision.CLOSE_REBUILD]
    elif video_status == VideoStatus.VIDEO_NORMAL:
        if (campaign.get("is_new_product") is True and campaign.get("spend_growth_confirmed") is True
                and campaign.get("orders_normal_confirmed") is True):
            rules.append("R007")
            decision = Decision.SCALE_NEW_PRODUCT
            recommendations = [Decision.SCALE_NEW_PRODUCT]
            uncertainties.append("新品扩量需要人工核对履约和退货；案例预算不是通用规则")
        elif roi_status == ROIStatus.NEAR_TARGET:
            decision = Decision.WAIT_OBSERVE
            recommendations = [Decision.WAIT_OBSERVE]
        elif roi_status == ROIStatus.BELOW_TARGET:
            rules.append("R003")
            policy_change = _adjacent_policy(policy, -1) if order_status == OrderStatus.FEW_ORDERS else None
            decision = (Decision.CLOSE_REBUILD_LOWER_ROI if policy_change else Decision.NEEDS_CONFIRMATION)
            recommendations = [decision]
        elif roi_status == ROIStatus.ABOVE_TARGET:
            rules.append("R004")
            policy_change = _adjacent_policy(policy, 1)
            decision = Decision.CLOSE_REBUILD_RAISE_ROI if policy_change else Decision.NEEDS_CONFIRMATION
            recommendations = [decision]

    if policy_change:
        target_roi_value = (policy_target_roi_values or {}).get(policy_change)
        if target_roi_value is None:
            uncertainties.append("下一策略档位的具体目标 ROI 未配置，不能推导数字")
    result = {
        "campaign_id": campaign.get("campaign_id"), "link_type": link_type,
        "roi_policy": policy, "target_roi": target,
        "order_status": order_status, "video_status": video_status,
        "roi_status": roi_status, "decision": decision,
        "recommended_action": recommendations[0] if recommendations else None,
        "roi_policy_change": {"from": policy, "to": policy_change} if policy_change else None,
        "target_roi_value": target_roi_value,
        "roi_near_threshold_status": ("requires_confirmation" if roi_near_threshold is None else "configured"),
        "facts": facts, "rules_used": rules,
        "inference": [order_status, video_status, roi_status],
        "recommendations": recommendations, "uncertainties": uncertainties,
        "source_type": source_type, "requires_human_confirmation": True,
    }
    return result
