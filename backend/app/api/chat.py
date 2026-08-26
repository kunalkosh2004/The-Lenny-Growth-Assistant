"""Chat API endpoint: grounded conversational assistant.

The ``POST /api/chat`` endpoint accepts a session ID and user message,
runs the grounded RAG pipeline, persists both messages, and returns
the assistant response with source citations.
"""

from __future__ import annotations

import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import get_db
from app.providers.base import ProviderError
from app.schemas.session import MessageResponse
from app.services.chat_service import ChatService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])


class ChatRequest(BaseModel):
    session_id: UUID
    message: str = Field(min_length=1, max_length=50000)
    top_k: int = Field(default=6, ge=1, le=20)


class ChatResponseSchema(BaseModel):
    message: MessageResponse
    sources: list[dict] = Field(default_factory=list)
    model: str = ""
    provider: str = ""
    usage: dict = Field(default_factory=dict)
    grounding_status: str = "grounded"


@router.post("", response_model=ChatResponseSchema, status_code=200)
def send_chat_message(
    request: ChatRequest,
    settings: Settings = Depends(get_settings),
    db: Session = Depends(get_db),
) -> dict:
    """Send a message through the grounded chat pipeline.

    Flow:
    1. Load conversation history for the session.
    2. Retrieve relevant transcript chunks via pgvector.
    3. Build a grounded prompt with context and history.
    4. Generate a response via the active LLM provider.
    5. Persist both user and assistant messages.
    6. Return the assistant message with source citations.
    """
    from app.schemas.session import MessageCreateRequest
    from app.services.session_service import SessionService

    session_svc = SessionService(db)

    # Verify session exists.
    session_svc.get_session(request.session_id)

    # Persist the user message.
    session_svc.add_message(
        request.session_id,
        MessageCreateRequest(role="user", content=request.message),
    )

    # Run the grounded chat pipeline.
    chat_svc = ChatService(db, settings)
    try:
        response = chat_svc.chat(
            session_id=request.session_id,
            user_message=request.message,
            top_k=request.top_k,
        )
    except ProviderError as exc:
        logger.error("LLM provider error: %s", exc)
        # Persist an error message so the user sees something in the UI.
        error_msg = session_svc.add_message(
            request.session_id,
            MessageCreateRequest(
                role="assistant",
                content=(
                    f"I encountered an error while generating a response: {exc}\n\n"
                    "Please check that the LLM provider is available and try again."
                ),
            ),
        )
        return {
            "message": _message_dict(error_msg),
            "sources": [],
            "model": "",
            "provider": "",
            "usage": {},
            "grounding_status": "error",
        }
    except Exception:
        logger.exception("Unexpected error during chat generation")
        error_msg = session_svc.add_message(
            request.session_id,
            MessageCreateRequest(
                role="assistant",
                content=(
                    "An unexpected error occurred while generating a response. "
                    "Please try again."
                ),
            ),
        )
        return {
            "message": _message_dict(error_msg),
            "sources": [],
            "model": "",
            "provider": "",
            "usage": {},
            "grounding_status": "error",
        }

    # Persist the assistant response.
    assistant_msg = session_svc.add_message(
        request.session_id,
        MessageCreateRequest(
            role="assistant",
            content=response.content,
            metadata={
                "sources": [s.to_dict() for s in response.sources],
                "model": response.model,
                "provider": response.provider,
            },
        ),
    )

    # Determine grounding status.
    grounding_status = "grounded"
    if not response.sources:
        grounding_status = "no_relevant_sources"

    return {
        "message": _message_dict(assistant_msg),
        "sources": [s.to_dict() for s in response.sources],
        "model": response.model,
        "provider": response.provider,
        "usage": response.usage,
        "grounding_status": grounding_status,
    }


def _message_dict(message) -> dict:
    return {
        "id": str(message.id),
        "session_id": str(message.session_id),
        "role": message.role,
        "content": message.content,
        "metadata": message.message_metadata or {},
        "created_at": message.created_at.isoformat() if message.created_at else None,
    }
