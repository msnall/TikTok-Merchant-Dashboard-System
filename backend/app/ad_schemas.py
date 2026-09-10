from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class AdPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AdPlanCreate(AdPayload):
    platform_campaign_id: str | None = Field(default=None, max_length=64)
    plan_name: str = Field(min_length=1, max_length=255)
    imported_product_name: str | None = Field(default=None, max_length=255)
    product_id: int | None = None
    market_id: int | None = None
    strategy_code: str | None = None
    current_status: str = "unknown"
    target_roi: float | None = None
    product_unit_price: float | None = None


class TargetRoiUpdate(AdPayload):
    target_roi: float | None = Field(ge=0)


class AdPlanVariantUpdate(AdPayload):
    strategy_code: Literal["A", "B"] | None


class AdStrategyCreate(AdPayload):
    product_id: int
    strategy_code: str = Field(default="A", min_length=1, max_length=20)
    base_target_roi: float = Field(default=2.0, ge=0)
    multiplier: float = Field(default=1.0, ge=0)
    empty_burn_threshold: float = Field(default=0, ge=0)
    low_roi_threshold: float = Field(default=0, ge=0)
    no_spend_hours: float = Field(default=24, ge=0)
    enabled: bool = True


class OperationCreate(AdPayload):
    ad_plan_id: int
    operation_type: str = Field(pattern="^(direct_stop|rebuild_target_roi)$")
    old_target_roi: float | None = Field(default=None, ge=0)
    new_target_roi: float | None = Field(default=None, ge=0)
    reason: str | None = None
    notes: str | None = None
