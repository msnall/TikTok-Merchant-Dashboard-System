from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


TASK_TYPES = {
    "customer_service", "order_check", "after_sales", "inventory_check", "ad_check",
    "sales_record", "find_material", "video_edit", "video_publish", "ad_launch",
    "ad_balance", "next_day_preparation", "ad_alert", "content_task",
}
TASK_STATUSES = {"pending", "in_progress", "completed", "skipped"}
TASK_PRIORITIES = {"high", "medium", "low"}


class WorkTaskPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    task_type: str = Field(min_length=1, max_length=40)
    status: str = "pending"
    priority: str = "medium"
    due_at: datetime | None = None
    task_date: date
    source: str = "manual"
    related_type: str | None = None
    related_id: int | None = None
    notes: str | None = None


class WorkTaskStatusPayload(BaseModel):
    status: str
    notes: str | None = None
