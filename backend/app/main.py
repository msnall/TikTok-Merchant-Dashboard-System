from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, inspect, or_
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .config import settings
from .models import Market, Product, Asset, Script, ContentTemplate, MixProject, MixProjectAsset, VideoWork, Tag, AssetFile, ContentVersion
from .schemas import RecommendationRequest
from .services import recommendations
from .semantic import embed, item_text, cosine, stored_embedding
import json

app = FastAPI(title="TikTok Content System API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

MODEL_MAP = {"markets": Market, "products": Product, "assets": Asset, "scripts": Script, "templates": ContentTemplate, "mix-projects": MixProject, "mix-project-assets": MixProjectAsset, "videos": VideoWork, "tags": Tag, "asset-files": AssetFile, "content-versions": ContentVersion}
ID_FIELDS = {m: {c.key for c in inspect(m).columns} for m in MODEL_MAP.values()}

def serialize(obj):
    data = {c.key: getattr(obj, c.key) for c in inspect(obj).mapper.column_attrs}
    for key in ("market", "product", "script", "template", "mix_project", "asset"):
        rel = getattr(obj, key, None)
        if rel is not None: data[key] = {"id": rel.id, "name": getattr(rel, "name", getattr(rel, "title", None))}
    if isinstance(obj, MixProject):
        data["assets"] = [serialize(x) for x in sorted(obj.assets, key=lambda entry: entry.order_index)]
        data["timeline"] = [{"start_second": entry.start_second, "end_second": entry.end_second, "usage_type": entry.usage_type, "asset": serialize(entry.asset)} for entry in sorted(obj.assets, key=lambda entry: entry.order_index)]
    return data

@app.on_event("startup")
def startup():
    Base.metadata.create_all(bind=engine)
    # Keep existing local SQLite databases usable after additive V2 fields are introduced.
    with engine.begin() as connection:
        for table, columns in (("assets", ("semantic_summary", "embedding_json")), ("scripts", ("embedding_json",)), ("content_templates", ("embedding_json",))):
            existing = {column[1] for column in connection.exec_driver_sql(f"PRAGMA table_info({table})")} if settings.database_url.startswith("sqlite") else {c[0] for c in connection.exec_driver_sql(f"SELECT column_name FROM information_schema.columns WHERE table_name='{table}'")}
            for column in columns:
                if column not in existing: connection.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {column} TEXT")
    for folder in ("assets", "thumbnails", "scripts", "videos", "temp"):
        Path(settings.storage_dir, folder).mkdir(parents=True, exist_ok=True)

@app.get("/api/health")
def health(): return {"status": "ok", "service": "content-system"}

def make_crud(path, model):
    @app.get(f"/api/{path}")
    def list_items(db: Session = Depends(get_db), q: str | None = Query(None), market_id: int | None = None, product_id: int | None = None, asset_type: str | None = None, script_type: str | None = None, template_type: str | None = None, source_platform: str | None = None):
        stmt = select(model)
        for field, value in (("market_id", market_id), ("product_id", product_id), ("asset_type", asset_type), ("script_type", script_type), ("template_type", template_type), ("source_platform", source_platform)):
            if value is not None and field in ID_FIELDS[model]: stmt = stmt.where(getattr(model, field) == value)
        if q:
            fields = [getattr(model, f) for f in ("name", "title", "description", "tags_text", "full_text") if hasattr(model, f)]
            if fields: stmt = stmt.where(or_(*(f.ilike(f"%{q}%") for f in fields)))
        return [serialize(x) for x in db.scalars(stmt.order_by(model.id.desc())).all()]
    @app.post(f"/api/{path}", status_code=201)
    def create_item(payload: dict, db: Session = Depends(get_db)):
        values = {("tags_text" if k == "tags" and hasattr(model, "tags_text") else k): v for k, v in payload.items() if (k in ID_FIELDS[model] or (k == "tags" and hasattr(model, "tags_text"))) and k != "id"}
        obj = model(**values)
        if hasattr(obj, "embedding_json"): obj.embedding_json = json.dumps(embed(item_text(obj)))
        db.add(obj); db.commit(); db.refresh(obj); return serialize(obj)
    @app.get(f"/api/{path}/{{item_id}}")
    def get_item(item_id: int, db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if not obj: raise HTTPException(404, "Item not found")
        return serialize(obj)
    @app.put(f"/api/{path}/{{item_id}}")
    def update_item(item_id: int, payload: dict, db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if not obj: raise HTTPException(404, "Item not found")
        for k, v in payload.items():
            attr = "tags_text" if k == "tags" and hasattr(model, "tags_text") else k
            if (k in ID_FIELDS[model] or (k == "tags" and hasattr(model, "tags_text"))) and k != "id": setattr(obj, attr, v)
        if hasattr(obj, "embedding_json"): obj.embedding_json = json.dumps(embed(item_text(obj)))
        db.commit(); db.refresh(obj); return serialize(obj)
    @app.delete(f"/api/{path}/{{item_id}}", status_code=204)
    def delete_item(item_id: int, db: Session = Depends(get_db)):
        obj = db.get(model, item_id)
        if not obj: raise HTTPException(404, "Item not found")
        db.delete(obj); db.commit()

for _path, _model in MODEL_MAP.items(): make_crud(_path, _model)

@app.post("/api/assets/{item_id}/file")
async def upload_asset_file(item_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    asset = db.get(Asset, item_id)
    if not asset: raise HTTPException(404, "Asset not found")
    allowed = {".jpg", ".jpeg", ".png", ".webp", ".mp4", ".mov", ".webm"}
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in allowed: raise HTTPException(400, "Unsupported media extension")
    safe_name = f"asset-{item_id}{suffix}"
    target_dir = Path(settings.storage_dir, "assets").resolve(); target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / safe_name).resolve()
    if target.parent != target_dir: raise HTTPException(400, "Invalid filename")
    size = 0
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_size:
                target.unlink(missing_ok=True); raise HTTPException(413, "File too large")
            output.write(chunk)
    asset.file_path = str(target.relative_to(Path(settings.storage_dir).resolve()))
    db.commit(); db.refresh(asset)
    return serialize(asset)

@app.post("/api/assistant/recommend")
def recommend(payload: RecommendationRequest, db: Session = Depends(get_db)):
    ranked = recommendations(db, **payload.model_dump())
    return {key: [{"score": row["score"], "reasons": row["reasons"], **serialize(row["item"])} for row in rows] for key, rows in ranked.items()}

@app.get("/api/search")
def semantic_search(q: str = Query(..., min_length=1), entity: str = Query("assets"), market_id: int | None = None, product_id: int | None = None, limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Hybrid lexical + local semantic search. pgvector can replace stored_embedding without changing this contract."""
    model = MODEL_MAP.get(entity)
    if model not in (Asset, Script, ContentTemplate): raise HTTPException(400, "entity must be assets, scripts, or templates")
    query_tokens = set(q.lower().split())
    results = []
    for item in db.scalars(select(model)).all():
        if market_id is not None and getattr(item, "market_id", None) != market_id: continue
        if product_id is not None and getattr(item, "product_id", None) != product_id: continue
        text = item_text(item).lower(); keyword_score = sum(token in text for token in query_tokens) / len(query_tokens) if query_tokens else 0
        semantic_score = cosine(embed(q), stored_embedding(item))
        final_score = round(.45 * keyword_score + .55 * semantic_score, 4)
        results.append({"keyword_score": round(keyword_score, 4), "semantic_score": semantic_score, "final_score": final_score, **serialize(item)})
    return sorted(results, key=lambda row: row["final_score"], reverse=True)[:limit]

@app.post("/api/videos/{video_id}/versions", status_code=201)
def create_video_version(video_id: int, payload: dict, db: Session = Depends(get_db)):
    video = db.get(VideoWork, video_id)
    if not video: raise HTTPException(404, "Video not found")
    latest = db.scalar(select(func.max(ContentVersion.version)).where(ContentVersion.video_work_id == video_id)) or 0
    db.query(ContentVersion).filter(ContentVersion.video_work_id == video_id).update({"is_latest": False})
    version = ContentVersion(video_work_id=video_id, version=latest + 1, change_note=payload.get("change_note"), snapshot_json=json.dumps(payload.get("snapshot", {})), is_latest=True)
    db.add(version); db.commit(); db.refresh(version); return serialize(version)

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    return {"assets": db.scalar(select(func.count(Asset.id))) or 0, "scripts": db.scalar(select(func.count(Script.id))) or 0, "templates": db.scalar(select(func.count(ContentTemplate.id))) or 0, "mix_projects": db.scalar(select(func.count(MixProject.id))) or 0, "videos": db.scalar(select(func.count(VideoWork.id))) or 0}
