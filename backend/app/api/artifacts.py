"""Artifact API endpoints for generation and retrieval.

Provides:
- ``POST /api/artifacts/generate`` — generate a Markdown or HTML/CSS artifact
- ``GET /api/artifacts/{artifact_id}`` — retrieve a stored artifact
- ``GET /api/sessions/{session_id}/artifacts`` — list artifacts for a session
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.models.artifact import Artifact
from app.providers.base import ProviderError
from app.providers.factory import get_llm_provider
from app.services.artifact_service import VALID_TYPES, ArtifactService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/artifacts", tags=["artifacts"])


class ArtifactGenerateRequest(BaseModel):
    session_id: UUID
    artifact_type: str = Field(
        ..., description="Artifact type: 'markdown' or 'html'",
    )
    request: str = Field(
        min_length=3, max_length=50000,
        description="Description of what to generate",
    )
    # Lower than chat's default context isn't needed here — fewer retrieved
    # chunks means less prompt to prefill, which matters a lot on a CPU-bound
    # local model where prefill (not just decode) is slow.
    top_k: int = Field(default=6, ge=1, le=30)


@router.post("/generate")
def generate_artifact(
    request: ArtifactGenerateRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """Generate a grounded artifact and persist it to the session."""
    from app.knowledge.retrieval import RetrievalService
    from app.schemas.session import MessageCreateRequest
    from app.services.session_service import SessionService

    # Validate artifact type.
    if request.artifact_type not in VALID_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid artifact type '{request.artifact_type}'. "
            f"Supported: {sorted(VALID_TYPES)}",
        )

    # Verify session exists.
    session_svc = SessionService(db)
    session_svc.get_session(request.session_id)

    # Build the service.
    retrieval = RetrievalService(db, settings)
    try:
        llm = get_llm_provider(settings)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    service = ArtifactService(retrieval, llm)

    # Generate.
    try:
        result = service.generate(
            artifact_type=request.artifact_type,
            request_text=request.request,
            top_k=request.top_k,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Persist the artifact.
    artifact = Artifact(
        session_id=request.session_id,
        type=request.artifact_type,
        title=result.title,
        content=result.content,
        artifact_metadata={
            "sources": result.sources,
            "model": result.model,
            "provider": result.provider,
            "word_count": len(result.content.split()),
        },
    )
    db.add(artifact)
    db.commit()
    db.refresh(artifact)

    # Also persist as an assistant message referencing the artifact.
    session_svc.add_message(
        request.session_id,
        MessageCreateRequest(
            role="assistant",
            content=f"[Generated {request.artifact_type} artifact: {result.title}]",
            metadata={
                "artifact_id": str(artifact.id),
                "artifact_type": request.artifact_type,
                "sources": result.sources,
            },
        ),
    )

    return {
        "artifact_id": str(artifact.id),
        "type": request.artifact_type,
        "title": result.title,
        "content": result.content,
        "sources": result.sources,
        "model": result.model,
        "provider": result.provider,
    }


@router.get("/{artifact_id}")
def get_artifact(
    artifact_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Retrieve a stored artifact by ID."""
    artifact = db.get(Artifact, artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact {artifact_id} not found.")
    return {
        "id": str(artifact.id),
        "session_id": str(artifact.session_id),
        "type": artifact.type,
        "title": artifact.title,
        "content": artifact.content,
        "metadata": artifact.artifact_metadata or {},
        "created_at": artifact.created_at.isoformat() if artifact.created_at else None,
    }


@router.get("/session/{session_id}")
def list_session_artifacts(
    session_id: UUID,
    db: Session = Depends(get_db),
) -> dict:
    """List all artifacts for a session."""
    stmt = (
        select(Artifact)
        .where(Artifact.session_id == session_id)
        .order_by(Artifact.created_at.desc())
    )
    artifacts = list(db.scalars(stmt).all())
    return {
        "artifacts": [
            {
                "id": str(a.id),
                "type": a.type,
                "title": a.title,
                "created_at": a.created_at.isoformat() if a.created_at else None,
            }
            for a in artifacts
        ],
        "count": len(artifacts),
    }
