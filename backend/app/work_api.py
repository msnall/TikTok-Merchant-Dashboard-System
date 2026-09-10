from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import get_db
from .main_helpers import serialize
from .work_models import WorkTask
from .work_schemas import TASK_PRIORITIES, TASK_STATUSES, TASK_TYPES, WorkTaskPayload, WorkTaskStatusPayload
from .work_services import ensure_daily_tasks

router = APIRouter(prefix="/api/work-tasks", tags=["work-tasks"])
legacy_router = APIRouter(prefix="/api/workbench/tasks", tags=["work-tasks"])


def _validate_values(payload):
    if payload.task_type not in TASK_TYPES:
        raise HTTPException(422, "不支持的任务类型")
    if payload.status not in TASK_STATUSES:
        raise HTTPException(422, "不支持的任务状态")
    if payload.priority not in TASK_PRIORITIES:
        raise HTTPException(422, "不支持的任务优先级")


@router.get("")
def list_tasks(task_date: date | None = Query(None), status: str | None = None, priority: str | None = None, db: Session = Depends(get_db)):
    target = task_date or date.today()
    ensure_daily_tasks(db, target)
    stmt = select(WorkTask).where(WorkTask.task_date == target, WorkTask.is_archived.is_(False)).order_by(WorkTask.due_at, WorkTask.id)
    if status:
        if status not in TASK_STATUSES:
            raise HTTPException(422, "不支持的任务状态")
        stmt = stmt.where(WorkTask.status == status)
    if priority:
        if priority not in TASK_PRIORITIES:
            raise HTTPException(422, "不支持的任务优先级")
        stmt = stmt.where(WorkTask.priority == priority)
    return [serialize(item) for item in db.scalars(stmt).all()]


@router.post("/generate")
def generate_tasks(task_date: date | None = None, db: Session = Depends(get_db)):
    return [serialize(item) for item in ensure_daily_tasks(db, task_date or date.today())]


@router.post("", status_code=201)
def create_task(payload: WorkTaskPayload, db: Session = Depends(get_db)):
    _validate_values(payload)
    item = WorkTask(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.get("/{task_id}")
def get_task(task_id: int, db: Session = Depends(get_db)):
    item = db.get(WorkTask, task_id)
    if not item or item.is_archived:
        raise HTTPException(404, "任务不存在")
    return serialize(item)


@router.put("/{task_id}")
def update_task(task_id: int, payload: WorkTaskPayload, db: Session = Depends(get_db)):
    item = db.get(WorkTask, task_id)
    if not item or item.is_archived:
        raise HTTPException(404, "任务不存在")
    _validate_values(payload)
    for key, value in payload.model_dump().items():
        setattr(item, key, value)
    if item.status == "completed" and item.completed_at is None:
        item.completed_at = datetime.utcnow()
    if item.status != "completed":
        item.completed_at = None
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.patch("/{task_id}/status")
def update_task_status(task_id: int, payload: WorkTaskStatusPayload, db: Session = Depends(get_db)):
    if payload.status not in TASK_STATUSES:
        raise HTTPException(422, "不支持的任务状态")
    item = db.get(WorkTask, task_id)
    if not item or item.is_archived:
        raise HTTPException(404, "任务不存在")
    item.status = payload.status
    item.notes = payload.notes if payload.notes is not None else item.notes
    item.completed_at = datetime.utcnow() if payload.status == "completed" else None
    db.commit()
    db.refresh(item)
    return serialize(item)


@router.delete("/{task_id}", status_code=204)
def delete_task(task_id: int, db: Session = Depends(get_db)):
    item = db.get(WorkTask, task_id)
    if not item:
        raise HTTPException(404, "任务不存在")
    if item.source == "manual":
        db.delete(item)
    else:
        item.is_archived = True
    db.commit()


@legacy_router.get("")
def legacy_list_tasks(task_date: date | None = Query(None), status: str | None = None, priority: str | None = None, db: Session = Depends(get_db)):
    return list_tasks(task_date=task_date, status=status, priority=priority, db=db)


@legacy_router.post("", status_code=201)
def legacy_create_task(payload: WorkTaskPayload, db: Session = Depends(get_db)):
    return create_task(payload, db)


@legacy_router.patch("/{task_id}")
def legacy_update_task(task_id: int, payload: WorkTaskStatusPayload, db: Session = Depends(get_db)):
    return update_task_status(task_id, payload, db)


@legacy_router.delete("/{task_id}", status_code=204)
def legacy_delete_task(task_id: int, db: Session = Depends(get_db)):
    return delete_task(task_id, db)
