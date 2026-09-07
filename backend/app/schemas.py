from pydantic import BaseModel, ConfigDict, Field

class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")

class MarketCreate(Payload):
    name: str = Field(min_length=1, max_length=100)
    language: str | None = None
    country_code: str | None = Field(default=None, max_length=5)
    description: str | None = None
class MarketUpdate(Payload):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    language: str | None = None
    country_code: str | None = Field(default=None, max_length=5)
    description: str | None = None

class ProductCreate(Payload):
    name: str = Field(min_length=1, max_length=150)
    category: str | None = None
    selling_points: str | None = None
    target_markets: str | None = None
    tags: str | None = None
    description: str | None = None
    market_id: int | None = None
class ProductUpdate(ProductCreate):
    name: str | None = Field(default=None, min_length=1, max_length=150)

class AssetCreate(Payload):
    name: str = Field(min_length=1, max_length=200)
    file_path: str | None = None
    thumbnail_path: str | None = None
    source_platform: str | None = None
    source_url: str | None = None
    asset_type: str | None = None
    product_id: int | None = None
    market_id: int | None = None
    duration: float | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=0)
    height: int | None = Field(default=None, ge=0)
    fps: float | None = Field(default=None, ge=0)
    description: str | None = None
    tags: str | None = None
    visual_features: str | None = None
    status: str = "active"
    semantic_summary: str | None = None
    tag_ids: list[int] | None = None
class AssetUpdate(AssetCreate):
    name: str | None = Field(default=None, min_length=1, max_length=200)

class ScriptCreate(Payload):
    title: str = Field(min_length=1, max_length=200)
    source_platform: str | None = None
    source_url: str | None = None
    market_id: int | None = None
    product_id: int | None = None
    script_type: str | None = None
    hook: str | None = None
    body: str | None = None
    ending: str | None = None
    cta: str | None = None
    full_text: str | None = None
    duration: float | None = Field(default=None, ge=0)
    tags: str | None = None
    notes: str | None = None
    tag_ids: list[int] | None = None
class ScriptUpdate(ScriptCreate):
    title: str | None = Field(default=None, min_length=1, max_length=200)

class TemplateCreate(Payload):
    name: str = Field(min_length=1, max_length=200)
    market_id: int | None = None
    product_id: int | None = None
    template_type: str | None = None
    structure: str | None = None
    description: str | None = None
    recommended_duration: float | None = Field(default=None, ge=0)
    tags: str | None = None
class TemplateUpdate(TemplateCreate):
    name: str | None = Field(default=None, min_length=1, max_length=200)

class MixProjectCreate(Payload):
    name: str = Field(min_length=1, max_length=200)
    market_id: int | None = None
    product_id: int | None = None
    script_id: int | None = None
    template_id: int | None = None
    target_duration: float | None = Field(default=None, ge=0)
    status: str = "draft"
    notes: str | None = None
class MixProjectUpdate(MixProjectCreate):
    name: str | None = Field(default=None, min_length=1, max_length=200)

class VideoWorkCreate(Payload):
    title: str = Field(min_length=1, max_length=200)
    mix_project_id: int | None = None
    market_id: int | None = None
    product_id: int | None = None
    file_path: str | None = None
    thumbnail_path: str | None = None
    duration: float | None = Field(default=None, ge=0)
    version: int = Field(default=1, ge=1)
    status: str = "draft"
    publish_status: str = "unpublished"
    notes: str | None = None
class VideoWorkUpdate(VideoWorkCreate):
    title: str | None = Field(default=None, min_length=1, max_length=200)

class MixProjectAssetCreate(Payload):
    mix_project_id: int
    asset_id: int
    order_index: int = Field(default=0, ge=0)
    start_second: float | None = Field(default=None, ge=0)
    end_second: float | None = Field(default=None, gt=0)
    usage_type: str | None = None
    notes: str | None = None

class TagCreate(Payload):
    name: str = Field(min_length=1, max_length=100)
    category: str | None = None

class RecommendationRequest(Payload):
    market_id: int | None = None
    product_id: int | None = None
    content_type: str | None = None
    duration: float | None = Field(default=None, ge=0)
    keywords: list[str] = Field(default_factory=list)

class AdoptRecommendationRequest(RecommendationRequest):
    plan_index: int = Field(default=0, ge=0, le=9)
    name: str | None = Field(default=None, max_length=200)
