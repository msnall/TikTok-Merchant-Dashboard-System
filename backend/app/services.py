from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Asset, Script
from .semantic import embed, item_text, stored_embedding, cosine

def _score(item, market_id, product_id, type_value, duration, keywords):
    reasons = []
    market = 1.0 if market_id and getattr(item, "market_id", None) == market_id else 0.0
    product = 1.0 if product_id and getattr(item, "product_id", None) == product_id else 0.0
    score = .30 * market + .25 * product
    if market: reasons.append("市场匹配")
    if product: reasons.append("产品匹配")
    type_field = "script_type" if isinstance(item, Script) else "asset_type"
    type_match = 1.0 if type_value and getattr(item, type_field, None) == type_value else 0.0
    score += .20 * type_match
    if type_match: reasons.append("内容类型匹配")
    query = " ".join(keywords or [])
    semantic = cosine(embed(query), stored_embedding(item)) if query else 0.0
    score += .15 * semantic
    if semantic >= .25: reasons.append("语义相似")
    item_duration = getattr(item, "duration", None) or getattr(item, "recommended_duration", None)
    duration_score = 0.0
    if duration and item_duration is not None:
        duration_score = max(0, 1 - abs(item_duration - duration) / max(duration, 1)); score += .10 * duration_score
        if duration_score >= .75: reasons.append("时长接近目标")
    breakdown = {
        "market": round(.30 * market, 3),
        "product": round(.25 * product, 3),
        "content_type": round(.20 * type_match, 3),
        "semantic": round(.15 * semantic, 3),
        "duration": round(.10 * duration_score, 3),
    }
    return round(min(score, 1), 3), reasons, breakdown

def recommendations(db: Session, market_id=None, product_id=None, content_type=None, duration=None, keywords=None):
    keywords = keywords or []
    result = {}
    for key, model in (("assets", Asset), ("scripts", Script)):
        items = db.scalars(select(model)).all()
        ranked = []
        for item in items:
            score, reasons, breakdown = _score(item, market_id, product_id, content_type, duration, keywords)
            ranked.append({"item": item, "score": score, "reasons": reasons, "score_breakdown": breakdown})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        result[key] = ranked[:10]
    plans = []
    scripts = result["scripts"][:5]
    assets = result["assets"][:10]
    role_asset = {"hook": "usage", "body": "usage", "ending": "result", "cta": "cta"}
    for index, script in enumerate(scripts):
        source_segments = list(script["item"].segments)
        if not source_segments:
            parts = [(role, getattr(script["item"], role, None)) for role in ("hook", "body", "ending", "cta")]
            parts = [(role, text) for role, text in parts if text]
            total = duration or script["item"].duration or 20
            segment_length = total / max(len(parts), 1)
            source_segments = [type("Segment", (), {"id": None, "role": role, "spoken_text": text, "start_second": i * segment_length,
                               "end_second": total if i == len(parts) - 1 else (i + 1) * segment_length,
                               "recommended_asset_type": role_asset[role]}) for i, (role, text) in enumerate(parts)]
        if not source_segments or not assets:
            continue
        script_duration = max((segment.end_second for segment in source_segments), default=duration or 20) or 20
        target_duration = duration or script_duration
        scale = target_duration / script_duration
        chosen_assets = []
        available = list(assets)
        timeline = []
        for segment_index, segment in enumerate(source_segments):
            desired_type = segment.recommended_asset_type or role_asset.get(segment.role)
            pool = available or list(assets)
            ranked_pool = sorted(pool, key=lambda entry: (entry["item"].asset_type == desired_type, entry["score"]), reverse=True)
            chosen = ranked_pool[0]
            if chosen in available:
                available.remove(chosen)
            chosen_assets.append(chosen)
            start = round(segment.start_second * scale, 2)
            end = round(segment.end_second * scale, 2)
            timeline.append({"asset_id": chosen["item"].id, "order_index": segment_index, "start_second": start,
                             "end_second": target_duration if segment_index == len(source_segments) - 1 else end,
                             "usage_type": segment.role, "script_segment_id": segment.id,
                             "script_text_snapshot": segment.spoken_text, "source_start_second": 0,
                             "source_end_second": min(chosen["item"].duration or (end - start), end - start)})
        plan_score = round((script["score"] + sum(item["score"] for item in chosen_assets)) / (1 + len(chosen_assets)), 3)
        plan_reasons = list(dict.fromkeys(script["reasons"] + [reason for item in chosen_assets for reason in item["reasons"]]))
        plans.append({"id": f"script-{script['item'].id}", "score": plan_score, "script_id": script["item"].id, "asset_ids": [item["item"].id for item in chosen_assets], "target_duration": target_duration, "reasons": plan_reasons,
                      "timeline": timeline,
                      "score_breakdown": {key: round((script["score_breakdown"][key] + sum(item["score_breakdown"][key] for item in chosen_assets)) / (1 + len(chosen_assets)), 3) for key in ("market", "product", "content_type", "semantic", "duration")}})
    result["mix_plans"] = plans
    return result
