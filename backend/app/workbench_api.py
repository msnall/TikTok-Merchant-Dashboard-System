from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session
from .db import get_db
from .models import MixProject, VideoWork
from .ad_models import AdPlan, AdPlanSnapshot, OperationRecord
from .main_helpers import serialize

router = APIRouter(prefix="/api/workbench", tags=["workbench"])

@router.get("/today")
def today(db: Session = Depends(get_db)):
    projects = db.scalars(select(MixProject).where(MixProject.status == "draft").order_by(MixProject.id.desc()).limit(10)).all()
    videos = db.scalars(select(VideoWork).where(VideoWork.file_path.is_(None)).order_by(VideoWork.id.desc()).limit(10)).all()
    alerts = db.scalars(select(AdPlan).where(AdPlan.current_status != "normal").order_by(AdPlan.updated_at.desc()).limit(10)).all()
    operations = db.scalars(select(OperationRecord).order_by(OperationRecord.operated_at.desc()).limit(5)).all()
    return {"tasks": [{"key": "customer_service", "label": "客服消息处理", "status": "pending"}, {"key": "orders", "label": "超时/即将超时订单检查", "status": "pending"}, {"key": "inventory", "label": "库存巡查", "status": "pending"}, {"key": "sales", "label": "销售登记", "status": "pending"}, {"key": "content", "label": "今日内容制作", "status": "pending"}, {"key": "tomorrow", "label": "明日内容准备", "status": "pending"}], "content_projects": [serialize(item) for item in projects], "pending_videos": [serialize(item) for item in videos], "ad_alerts": [serialize(item) for item in alerts], "recent_operations": [serialize(item) for item in operations]}
