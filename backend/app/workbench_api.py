from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import MixProject, VideoWork
from .ad_models import AdPlan, AdPlanSnapshot, OperationRecord
from .main_helpers import serialize
from .work_services import ensure_daily_tasks
from .work_schemas import TASK_PRIORITIES, TASK_STATUSES
from datetime import date

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

@router.get("/today")
def today(task_date: date | None = None, status: str | None = None, priority: str | None = None, db: Session = Depends(get_db)):
    target_date = task_date or date.today()
    tasks = ensure_daily_tasks(db, target_date)
    if status:
        if status not in TASK_STATUSES:
            raise HTTPException(422, "不支持的任务状态")
        tasks = [item for item in tasks if item.status == status]
    if priority:
        if priority not in TASK_PRIORITIES:
            raise HTTPException(422, "不支持的任务优先级")
        tasks = [item for item in tasks if item.priority == priority]
    projects = db.scalars(select(MixProject).where(MixProject.status == "draft").order_by(MixProject.id.desc()).limit(10)).all()
    videos = db.scalars(select(VideoWork).where(VideoWork.file_path.is_(None)).order_by(VideoWork.id.desc()).limit(10)).all()
    alerts = db.scalars(select(AdPlan).where(AdPlan.current_status != "normal").order_by(AdPlan.updated_at.desc()).limit(10)).all()
    operations = db.scalars(select(OperationRecord).order_by(OperationRecord.operated_at.desc()).limit(5)).all()
    return {"date": target_date.isoformat(), "tasks": [serialize(item) for item in tasks], "content_projects": [serialize(item) for item in projects], "pending_videos": [serialize(item) for item in videos], "ad_alerts": [serialize(item) for item in alerts], "recent_operations": [serialize(item) for item in operations]}
