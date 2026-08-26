"""Knowledge base API endpoints for verification and testing."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.knowledge.embeddings import EmbeddingProviderError
from app.knowledge.ingest import IngestionService
from app.knowledge.retrieval import RetrievalService

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    top_k: int = Field(default=6, ge=1, le=20)


@router.get("/status")
def knowledge_status(
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    service = IngestionService(db, settings)
    return service.status()


@router.post("/search")
def knowledge_search(
    request: SearchRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    service = RetrievalService(db, settings)
    try:
        results = service.search(request.query, top_k=request.top_k)
    except EmbeddingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {
        "results": [r.to_dict() for r in results],
        "count": len(results),
    }
