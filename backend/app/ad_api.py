from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session
from .ad_models import AdImportBatch, AdPlan, AdPlanSnapshot, AdStrategy, OperationRecord
from .ad_schemas import AdPlanCreate, AdPlanVariantUpdate, AdStrategyCreate, OperationCreate, TargetRoiUpdate
from .ad_services import import_rows, latest_snapshot, parse_upload, recompute_plan_status
from .db import get_db
from .main_helpers import serialize
from .models import Market, Product

router = APIRouter(prefix="/api", tags=["advertising"])


def serialize_plan(item: AdPlan):
    data = serialize(item)
    snapshot = latest_snapshot(item)
    data["latest_snapshot"] = serialize(snapshot) if snapshot else None
    return data

@router.get("/ads/plans")
def list_ad_plans(status: str | None = None, db: Session = Depends(get_db)):
    stmt = select(AdPlan).order_by(AdPlan.id.desc())
    items = db.scalars(stmt).all()
    for item in items:
        recompute_plan_status(item)
    db.commit()
    if status:
        items = [item for item in items if item.current_status == status]
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
    db.commit(); db.refresh(item)
    return serialize_plan(item)

@router.delete("/ads/plans/{plan_id}", status_code=204)
def delete_ad_plan(plan_id: int, db: Session = Depends(get_db)):
    item = db.get(AdPlan, plan_id)
    if not item: raise HTTPException(404, "广告计划不存在")
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
    batch = import_rows(db, filename, rows, db.scalars(select(Market)).all(), db.scalars(select(Product)).all()); db.commit(); db.refresh(batch)
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
