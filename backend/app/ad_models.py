from datetime import datetime
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class AdImportBatch(Base):
    __tablename__ = "ad_import_batches"
    id: Mapped[int] = mapped_column(primary_key=True)
    file_name: Mapped[str] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(30), default="completed")
    error_message: Mapped[str | None] = mapped_column(Text)
    snapshots = relationship("AdPlanSnapshot", back_populates="import_batch", cascade="all, delete-orphan")


class AdPlan(Base):
    __tablename__ = "ad_plans"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform_campaign_id: Mapped[str | None] = mapped_column(String(64), index=True)
    plan_name: Mapped[str] = mapped_column(String(255), index=True)
    imported_product_name: Mapped[str | None] = mapped_column(String(255))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id", ondelete="SET NULL"))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id", ondelete="SET NULL"))
    strategy_code: Mapped[str | None] = mapped_column(String(20))
    current_status: Mapped[str] = mapped_column(String(40), default="unknown")
    target_roi: Mapped[float | None] = mapped_column(Float)
    product_unit_price: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    product = relationship("Product")
    market = relationship("Market")
    snapshots = relationship("AdPlanSnapshot", back_populates="ad_plan", cascade="all, delete-orphan")
    operations = relationship("OperationRecord", back_populates="ad_plan")


class AdPlanSnapshot(Base):
    __tablename__ = "ad_plan_snapshots"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_plan_id: Mapped[int] = mapped_column(ForeignKey("ad_plans.id", ondelete="CASCADE"))
    import_batch_id: Mapped[int] = mapped_column(ForeignKey("ad_import_batches.id", ondelete="CASCADE"))
    snapshot_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    spend: Mapped[float | None] = mapped_column(Float)
    orders: Mapped[int | None] = mapped_column(Integer)
    revenue: Mapped[float | None] = mapped_column(Float)
    actual_roi: Mapped[float | None] = mapped_column(Float)
    budget: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(40), default="unknown")
    reason: Mapped[str | None] = mapped_column(Text)
    recommendation: Mapped[str | None] = mapped_column(Text)
    ad_plan = relationship("AdPlan", back_populates="snapshots")
    import_batch = relationship("AdImportBatch", back_populates="snapshots")


class AdStrategy(Base):
    __tablename__ = "ad_strategies"
    id: Mapped[int] = mapped_column(primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id", ondelete="CASCADE"))
    strategy_code: Mapped[str] = mapped_column(String(20), default="A")
    base_target_roi: Mapped[float] = mapped_column(Float, default=2.0)
    multiplier: Mapped[float] = mapped_column(Float, default=1.0)
    empty_burn_threshold: Mapped[float] = mapped_column(Float, default=0)
    low_roi_threshold: Mapped[float] = mapped_column(Float, default=0)
    no_spend_hours: Mapped[float] = mapped_column(Float, default=24)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    product = relationship("Product")


class OperationRecord(Base):
    __tablename__ = "operation_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    ad_plan_id: Mapped[int] = mapped_column(ForeignKey("ad_plans.id", ondelete="CASCADE"))
    operation_type: Mapped[str] = mapped_column(String(40))
    old_target_roi: Mapped[float | None] = mapped_column(Float)
    new_target_roi: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    operated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    ad_plan = relationship("AdPlan", back_populates="operations")
