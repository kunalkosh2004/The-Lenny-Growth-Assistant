"""Skills API endpoints for content generation.

Provides the ``POST /api/skills/ship30`` endpoint for generating
Ship 30 for 30-style grounded essays from transcript knowledge.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.knowledge.retrieval import RetrievalService
from app.providers.base import ProviderError
from app.providers.factory import get_llm_provider
from app.skills.ship30 import Ship30Skill

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/skills", tags=["skills"])


class Ship30Request(BaseModel):
    topic: str = Field(min_length=3, max_length=5000)
    session_id: UUID | None = None
    top_k: int = Field(default=10, ge=1, le=30)
    target_words: int = Field(default=1250, ge=200, le=5000)


@router.post("/ship30")
def generate_ship30_article(
    request: Ship30Request,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """Generate a Ship 30 for 30-style essay grounded in transcript knowledge.

    The article follows a structured two-pass process:
    1. Retrieve relevant transcript chunks for the topic.
    2. Generate a grounded outline from the context.
    3. Expand into a ~1,250-word article with writing principles applied.
    """
    retrieval = RetrievalService(db, settings)

    try:
        llm = get_llm_provider(settings)
    except ProviderError as exc:
        return {
            "error": str(exc),
            "status": "error",
            "content": "",
            "word_count": 0,
            "sources": [],
        }

    skill = Ship30Skill(retrieval, llm)

    try:
        result = skill.generate(
            topic=request.topic,
            top_k=request.top_k,
            target_words=request.target_words,
        )
    except ValueError as exc:
        return {
            "error": str(exc),
            "status": "error",
            "content": "",
            "word_count": 0,
            "sources": [],
        }
    except ProviderError as exc:
        logger.error("LLM provider error during article generation: %s", exc)
        return {
            "error": f"LLM generation failed: {exc}",
            "status": "error",
            "content": "",
            "word_count": 0,
            "sources": [],
        }
    except Exception as exc:
        logger.exception("Unexpected error during article generation")
        return {
            "error": f"Unexpected error: {exc}",
            "status": "error",
            "content": "",
            "word_count": 0,
            "sources": [],
        }

    # If a session_id was provided, optionally persist the article.
    if request.session_id is not None:
        try:
            from app.schemas.session import MessageCreateRequest
            from app.services.session_service import SessionService

            svc = SessionService(db)
            svc.add_message(
                request.session_id,
                MessageCreateRequest(
                    role="assistant",
                    content=result.content,
                    metadata={
                        "skill": "ship30",
                        "topic": request.topic,
                        "word_count": result.word_count,
                        "sources": result.sources,
                    },
                ),
            )
        except Exception:
            logger.warning("Could not persist article to session %s", request.session_id)

    return {
        "status": "ok",
        "content": result.content,
        "word_count": result.word_count,
        "sources": result.sources,
        "model": result.model,
        "provider": result.provider,
    }
