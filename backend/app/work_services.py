from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from .ad_models import AdPlan
from .ad_services import ALERT_STATUSES, latest_snapshot, recompute_plan_status
from .models import MixProject, VideoWork
from .work_models import WorkTask


FIXED_TASKS = (
    ("08:30", "客服消息", "customer_service", "medium"),
    ("09:00", "超时/即将超时订单检查", "order_check", "medium"),
    ("09:15", "售后仅退款检查", "after_sales", "medium"),
    ("09:30", "库存巡查", "inventory_check", "medium"),
    ("10:00", "广告计划检查", "ad_check", "high"),
    ("11:00", "销售登记", "sales_record", "medium"),
    ("11:30", "寻找内容素材", "find_material", "medium"),
    ("14:00", "剪视频", "video_edit", "medium"),
    ("16:00", "发布视频", "video_publish", "medium"),
    ("17:00", "投放广告计划", "ad_launch", "high"),
    ("20:00", "客服消息复查", "customer_service", "medium"),
    ("21:00", "广告账户余额检查", "ad_balance", "medium"),
    ("22:00", "准备明日脚本", "next_day_preparation", "low"),
)


def _find_existing(db: Session, task_date: date, task_type: str, source: str, related_id: int | None = None, title: str | None = None):
    stmt = select(WorkTask).where(WorkTask.task_date == task_date, WorkTask.task_type == task_type, WorkTask.source == source)
    if related_id is None:
        stmt = stmt.where(WorkTask.related_id.is_(None))
    else:
        stmt = stmt.where(WorkTask.related_id == related_id)
    if title is not None:
        stmt = stmt.where(WorkTask.title == title)
    return db.scalar(stmt)


def ensure_daily_tasks(db: Session, task_date: date) -> list[WorkTask]:
    """Create the deterministic SOP view and current system-backed follow-ups once per day."""
    for due, title, task_type, priority in FIXED_TASKS:
        if _find_existing(db, task_date, task_type, "sop", title=title):
            continue
        due_at = datetime.combine(task_date, time.fromisoformat(due))
        db.add(WorkTask(title=title, description="人工运营任务，请在实际业务系统完成检查后更新状态。", task_type=task_type,
                        priority=priority, due_at=due_at, task_date=task_date, source="sop"))

    plans = db.scalars(select(AdPlan)).all()
    for plan in plans:
        recompute_plan_status(plan)
    alerts = [plan for plan in plans if plan.current_status in ALERT_STATUSES]
    for plan in alerts:
        if not _find_existing(db, task_date, "ad_alert", "system", plan.id):
            snapshot = latest_snapshot(plan)
            description = snapshot.reason if snapshot and snapshot.reason else "广告计划触发异常规则，请回 TikTok 后台确认。"
            db.add(WorkTask(title=f"检查广告计划：{plan.plan_name}", description=description,
                            task_type="ad_alert", priority="high", task_date=task_date, source="system",
                            related_type="ad_plan", related_id=plan.id))

    projects = db.scalars(select(MixProject).where(MixProject.status == "draft").limit(20)).all()
    for project in projects:
        if not _find_existing(db, task_date, "content_task", "system", project.id):
            db.add(WorkTask(title=f"完成混剪方案：{project.name}", description="方案仍处于草稿状态，请继续调整时间轴或准备成片。",
                            task_type="content_task", priority="medium", task_date=task_date, source="system",
                            related_type="mix_project", related_id=project.id))

    videos = db.scalars(select(VideoWork).where(VideoWork.file_path.is_(None)).limit(20)).all()
    for video in videos:
        if not _find_existing(db, task_date, "video_publish", "system", video.id):
            db.add(WorkTask(title=f"上传成片：{video.title}", description="混剪方案已有成片记录，但还没有上传视频文件。",
                            task_type="video_publish", priority="medium", task_date=task_date, source="system",
                            related_type="video_work", related_id=video.id))

    db.commit()
    return db.scalars(select(WorkTask).where(WorkTask.task_date == task_date, WorkTask.is_archived.is_(False)).order_by(WorkTask.due_at, WorkTask.priority.desc(), WorkTask.id)).all()
