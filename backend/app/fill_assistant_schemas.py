from typing import Literal

from pydantic import BaseModel, ConfigDict


class FillAssistantPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CampaignCalculation(FillAssistantPayload):
    row_number: int
    campaign_name: str
    strategy_code: Literal["A", "B", "C", "D"]
    product_name: str
    cost: float
    orders: int
    revenue: float
    actual_roi: float
    current_budget: float | None = None
    target_roi: float | None = None
    payout_roi: float | None = None
    payout_amount: float | None = None
    payout_eligible: bool
    payout_status: Literal["calculated", "not_eligible", "target_roi_pending"]


class ProductCalculation(FillAssistantPayload):
    product_name: str
    plan_count: int
    total_revenue: float
    total_consumption: float
    estimated_payout: float | None = None
    missing_target_roi_count: int
    details: list[CampaignCalculation]


class FillAssistantAnalysis(FillAssistantPayload):
    filename: str
    total_rows: int
    zero_cost_rows: int
    effective_rows: int
    product_count: int
    total_consumption: float
    payout_eligible_plans: int
    calculated_payout_plans: int
    missing_target_roi_plans: int
    products: list[ProductCalculation]


class AffiliateFeeAnalysis(FillAssistantPayload):
    filename: str
    total_rows: int
    standard_commission_total: float
    store_ad_commission_total: float
    total_affiliate_fee: float
    currency: str | None = None
    standard_empty_rows: int
    store_ad_empty_rows: int


class SalesDataRow(FillAssistantPayload):
    seller_sku: str
    seller_skus: list[str] = []
    name: str
    subtotal_after_discount: float
    matched: bool


class SalesDataAnalysis(FillAssistantPayload):
    filename: str
    total_rows: int
    valid_rows: int
    blank_sku_rows: int
    sku_count: int
    product_count: int
    matched_sku_count: int
    unmatched_sku_count: int
    total_amount: float
    rows: list[SalesDataRow]
