from pathlib import Path
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, Query, UploadFile, File, Request
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, func, inspect, or_
from sqlalchemy.exc import IntegrityError
from pydantic import ValidationError
from sqlalchemy.orm import Session
from .db import Base, engine, get_db
from .config import settings
from .models import Market, Product, Asset, Script, ContentTemplate, MixProject, MixProjectAsset, VideoWork, Tag, AssetFile, ContentVersion
from .schemas import RecommendationRequest, AdoptRecommendationRequest, MarketCreate, ProductCreate, AssetCreate, ScriptCreate, TemplateCreate, MixProjectCreate, MixProjectAssetCreate, VideoWorkCreate, TagCreate
from .services import recommendations
from .semantic import embed, item_text, cosine, stored_embedding
from . import ad_models
from . import work_models
from .ad_api import router as ad_router
from .workbench_api import router as workbench_router
from .work_api import router as work_task_router, legacy_router as legacy_work_task_router
import json
import io
import re
import shutil
import subprocess
import zipfile

app = FastAPI(title="TikTok Content System API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")
app.include_router(ad_router)
app.include_router(workbench_router)
app.include_router(work_task_router)
app.include_router(legacy_work_task_router)

@app.exception_handler(IntegrityError)
async def integrity_error_handler(request: Request, exc: IntegrityError):
    return JSONResponse(status_code=409, content={"detail": "数据关系或唯一约束冲突"})

@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "服务器内部错误"})

MODEL_MAP = {"markets": Market, "products": Product, "assets": Asset, "scripts": Script, "templates": ContentTemplate, "mix-projects": MixProject, "mix-project-assets": MixProjectAsset, "videos": VideoWork, "tags": Tag, "asset-files": AssetFile, "content-versions": ContentVersion}
SCHEMA_MAP = {Market: MarketCreate, Product: ProductCreate, Asset: AssetCreate, Script: ScriptCreate, ContentTemplate: TemplateCreate, MixProject: MixProjectCreate, MixProjectAsset: MixProjectAssetCreate, VideoWork: VideoWorkCreate, Tag: TagCreate}
ID_FIELDS = {m: {c.key for c in inspect(m).columns} for m in MODEL_MAP.values()}

