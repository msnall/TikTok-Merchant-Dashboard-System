import csv
import io
import re
from datetime import datetime
from .ad_models import AdPlan, AdPlanSnapshot, AdStrategy

ALIASES = {
    "plan_name": ["plan_name", "广告计划", "广告计划名称", "计划名称", "campaign_name", "campaign"],
    "spend": ["spend", "消耗", "花费", "cost"], "orders": ["orders", "订单", "成交订单", "purchases"],
    "revenue": ["revenue", "销售额", "成交金额", "gmv"], "actual_roi": ["actual_roi", "实际roi", "实际 ROI", "roi"],
    "budget": ["budget", "预算"], "product_name": ["product_name", "产品", "产品名称"],
    "market_name": ["market_name", "市场", "国家", "市场名称"], "strategy_code": ["strategy_code", "策略", "策略类型"],
    "target_roi": ["target_roi", "目标roi", "目标 ROI", "目标回报"],
    "product_unit_price": ["product_unit_price", "客单价", "产品客单价", "售价"],
}


def _number(value, default=0.0):
    if value is None or str(value).strip() == "": return default
    try: return float(str(value).replace(",", "").replace("%", ""))
    except (TypeError, ValueError): return default


def _find(row, key):
    normalized = {re.sub(r"[\s_\-]", "", str(k)).lower(): v for k, v in row.items()}
    for alias in ALIASES[key]:
        value = normalized.get(re.sub(r"[\s_\-]", "", alias).lower())
        if value is not None: return value
    return None


def parse_upload(filename: str, content: bytes):
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if suffix in {"csv", "txt"}:
        text = content.decode("utf-8-sig", errors="replace")
        return list(csv.DictReader(io.StringIO(text)))
    if suffix in {"xlsx", "xlsm"}:
        try:
            from openpyxl import load_workbook
        except ImportError as exc:
            raise ValueError("解析 xlsx 需要安装 openpyxl：pip install openpyxl") from exc
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        sheet = workbook.active; rows = sheet.iter_rows(values_only=True); headers = [str(x or "") for x in next(rows, ())]
        return [dict(zip(headers, values)) for values in rows if any(value is not None for value in values)]
    raise ValueError("仅支持 .xlsx、.xlsm 或 .csv 文件")


def evaluate_snapshot(ad_plan, spend, orders, actual_roi):
    target = ad_plan.target_roi or 0
    price = ad_plan.product_unit_price or 0
    if spend > price > 0 and orders <= 0: return "empty_burn", "消耗已超过产品客单价但没有有效订单", "建议回 TikTok 检查素材，考虑关停并重建"
    if spend > 0 and target > 0 and actual_roi is not None and actual_roi < target: return "low_roi", "实际 ROI 低于产品策略目标", "建议回 TikTok 检查，必要时重建并调整目标 ROI"
    if spend <= 0: return "no_spend", "当前快照没有消耗", "建议确认计划是否正常投放"
    return "normal", "当前快照未触发配置规则", "继续观察"


def import_rows(db, filename, rows, markets, products):
    from .ad_models import AdImportBatch
    batch = AdImportBatch(file_name=filename, row_count=len(rows), status="completed"); db.add(batch); db.flush()
    for row in rows:
        name = str(_find(row, "plan_name") or "").strip()
        if not name: continue
        product_name = str(_find(row, "product_name") or "").strip()
        market_name = str(_find(row, "market_name") or "").strip()
        product = next((p for p in products if p.name == product_name), None)
        market = next((m for m in markets if m.name == market_name or m.country_code == market_name), None)
        plan = db.query(AdPlan).filter(AdPlan.plan_name == name).first()
        strategy_code = _find(row, "strategy_code")
        imported_target = _number(_find(row, "target_roi"), None)
        imported_price = _number(_find(row, "product_unit_price"), None)
        if not plan:
            plan = AdPlan(plan_name=name, product_id=product.id if product else None, market_id=market.id if market else None,
                          strategy_code=strategy_code, target_roi=imported_target, product_unit_price=imported_price)
            db.add(plan); db.flush()
        elif imported_target is not None:
            plan.target_roi = imported_target
        elif plan.target_roi is None and product and strategy_code:
            strategy = db.query(AdStrategy).filter(AdStrategy.product_id == product.id, AdStrategy.strategy_code == strategy_code, AdStrategy.enabled.is_(True)).first()
            if strategy:
                plan.target_roi = strategy.base_target_roi * strategy.multiplier
        if plan.product_unit_price is None and imported_price is not None:
            plan.product_unit_price = imported_price
        spend = _number(_find(row, "spend")); orders = int(_number(_find(row, "orders"), 0)); revenue = _number(_find(row, "revenue")); roi = _number(_find(row, "actual_roi"), revenue / spend if spend else 0) if (_find(row, "actual_roi") is not None or spend) else None
        status, reason, recommendation = evaluate_snapshot(plan, spend, orders, roi)
        snapshot = AdPlanSnapshot(ad_plan_id=plan.id, import_batch_id=batch.id, spend=spend, orders=orders, revenue=revenue, actual_roi=roi, budget=_number(_find(row, "budget"), None), status=status, reason=reason, recommendation=recommendation)
        db.add(snapshot); plan.current_status = status
    return batch
