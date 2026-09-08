from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class WorkTask(Base):
    __tablename__ = "work_tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    task_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    priority: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime, index=True)
    task_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(30), nullable=False, default="manual")
    related_type: Mapped[str | None] = mapped_column(String(40))
    related_id: Mapped[int | None] = mapped_column(Integer)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