def validate_payload(schema, payload):
    try:
        return schema.model_validate(payload).model_dump(exclude_unset=True)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc

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
    def list_items(db: Session = Depends(get_db), q: str | None = Query(None), market_id: int | None = None, product_id: int | None = None, asset_type: str | None = None, script_type: str | None = None, template_type: str | None = None, source_platform: str | None = None, tag_id: int | None = None, duration_min: float | None = Query(None, ge=0), duration_max: float | None = Query(None, ge=0), mix_project_id: int | None = None, video_work_id: int | None = None, asset_id: int | None = None):
        stmt = select(model)
        for field, value in (("market_id", market_id), ("product_id", product_id), ("asset_type", asset_type), ("script_type", script_type), ("template_type", template_type), ("source_platform", source_platform)):
            if value is not None and field in ID_FIELDS[model]: stmt = stmt.where(getattr(model, field) == value)
        if mix_project_id is not None and model is VideoWork: stmt = stmt.where(model.mix_project_id == mix_project_id)
        if video_work_id is not None and model is ContentVersion: stmt = stmt.where(model.video_work_id == video_work_id)
        if asset_id is not None and model is AssetFile: stmt = stmt.where(model.asset_id == asset_id)
        if tag_id is not None and model in (Asset, Script): stmt = stmt.join(model.tag_entities).where(Tag.id == tag_id)
        duration_field = getattr(model, "duration", None)
        if duration_field is None: duration_field = getattr(model, "recommended_duration", None)
        if duration_field is not None:
            if duration_min is not None: stmt = stmt.where(duration_field >= duration_min)
            if duration_max is not None: stmt = stmt.where(duration_field <= duration_max)
        if q:
            fields = [getattr(model, f) for f in ("name", "title", "description", "tags_text", "full_text") if hasattr(model, f)]
            if fields: stmt = stmt.where(or_(*(f.ilike(f"%{q}%") for f in fields)))
        return [serialize(x) for x in db.scalars(stmt.order_by(model.id.desc())).all()]
    @app.post(f"/api/{path}", status_code=201)
    def create_item(payload: dict, db: Session = Depends(get_db)):
        schema = SCHEMA_MAP.get(model)
        if schema:
            payload = validate_payload(schema, payload)
        tag_ids = payload.pop("tag_ids", None)
        values = {("tags_text" if k == "tags" and hasattr(model, "tags_text") else k): v for k, v in payload.items() if (k in ID_FIELDS[model] or (k == "tags" and hasattr(model, "tags_text"))) and k != "id"}
        obj = model(**values)
        if tag_ids is not None and model in (Asset, Script):
            obj.tag_entities = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()
            if len(obj.tag_entities) != len(set(tag_ids)):
                raise HTTPException(404, "Tag not found")
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
        schema = SCHEMA_MAP.get(model)
        if schema:
            candidate = {}
            for key in schema.model_fields:
                attr = "tags_text" if key == "tags" and hasattr(obj, "tags_text") else key
                if hasattr(obj, attr):
                    candidate[key] = getattr(obj, attr)
            candidate.update(payload)
            payload = validate_payload(schema, candidate)
        tag_ids = payload.pop("tag_ids", None)
        for k, v in payload.items():
            attr = "tags_text" if k == "tags" and hasattr(model, "tags_text") else k
            if (k in ID_FIELDS[model] or (k == "tags" and hasattr(model, "tags_text"))) and k != "id": setattr(obj, attr, v)
        if tag_ids is not None and model in (Asset, Script):
            obj.tag_entities = db.scalars(select(Tag).where(Tag.id.in_(tag_ids))).all()
            if len(obj.tag_entities) != len(set(tag_ids)):
                raise HTTPException(404, "Tag not found")
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
    # Normalize MP4 uploads to H.264/AAC when ffmpeg is available so browser
    # previews work for source files encoded as HEVC/H.265.
    if suffix == ".mp4" and shutil.which("ffmpeg"):
        compatible = target.with_name(f"{target.stem}-h264.mp4")
        try:
            result = subprocess.run([shutil.which("ffmpeg"), "-y", "-i", str(target), "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(compatible)], capture_output=True, timeout=300)
            if result.returncode == 0 and compatible.exists() and compatible.stat().st_size > 0:
                target.unlink(missing_ok=True)
                compatible.replace(target)
                size = target.stat().st_size
        except (OSError, subprocess.SubprocessError):
            compatible.unlink(missing_ok=True)
    asset.file_path = str(target.relative_to(Path(settings.storage_dir).resolve()))
    db.add(AssetFile(asset_id=asset.id, file_path=asset.file_path, file_type=file.content_type or suffix.lstrip("."), file_size=size, is_thumbnail=False))
    db.commit(); db.refresh(asset)
    return serialize(asset)

@app.post("/api/videos/{video_id}/file")
async def upload_video_file(video_id: int, file: UploadFile = File(...), db: Session = Depends(get_db)):
    video = db.get(VideoWork, video_id)
    if not video: raise HTTPException(404, "Video not found")
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".mp4", ".mov", ".webm"}: raise HTTPException(400, "Unsupported video extension")
    target_dir = Path(settings.storage_dir, "videos").resolve(); target_dir.mkdir(parents=True, exist_ok=True)
    target = (target_dir / f"video-{video_id}{suffix}").resolve()
    if target.parent != target_dir: raise HTTPException(400, "Invalid filename")
    size = 0
    with target.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            size += len(chunk)
            if size > settings.max_upload_size:
                target.unlink(missing_ok=True); raise HTTPException(413, "File too large")
            output.write(chunk)
    if suffix == ".mp4" and shutil.which("ffmpeg"):
        compatible = target.with_name(f"{target.stem}-h264.mp4")
        try:
            result = subprocess.run([shutil.which("ffmpeg"), "-y", "-i", str(target), "-c:v", "libx264", "-c:a", "aac", "-movflags", "+faststart", str(compatible)], capture_output=True, timeout=300)
            if result.returncode == 0 and compatible.exists() and compatible.stat().st_size > 0:
                target.unlink(missing_ok=True); compatible.replace(target)
        except (OSError, subprocess.SubprocessError):
            compatible.unlink(missing_ok=True)
    video.file_path = str(target.relative_to(Path(settings.storage_dir).resolve()))
    db.commit(); db.refresh(video)
    return serialize(video)

@app.post("/api/assistant/recommend")
def recommend(payload: RecommendationRequest, db: Session = Depends(get_db)):
    ranked = recommendations(db, **payload.model_dump())
    response = {}
    for key, rows in ranked.items():
        if key == "mix_plans":
            response[key] = rows
        else:
            response[key] = [{"score": row["score"], "reasons": row["reasons"], "score_breakdown": row.get("score_breakdown", {}), **serialize(row["item"])} for row in rows]
    return response

@app.post("/api/assistant/adopt", status_code=201)
def adopt_recommendation(payload: AdoptRecommendationRequest, db: Session = Depends(get_db)):
    ranked = recommendations(db, **payload.model_dump(exclude={"plan_index", "name"}))
    plans = ranked.get("mix_plans", [])
    if payload.plan_index >= len(plans):
        raise HTTPException(404, "推荐方案不存在，请重新获取推荐")
    plan = plans[payload.plan_index]
    project = MixProject(name=payload.name or f"推荐混剪方案 {plan['id']}", market_id=payload.market_id,
                         product_id=payload.product_id, script_id=plan["script_id"], template_id=plan["template_id"],
                         target_duration=payload.duration, status="draft", notes="由创作助手推荐采用")
    db.add(project); db.flush()
    for entry in plan["timeline"]:
        db.add(MixProjectAsset(mix_project_id=project.id, **entry))
    db.commit(); db.refresh(project)
    return {"project": serialize(project), "plan": plan}

@app.get("/api/search")
def semantic_search(q: str = Query(..., min_length=1), entity: str = Query("assets"), type: str | None = None, market_id: int | None = None, product_id: int | None = None, tag_id: int | None = None, source_platform: str | None = None, duration_min: float | None = Query(None, ge=0), duration_max: float | None = Query(None, ge=0), limit: int = Query(20, ge=1, le=100), db: Session = Depends(get_db)):
    """Hybrid lexical + local semantic search. pgvector can replace stored_embedding without changing this contract."""
    model = MODEL_MAP.get(entity)
    if model not in (Asset, Script, ContentTemplate): raise HTTPException(400, "entity must be assets, scripts, or templates")
    query_tokens = set(q.lower().split())
    results = []
    for item in db.scalars(select(model)).all():
        if market_id is not None and getattr(item, "market_id", None) != market_id: continue
        if product_id is not None and getattr(item, "product_id", None) != product_id: continue
        if source_platform is not None and getattr(item, "source_platform", None) != source_platform: continue
        type_field = "asset_type" if model is Asset else "script_type" if model is Script else "template_type"
        if type is not None and getattr(item, type_field, None) != type: continue
        if tag_id is not None and model in (Asset, Script) and not any(tag.id == tag_id for tag in item.tag_entities): continue
        item_duration = getattr(item, "duration", None) or getattr(item, "recommended_duration", None)
        if duration_min is not None and (item_duration is None or item_duration < duration_min): continue
        if duration_max is not None and (item_duration is None or item_duration > duration_max): continue
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

@app.put("/api/mix-projects/{project_id}/timeline")
def replace_timeline(project_id: int, entries: list[MixProjectAssetCreate], db: Session = Depends(get_db)):
    project = db.get(MixProject, project_id)
    if not project: raise HTTPException(404, "Mix project not found")
    target = project.target_duration
    intervals = []
    for entry in entries:
        if not db.get(Asset, entry.asset_id): raise HTTPException(404, f"Asset {entry.asset_id} not found")
        if entry.start_second is not None and entry.start_second < 0: raise HTTPException(422, "start_second must be >= 0")
        if entry.start_second is not None and entry.end_second is not None and entry.end_second <= entry.start_second: raise HTTPException(422, "end_second must be greater than start_second")
        if target is not None and entry.end_second is not None and entry.end_second > target: raise HTTPException(422, "end_second exceeds target_duration")
        if entry.start_second is not None and entry.end_second is not None:
            intervals.append((entry.start_second, entry.end_second))
    for previous, current in zip(sorted(intervals), sorted(intervals)[1:]):
        if current[0] < previous[1]:
            raise HTTPException(422, "timeline entries cannot overlap")
    db.query(MixProjectAsset).filter(MixProjectAsset.mix_project_id == project_id).delete(synchronize_session=False)
    for index, entry in enumerate(entries):
        values = entry.model_dump(exclude={"mix_project_id", "order_index"})
        db.add(MixProjectAsset(mix_project_id=project_id, order_index=index, **values))
    db.commit(); db.refresh(project); return serialize(project)

@app.post("/api/mix-projects/{project_id}/clone", status_code=201)
def clone_mix_project(project_id: int, db: Session = Depends(get_db)):
    source = db.get(MixProject, project_id)
    if not source: raise HTTPException(404, "Mix project not found")
    clone = MixProject(name=f"{source.name} - 副本", market_id=source.market_id, product_id=source.product_id,
                       script_id=source.script_id, template_id=source.template_id, target_duration=source.target_duration,
                       status="draft", notes=source.notes)
    db.add(clone); db.flush()
    for entry in sorted(source.assets, key=lambda row: row.order_index):
        db.add(MixProjectAsset(mix_project_id=clone.id, asset_id=entry.asset_id, order_index=entry.order_index,
                               start_second=entry.start_second, end_second=entry.end_second,
                               usage_type=entry.usage_type, notes=entry.notes))
    db.commit(); db.refresh(clone)
    return serialize(clone)

@app.get("/api/mix-projects/{project_id}/assets.zip")
def download_mix_project_assets(project_id: int, db: Session = Depends(get_db)):
    project = db.get(MixProject, project_id)
    if not project: raise HTTPException(404, "Mix project not found")
    storage_root = Path(settings.storage_dir).resolve()
    archive = io.BytesIO()
    file_count = 0
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        for index, entry in enumerate(sorted(project.assets, key=lambda row: row.order_index), start=1):
            if not entry.asset.file_path: continue
            source = (storage_root / entry.asset.file_path).resolve()
            if storage_root not in source.parents or not source.is_file(): continue
            safe_name = re.sub(r'[^\w\-.\u4e00-\u9fff]+', '_', entry.asset.name).strip('_') or f"asset-{entry.asset.id}"
            bundle.write(source, f"{index:02d}_{safe_name}{source.suffix.lower()}")
            file_count += 1
        if not file_count: raise HTTPException(404, "该方案没有可下载的源文件")
    archive.seek(0)
    headers = {"Content-Disposition": f'attachment; filename="mix-project-{project_id}-assets.zip"'}
    return StreamingResponse(archive, media_type="application/zip", headers=headers)

@app.get("/api/dashboard")
def dashboard(db: Session = Depends(get_db)):
    def distribution(model, field):
        rows = db.execute(select(field, func.count()).where(field.is_not(None)).group_by(field).order_by(func.count().desc())).all()
        return [{"key": key, "count": count} for key, count in rows]
    return {
        "assets": db.scalar(select(func.count(Asset.id))) or 0,
        "scripts": db.scalar(select(func.count(Script.id))) or 0,
        "templates": db.scalar(select(func.count(ContentTemplate.id))) or 0,
        "mix_projects": db.scalar(select(func.count(MixProject.id))) or 0,
        "videos": db.scalar(select(func.count(VideoWork.id))) or 0,
        "market_distribution": distribution(Asset, Asset.market_id),
        "product_distribution": distribution(Asset, Asset.product_id),
        "asset_type_distribution": distribution(Asset, Asset.asset_type),
        "script_type_distribution": distribution(Script, Script.script_type),
    }

@app.get("/api/assets/{asset_id}/lineage")
def asset_lineage(asset_id: int, db: Session = Depends(get_db)):
    asset = db.get(Asset, asset_id)
    if not asset: raise HTTPException(404, "Asset not found")
    projects = db.scalars(select(MixProject).join(MixProjectAsset).where(MixProjectAsset.asset_id == asset_id).distinct()).all()
    project_rows = []
    for project in projects:
        videos = db.scalars(select(VideoWork).where(VideoWork.mix_project_id == project.id)).all()
        project_rows.append({"id": project.id, "name": project.name, "status": project.status, "videos": [serialize(video) for video in videos]})
    return {"asset": serialize(asset), "mix_projects": project_rows}

@app.get("/api/videos/{video_id}/lineage")
def video_lineage(video_id: int, db: Session = Depends(get_db)):
    video = db.get(VideoWork, video_id)
    if not video: raise HTTPException(404, "Video not found")
    project = db.get(MixProject, video.mix_project_id) if video.mix_project_id else None
    return {"video": serialize(video), "mix_project": serialize(project) if project else None}
