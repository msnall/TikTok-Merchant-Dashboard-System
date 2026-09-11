from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .ad_models import AdImportBatch, AdPlan, AdPlanSnapshot, AdStrategy, AdTargetRoiSetting, OperationRecord
from .ad_schemas import AdPlanCreate, AdPlanVariantUpdate, AdStrategyCreate, AdTargetRoiSettingPayload, OperationCreate, TargetRoiUpdate
from .ad_services import VALID_STRATEGY_CODES, apply_target_setting, clear_target_setting, import_rows, latest_snapshot, normalize_product_name, parse_upload, recompute_plan_status
from .db import get_db
from .main_helpers import serialize
from .models import Market, Product
from .work_models import WorkTask

router = APIRouter(prefix="/api", tags=["advertising"])


def serialize_plan(item: AdPlan):
    data = serialize(item)
    snapshot = latest_snapshot(item)
    data["latest_snapshot"] = serialize(snapshot) if snapshot else None
    return data


@router.get("/ads/plans")
def list_ad_plans(status: str | None = None, q: str | None = None, product_id: int | None = None,
                  strategy_code: str | None = None, db: Session = Depends(get_db)):
    stmt = select(AdPlan).order_by(AdPlan.id.desc())
    items = db.scalars(stmt).all()
    for item in items:
        recompute_plan_status(item)
    db.commit()
    if status:
        items = [item for item in items if item.current_status == status]
    if q:
        query = q.strip().casefold()
        items = [item for item in items if query in item.plan_name.casefold()
                 or query in (item.imported_product_name or "").casefold()
                 or query in (item.platform_campaign_id or "").casefold()]
    if product_id is not None:
        items = [item for item in items if item.product_id == product_id]
    if strategy_code:
        items = [item for item in items if item.strategy_code == strategy_code]
    return [serialize_plan(item) for item in items]

