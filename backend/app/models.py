from datetime import datetime
from sqlalchemy import String, Text, Integer, Float, DateTime, ForeignKey, Table, Column, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base

asset_tags = Table("asset_tags", Base.metadata,
    Column("asset_id", ForeignKey("assets.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True))
script_tags = Table("script_tags", Base.metadata,
    Column("script_id", ForeignKey("scripts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True))

class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Market(Base):
    __tablename__ = "markets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    language: Mapped[str | None] = mapped_column(String(50))
    country_code: Mapped[str | None] = mapped_column(String(5))
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    products = relationship("Product", back_populates="market")

class Product(Base, TimestampMixin):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(150))
    category: Mapped[str | None] = mapped_column(String(100))
    selling_points: Mapped[str | None] = mapped_column(Text)
    target_markets: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    market = relationship("Market", back_populates="products")

class Asset(Base, TimestampMixin):
    __tablename__ = "assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    file_path: Mapped[str | None] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    source_platform: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(500))
    asset_type: Mapped[str | None] = mapped_column(String(50))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    duration: Mapped[float | None] = mapped_column(Float)
    width: Mapped[int | None] = mapped_column(Integer)
    height: Mapped[int | None] = mapped_column(Integer)
    fps: Mapped[float | None] = mapped_column(Float)
    description: Mapped[str | None] = mapped_column(Text)
    tags_text: Mapped[str | None] = mapped_column("tags", Text)
    visual_features: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active")
    semantic_summary: Mapped[str | None] = mapped_column(Text)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    product = relationship("Product")
    market = relationship("Market")
    tag_entities = relationship("Tag", secondary=asset_tags, back_populates="assets")

class Script(Base, TimestampMixin):
    __tablename__ = "scripts"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    source_platform: Mapped[str | None] = mapped_column(String(50))
    source_url: Mapped[str | None] = mapped_column(String(500))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    script_type: Mapped[str | None] = mapped_column(String(50))
    hook: Mapped[str | None] = mapped_column(Text)
    body: Mapped[str | None] = mapped_column(Text)
    ending: Mapped[str | None] = mapped_column(Text)
    cta: Mapped[str | None] = mapped_column(Text)
    full_text: Mapped[str | None] = mapped_column(Text)
    duration: Mapped[float | None] = mapped_column(Float)
    tags_text: Mapped[str | None] = mapped_column("tags", Text)
    notes: Mapped[str | None] = mapped_column(Text)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    market = relationship("Market")
    product = relationship("Product")
    tag_entities = relationship("Tag", secondary=script_tags, back_populates="scripts")

class ContentTemplate(Base, TimestampMixin):
    __tablename__ = "content_templates"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    template_type: Mapped[str | None] = mapped_column(String(50))
    structure: Mapped[str | None] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    recommended_duration: Mapped[float | None] = mapped_column(Float)
    tags_text: Mapped[str | None] = mapped_column("tags", Text)
    embedding_json: Mapped[str | None] = mapped_column(Text)
    market = relationship("Market")
    product = relationship("Product")

class MixProject(Base, TimestampMixin):
    __tablename__ = "mix_projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    script_id: Mapped[int | None] = mapped_column(ForeignKey("scripts.id"))
    template_id: Mapped[int | None] = mapped_column(ForeignKey("content_templates.id"))
    target_duration: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    notes: Mapped[str | None] = mapped_column(Text)
    market = relationship("Market")
    product = relationship("Product")
    script = relationship("Script")
    template = relationship("ContentTemplate")
    assets = relationship("MixProjectAsset", back_populates="mix_project", cascade="all, delete-orphan")

class MixProjectAsset(Base):
    __tablename__ = "mix_project_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    mix_project_id: Mapped[int] = mapped_column(ForeignKey("mix_projects.id", ondelete="CASCADE"))
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"))
    order_index: Mapped[int] = mapped_column(Integer, default=0)
    start_second: Mapped[float | None] = mapped_column(Float)
    end_second: Mapped[float | None] = mapped_column(Float)
    usage_type: Mapped[str | None] = mapped_column(String(30))
    notes: Mapped[str | None] = mapped_column(Text)
    mix_project = relationship("MixProject", back_populates="assets")
    asset = relationship("Asset")

class VideoWork(Base, TimestampMixin):
    __tablename__ = "video_works"
    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    mix_project_id: Mapped[int | None] = mapped_column(ForeignKey("mix_projects.id"))
    market_id: Mapped[int | None] = mapped_column(ForeignKey("markets.id"))
    product_id: Mapped[int | None] = mapped_column(ForeignKey("products.id"))
    file_path: Mapped[str | None] = mapped_column(String(500))
    thumbnail_path: Mapped[str | None] = mapped_column(String(500))
    duration: Mapped[float | None] = mapped_column(Float)
    version: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[str] = mapped_column(String(30), default="draft")
    publish_status: Mapped[str] = mapped_column(String(30), default="unpublished")
    publish_date: Mapped[datetime | None] = mapped_column(DateTime)
    notes: Mapped[str | None] = mapped_column(Text)
    mix_project = relationship("MixProject")
    market = relationship("Market")
    product = relationship("Product")

class AssetFile(Base, TimestampMixin):
    __tablename__ = "asset_files"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id", ondelete="CASCADE"))
    file_path: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str | None] = mapped_column(String(30))
    file_size: Mapped[int | None] = mapped_column(Integer)
    is_thumbnail: Mapped[bool] = mapped_column(Boolean, default=False)
    asset = relationship("Asset")

class ContentVersion(Base, TimestampMixin):
    __tablename__ = "content_versions"
    id: Mapped[int] = mapped_column(primary_key=True)
    video_work_id: Mapped[int] = mapped_column(ForeignKey("video_works.id", ondelete="CASCADE"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    change_note: Mapped[str | None] = mapped_column(Text)
    snapshot_json: Mapped[str | None] = mapped_column(Text)
    is_latest: Mapped[bool] = mapped_column(Boolean, default=True)
    video_work = relationship("VideoWork")

class Tag(Base):
    __tablename__ = "tags"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    category: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    assets = relationship("Asset", secondary=asset_tags, back_populates="tag_entities")
    scripts = relationship("Script", secondary=script_tags, back_populates="tag_entities")
