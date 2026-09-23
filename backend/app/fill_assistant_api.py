from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .ad_models import AdTargetRoiSetting
from .ad_services import apply_target_setting
from .db import get_db
from .fill_assistant_schemas import AffiliateFeeAnalysis, FillAssistantAnalysis, SalesDataAnalysis
from .fill_assistant_services import (
    analyze_affiliate_fees,
    analyze_product_campaign,
    analyze_sales_data,
    export_affiliate_fee_workbook,
    export_consumption_workbook,
    export_payout_workbook,
    export_sales_data_workbook,
    parse_payout_config,
    parse_product_code_mappings,
)
from .main_helpers import serialize
from .models import Product, ProductCodeMapping


router = APIRouter(prefix="/api/fill-assistant", tags=["fill-assistant"])


@router.post("/analyze", response_model=FillAssistantAnalysis)
async def analyze(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or "product-campaign.xlsx"
    settings = db.scalars(select(AdTargetRoiSetting)).all()
    products = [item.name for item in db.scalars(select(Product)).all()]
    try:
        return analyze_product_campaign(filename, await file.read(), settings, products)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/affiliate-fees/analyze", response_model=AffiliateFeeAnalysis)
async def analyze_affiliate_fee_file(file: UploadFile = File(...)):
    filename = file.filename or "affiliate-orders.csv"
    try:
        return analyze_affiliate_fees(filename, await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get("/sales/product-codes")
def product_code_status(db: Session = Depends(get_db)):
    return {
        "total": db.scalar(select(func.count(ProductCodeMapping.id))) or 0,
        "updated_at": db.scalar(select(func.max(ProductCodeMapping.updated_at))),
    }


@router.post("/sales/product-codes")
async def import_product_codes(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or "产品编码.xlsx"
    try:
        parsed = parse_product_code_mappings(filename, await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    current = {item.sellersku: item for item in db.scalars(select(ProductCodeMapping)).all()}
    created = 0
    updated = 0
    unchanged = 0
    try:
        for seller_sku, name in parsed["mappings"].items():
            mapping = current.get(seller_sku)
            if mapping is None:
                db.add(ProductCodeMapping(sellersku=seller_sku, name=name))
                created += 1
            elif mapping.name != name:
                mapping.name = name
                updated += 1
            else:
                unchanged += 1
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "filename": filename,
        "source_rows": parsed["source_rows"],
        "unique_mappings": len(parsed["mappings"]),
        "duplicate_rows": parsed["duplicate_rows"],
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "total_saved": db.scalar(select(func.count(ProductCodeMapping.id))) or 0,
    }


@router.post("/sales/analyze", response_model=SalesDataAnalysis)
async def analyze_sales_file(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or "全部订单.csv"
    mappings = {
        item.sellersku: item.name
        for item in db.scalars(select(ProductCodeMapping)).all()
    }
    try:
        return analyze_sales_data(filename, await file.read(), mappings)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post("/import-payout-config")
async def import_payout_config(file: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        rows = parse_payout_config(await file.read())
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    created = 0
    updated = 0
    affected_plans = 0
    try:
        for row in rows:
            setting = db.scalar(select(AdTargetRoiSetting).where(
                AdTargetRoiSetting.product_key == row["product_key"],
                AdTargetRoiSetting.strategy_code == row["strategy_code"],
            ))
            if setting is None:
                setting = AdTargetRoiSetting(**{key: row[key] for key in ("product_name", "product_key", "strategy_code", "target_roi")})
                db.add(setting); db.flush(); created += 1
            else:
                setting.product_name = row["product_name"]
                setting.target_roi = row["target_roi"]
                updated += 1
            affected_plans += apply_target_setting(db, setting)
        db.commit()
    except Exception:
        db.rollback()
        raise
    settings = db.scalars(select(AdTargetRoiSetting).order_by(
        AdTargetRoiSetting.product_name, AdTargetRoiSetting.strategy_code
    )).all()
    return {
        "imported": len(rows), "created": created, "updated": updated,
        "affected_plans": affected_plans, "settings": [serialize(item) for item in settings],
    }


@router.post("/export-consumption")
def export_consumption(payload: FillAssistantAnalysis):
    return StreamingResponse(
        export_consumption_workbook(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="full-consumption.xlsx"'},
    )


@router.post("/export-payout")
def export_payout(payload: FillAssistantAnalysis):
    return StreamingResponse(
        export_payout_workbook(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="estimated-payout.xlsx"'},
    )


@router.post("/affiliate-fees/export")
def export_affiliate_fee(payload: AffiliateFeeAnalysis):
    return StreamingResponse(
        export_affiliate_fee_workbook(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="affiliate-fee-summary.xlsx"'},
    )


@router.post("/sales/export")
def export_sales_data(payload: SalesDataAnalysis):
    return StreamingResponse(
        export_sales_data_workbook(payload),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="sales-data.xlsx"'},
    )
