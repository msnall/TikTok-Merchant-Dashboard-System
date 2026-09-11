from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import MixProject, VideoWork
from .ad_models import AdPlan, AdPlanSnapshot, OperationRecord
from .main_helpers import serialize
from .work_services import ensure_daily_tasks
from .ad_services import REMINDER_STATUSES, is_alert_pending, latest_snapshot
from .work_schemas import TASK_PRIORITIES, TASK_STATUSES
from datetime import date

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

@router.get("/today")
def today(task_date: date | None = None, status: str | None = None, priority: str | None = None, db: Session = Depends(get_db)):
    target_date = task_date or date.today()
    tasks = ensure_daily_tasks(db, target_date)
    all_tasks = list(tasks)
    if status:
        if status not in TASK_STATUSES:
            raise HTTPException(422, "不支持的任务状态")
        tasks = [item for item in tasks if item.status == status]
    if priority:
        if priority not in TASK_PRIORITIES:
            raise HTTPException(422, "不支持的任务优先级")
        tasks = [item for item in tasks if item.priority == priority]
    summary = {
        "total": len(all_tasks),
        "pending": sum(item.status == "pending" for item in all_tasks),
        "in_progress": sum(item.status == "in_progress" for item in all_tasks),
        "completed": sum(item.status == "completed" for item in all_tasks),
        "skipped": sum(item.status == "skipped" for item in all_tasks),
        "completion_rate": round(sum(item.status == "completed" for item in all_tasks) / len(all_tasks) * 100, 2) if all_tasks else 0,
    }
    projects = db.scalars(select(MixProject).where(MixProject.status == "draft").order_by(MixProject.id.desc()).limit(10)).all()
    videos = db.scalars(select(VideoWork).where(VideoWork.file_path.is_(None)).order_by(VideoWork.id.desc()).limit(10)).all()
    alert_candidates = db.scalars(select(AdPlan).where(AdPlan.current_status.in_(REMINDER_STATUSES)).order_by(AdPlan.updated_at.desc()).limit(50)).all()
    alerts = [plan for plan in alert_candidates if is_alert_pending(plan)][:10]
    operations = db.scalars(select(OperationRecord).order_by(OperationRecord.operated_at.desc()).limit(5)).all()
    serialized_alerts = []
    for item in alerts:
        data = serialize(item)
        snapshot = latest_snapshot(item)
        data["latest_snapshot"] = serialize(snapshot) if snapshot else None
        serialized_alerts.append(data)
    return {"date": target_date.isoformat(), "tasks": [serialize(item) for item in tasks], "task_summary": summary, "content_projects": [serialize(item) for item in projects], "pending_videos": [serialize(item) for item in videos], "ad_alerts": serialized_alerts, "recent_operations": [serialize(item) for item in operations]}
