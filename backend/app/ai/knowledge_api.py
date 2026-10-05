from typing import Literal

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from .retrieval import search_knowledge


router = APIRouter(prefix="/api/ai/knowledge", tags=["knowledge retrieval"])
SourceType = Literal["operator_experience", "official_platform_definition", "synthetic_demo"]


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=300)
    top_k: int = Field(default=5, ge=1, le=20)
    source_type: SourceType | None = None


@router.get("/search")
def get_search(query: str = Query(min_length=1, max_length=300),
               top_k: int = Query(default=5, ge=1, le=20),
               source_type: SourceType | None = None):
    return {"query": query, "results": search_knowledge(query, top_k, source_type)}


@router.post("/search")
def post_search(payload: SearchRequest):
    return {"query": payload.query,
            "results": search_knowledge(payload.query, payload.top_k, payload.source_type)}
