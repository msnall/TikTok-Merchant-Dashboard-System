from typing import Any
from pydantic import Field
from pydantic import BaseModel, ConfigDict

class Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")

class RecommendationRequest(BaseModel):
    market_id: int | None = None
    product_id: int | None = None
    content_type: str | None = None
    duration: float | None = None
    keywords: list[str] = Field(default_factory=list)
