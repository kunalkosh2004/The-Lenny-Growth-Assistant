from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.session import (
    MessageCreateRequest,
    MessageResponse,
    SessionCreateRequest,
    SessionDetail,
    SessionSummary,
    SessionUpdateRequest,
)
from app.services.session_service import SessionService

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


def get_session_service(db: Session = Depends(get_db)) -> SessionService:
    return SessionService(db)


def _to_message_response(message) -> MessageResponse:
    return MessageResponse(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        metadata=message.message_metadata,
        created_at=message.created_at,
    )


def _to_session_summary(session) -> SessionSummary:
    return SessionSummary(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=getattr(session, "message_count", 0),
    )


def _to_session_detail(session) -> SessionDetail:
    return SessionDetail(
        id=session.id,
        title=session.title,
        created_at=session.created_at,
        updated_at=session.updated_at,
        message_count=getattr(session, "message_count", len(session.messages)),
        messages=[_to_message_response(message) for message in session.messages],
    )


@router.post("", response_model=SessionSummary, status_code=201)
def create_session(
    payload: SessionCreateRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionSummary:
    session = service.create_session(payload)
    return _to_session_summary(session)


@router.get("", response_model=list[SessionSummary])
def list_sessions(service: SessionService = Depends(get_session_service)) -> list[SessionSummary]:
    sessions = service.list_sessions()
    return [_to_session_summary(session) for session in sessions]


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(
    session_id: UUID,
    service: SessionService = Depends(get_session_service),
) -> SessionDetail:
    session = service.get_session(session_id)
    return _to_session_detail(session)


@router.patch("/{session_id}", response_model=SessionSummary)
def update_session(
    session_id: UUID,
    payload: SessionUpdateRequest,
    service: SessionService = Depends(get_session_service),
) -> SessionSummary:
    session = service.update_session(session_id, payload)
    return _to_session_summary(session)


@router.delete("/{session_id}", status_code=204)
def delete_session(
    session_id: UUID,
    service: SessionService = Depends(get_session_service),
) -> Response:
    service.delete_session(session_id)
    return Response(status_code=204)


@router.post("/{session_id}/messages", response_model=MessageResponse, status_code=201)
def create_message(
    session_id: UUID,
    payload: MessageCreateRequest,
    service: SessionService = Depends(get_session_service),
) -> MessageResponse:
    message = service.add_message(session_id, payload)
    return _to_message_response(message)


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(
    session_id: UUID,
    service: SessionService = Depends(get_session_service),
) -> list[MessageResponse]:
    messages = service.list_messages(session_id)
    return [_to_message_response(message) for message in messages]
