from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from .ad_models import AdTargetRoiSetting
from .ad_services import apply_target_setting
from .db import get_db
from .fill_assistant_schemas import FillAssistantAnalysis
from .fill_assistant_services import (
    analyze_product_campaign,
    export_consumption_workbook,
    export_payout_workbook,
    parse_payout_config,
)
from .main_helpers import serialize
from .models import Product


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
