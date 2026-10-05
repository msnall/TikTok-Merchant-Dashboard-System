"""Deterministic data sufficiency assessment, not model confidence."""


def assess_confidence(data: dict, *, historical_delta: dict | None = None) -> tuple[str, list[str]]:
    missing: list[str] = []
    for field in ("spend", "orders", "target_roi"):
        if data.get(field) is None:
            missing.append(field)
    if data.get("current_roi") is None:
        missing.append("current_roi")
    video_missing = [field for field in ("ctr", "cvr", "official_completion_rate")
                    if data.get(field) is None]
    reasons = []
    if missing:
        reasons.append("缺少业务字段: " + ", ".join(missing))
    if video_missing:
        reasons.append("缺少视频指标: " + ", ".join(video_missing))
    if not historical_delta:
        reasons.append("暂无可比较的历史分析")
    if "target_roi" in missing or "spend" in missing or "orders" in missing:
        return "INSUFFICIENT", reasons
    if video_missing or "current_roi" in missing:
        return "MEDIUM", reasons
    if historical_delta:
        return "HIGH", reasons or ["业务字段、视频指标和历史变化均可用"]
    return "MEDIUM", reasons or ["本轮业务字段和视频指标完整，尚无历史对比"]
