from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import Asset, Script, ContentTemplate
from .semantic import embed, item_text, stored_embedding, cosine

def _score(item, market_id, product_id, type_value, duration, keywords):
    reasons = []
    market = 1.0 if market_id and getattr(item, "market_id", None) == market_id else 0.0
    product = 1.0 if product_id and getattr(item, "product_id", None) == product_id else 0.0
    score = .30 * market + .25 * product
    if market: reasons.append("市场匹配")
    if product: reasons.append("产品匹配")
    type_field = "script_type" if isinstance(item, Script) else "template_type" if isinstance(item, ContentTemplate) else "asset_type"
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
    for key, model in (("assets", Asset), ("scripts", Script), ("templates", ContentTemplate)):
        items = db.scalars(select(model)).all()
        ranked = []
        for item in items:
            score, reasons, breakdown = _score(item, market_id, product_id, content_type, duration, keywords)
            ranked.append({"item": item, "score": score, "reasons": reasons, "score_breakdown": breakdown})
        ranked.sort(key=lambda x: x["score"], reverse=True)
        result[key] = ranked[:10]
    plans = []
    scripts = result["scripts"][:3]
    templates = result["templates"][:3]
    assets = result["assets"][:3]
    for index, (script, template) in enumerate(zip(scripts, templates)):
        chosen_assets = assets[index:index + 1] or assets[:1]
        if not chosen_assets: continue
        plan_score = round((script["score"] + template["score"] + sum(item["score"] for item in chosen_assets)) / (2 + len(chosen_assets)), 3)
        plan_reasons = list(dict.fromkeys(script["reasons"] + template["reasons"] + [reason for item in chosen_assets for reason in item["reasons"]]))
        plans.append({"id": f"generated-{index + 1}", "score": plan_score, "script_id": script["item"].id, "template_id": template["item"].id, "asset_ids": [item["item"].id for item in chosen_assets], "target_duration": duration, "reasons": plan_reasons,
                      "score_breakdown": {key: round((script["score_breakdown"][key] + template["score_breakdown"][key] + sum(item["score_breakdown"][key] for item in chosen_assets)) / (2 + len(chosen_assets)), 3) for key in ("market", "product", "content_type", "semantic", "duration")}})
    result["mix_plans"] = plans
    return result