@router.post("/ads/plans", status_code=201)
def create_ad_plan(payload: AdPlanCreate, db: Session = Depends(get_db)):
    item = AdPlan(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return serialize(item)

@router.get("/ads/plans/{plan_id}")
def get_ad_plan(plan_id: int, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item: raise HTTPException(404, "广告计划不存在")
    recompute_plan_status(item); db.commit()
    data = serialize_plan(item); data["snapshots"] = [serialize(row) for row in sorted(item.snapshots, key=lambda row: row.snapshot_at, reverse=True)]; return data

@router.put("/ads/plans/{plan_id}")
def update_ad_plan(plan_id: int, payload: AdPlanCreate, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item: raise HTTPException(404, "广告计划不存在")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return serialize(item)


@router.patch("/ads/plans/{plan_id}/target-roi")
def update_target_roi(plan_id: int, payload: TargetRoiUpdate, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item:
        raise HTTPException(404, "广告计划不存在")
    if item.imported_product_name and item.strategy_code in VALID_STRATEGY_CODES and payload.target_roi is not None:
        product_key = normalize_product_name(item.imported_product_name)
        setting = db.scalar(select(AdTargetRoiSetting).where(
            AdTargetRoiSetting.product_key == product_key,
            AdTargetRoiSetting.strategy_code == item.strategy_code,
        ))
        if setting is None:
            setting = AdTargetRoiSetting(product_name=item.imported_product_name, product_key=product_key,
                                         strategy_code=item.strategy_code, target_roi=payload.target_roi)
            db.add(setting); db.flush()
        else:
            setting.product_name = item.imported_product_name
            setting.target_roi = payload.target_roi
        apply_target_setting(db, setting)
    else:
        item.target_roi = payload.target_roi
        recompute_plan_status(item)
    db.commit(); db.refresh(item)
    return serialize_plan(item)


@router.patch("/ads/plans/{plan_id}/variant")
def update_plan_variant(plan_id: int, payload: AdPlanVariantUpdate, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item:
        raise HTTPException(404, "广告计划不存在")
    item.strategy_code = payload.strategy_code
    setting = None
    if item.imported_product_name and payload.strategy_code:
        setting = db.scalar(select(AdTargetRoiSetting).where(
            AdTargetRoiSetting.product_key == normalize_product_name(item.imported_product_name),
            AdTargetRoiSetting.strategy_code == payload.strategy_code,
        ))
    item.target_roi = setting.target_roi if setting else None
    recompute_plan_status(item)
    db.commit(); db.refresh(item)
    return serialize_plan(item)


@router.get("/ads/target-roi-settings")
def list_target_roi_settings(db: Session = Depends(get_db)):
    stmt = select(AdTargetRoiSetting).order_by(AdTargetRoiSetting.product_name, AdTargetRoiSetting.strategy_code)
    return [serialize(item) for item in db.scalars(stmt).all()]


@router.post("/ads/target-roi-settings", status_code=201)
def create_target_roi_setting(payload: AdTargetRoiSettingPayload, db: Session = Depends(get_db)):
    product_name = payload.product_name.strip()
    product_key = normalize_product_name(product_name)
    existing = db.scalar(select(AdTargetRoiSetting).where(
        AdTargetRoiSetting.product_key == product_key,
        AdTargetRoiSetting.strategy_code == payload.strategy_code,
    ))
    if existing:
        raise HTTPException(409, "该产品和 A/B/C/D 类型已经配置目标 ROI")
    item = AdTargetRoiSetting(product_name=product_name, product_key=product_key,
                              strategy_code=payload.strategy_code, target_roi=payload.target_roi)
    db.add(item); db.flush()
    affected_plans = apply_target_setting(db, item)
    db.commit(); db.refresh(item)
    data = serialize(item); data["affected_plans"] = affected_plans
    return data


@router.put("/ads/target-roi-settings/{setting_id}")
def update_target_roi_setting(setting_id: int, payload: AdTargetRoiSettingPayload, db: Session = Depends(get_db)):
    item = db.get(AdTargetRoiSetting, setting_id)
    if not item:
        raise HTTPException(404, "目标 ROI 配置不存在")
    old_product_key = item.product_key
    old_strategy_code = item.strategy_code
    product_name = payload.product_name.strip()
    product_key = normalize_product_name(product_name)
    duplicate = db.scalar(select(AdTargetRoiSetting).where(
        AdTargetRoiSetting.product_key == product_key,
        AdTargetRoiSetting.strategy_code == payload.strategy_code,
        AdTargetRoiSetting.id != setting_id,
    ))
    if duplicate:
        raise HTTPException(409, "该产品和 A/B/C/D 类型已经配置目标 ROI")
    if old_product_key != product_key or old_strategy_code != payload.strategy_code:
        clear_target_setting(db, old_product_key, old_strategy_code)
    item.product_name = product_name
    item.product_key = product_key
    item.strategy_code = payload.strategy_code
    item.target_roi = payload.target_roi
    affected_plans = apply_target_setting(db, item)
    db.commit(); db.refresh(item)
    data = serialize(item); data["affected_plans"] = affected_plans
    return data


@router.delete("/ads/target-roi-settings/{setting_id}", status_code=204)
def delete_target_roi_setting(setting_id: int, db: Session = Depends(get_db)):
    item = db.get(AdTargetRoiSetting, setting_id)
    if not item:
        raise HTTPException(404, "目标 ROI 配置不存在")
    clear_target_setting(db, item.product_key, item.strategy_code)
    db.delete(item); db.commit()

@router.delete("/ads/plans/{plan_id}", status_code=204)
def delete_ad_plan(plan_id: int, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item: raise HTTPException(404, "广告计划不存在")
    db.query(WorkTask).filter(
        WorkTask.related_type == "ad_plan", WorkTask.related_id == plan_id
    ).delete(synchronize_session=False)
    db.delete(item); db.commit()

@router.get("/ads/snapshots")
def list_snapshots(ad_plan_id: int | None = None, import_batch_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(AdPlanSnapshot).order_by(AdPlanSnapshot.id.desc())
    if ad_plan_id: stmt = stmt.where(AdPlanSnapshot.ad_plan_id == ad_plan_id)
    if import_batch_id: stmt = stmt.where(AdPlanSnapshot.import_batch_id == import_batch_id)
    return [serialize(item) for item in db.scalars(stmt).all()]

@router.get("/ads/import-batches")
def list_import_batches(db: Session = Depends(get_db)):
    return [serialize(item) for item in db.scalars(select(AdImportBatch).order_by(AdImportBatch.id.desc())).all()]

@router.post("/ads/import", status_code=201)
async def import_ads(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename = file.filename or "advertising-data.xlsx"
    try: rows = parse_upload(filename, await file.read())
    except ValueError as exc: raise HTTPException(400, str(exc)) from exc
    if not rows: raise HTTPException(400, "文件没有可导入的数据")
    try:
        batch = import_rows(db, filename, rows, db.scalars(select(Market)).all(), db.scalars(select(Product)).all())
        db.commit(); db.refresh(batch)
    except ValueError as exc:
        db.rollback()
        raise HTTPException(400, str(exc)) from exc
    return {"batch": serialize(batch), "plans": len(db.scalars(select(AdPlan)).all()), "snapshots": len(batch.snapshots)}

@router.get("/ad-strategies")
def list_strategies(product_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(AdStrategy).order_by(AdStrategy.id.desc())
    if product_id: stmt = stmt.where(AdStrategy.product_id == product_id)
    return [serialize(item) for item in db.scalars(stmt).all()]

@router.post("/ad-strategies", status_code=201)
def create_strategy(payload: AdStrategyCreate, db: Session = Depends(get_db)):
    if not db.get(Product, payload.product_id): raise HTTPException(404, "产品不存在")
    item = AdStrategy(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return serialize(item)

@router.get("/operations")
def list_operations(ad_plan_id: int | None = None, db: Session = Depends(get_db)):
    stmt = select(OperationRecord).order_by(OperationRecord.operated_at.desc())
    if ad_plan_id: stmt = stmt.where(OperationRecord.ad_plan_id == ad_plan_id)
    return [serialize(item) for item in db.scalars(stmt).all()]

@router.post("/operations", status_code=201)
def create_operation(payload: OperationCreate, db: Session = Depends(get_db)):
    if not db.get(AdPlan, payload.ad_plan_id): raise HTTPException(404, "广告计划不存在")
    item = OperationRecord(**payload.model_dump()); db.add(item); db.commit(); db.refresh(item); return serialize(item)

@router.delete("/operations/{operation_id}", status_code=204)
def delete_operation(operation_id: int, db: Session = Depends(get_db)):
    item = db.get(OperationRecord, operation_id)
    if not item: raise HTTPException(404, "运营记录不存在")
    db.delete(item); db.commit()

@router.put("/operations/{operation_id}")
def update_operation(operation_id: int, payload: OperationCreate, db: Session = Depends(get_db)):
    item = db.get(OperationRecord, operation_id)
    if not item: raise HTTPException(404, "运营记录不存在")
    if not db.get(AdPlan, payload.ad_plan_id): raise HTTPException(404, "广告计划不存在")
    for key, value in payload.model_dump().items(): setattr(item, key, value)
    db.commit(); db.refresh(item); return serialize(item)
