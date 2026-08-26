import uuid
from datetime import UTC, datetime

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.models.chat_session import ChatSession
from app.models.message import Message
from app.schemas.session import MessageCreateRequest, SessionCreateRequest, SessionUpdateRequest

ALLOWED_MESSAGE_ROLES = {"user", "assistant", "system"}


class SessionService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_session(self, payload: SessionCreateRequest) -> ChatSession:
        title = payload.title.strip() if payload.title else "New chat"
        if not title:
            title = "New chat"

        session = ChatSession(title=title)
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def list_sessions(self) -> list[ChatSession]:
        message_count = func.count(Message.id).label("message_count")
        stmt = (
            select(ChatSession, message_count)
            .outerjoin(Message, Message.session_id == ChatSession.id)
            .group_by(ChatSession.id)
            .order_by(ChatSession.updated_at.desc())
        )
        rows = self.db.execute(stmt).all()
        sessions: list[ChatSession] = []
        for session, count in rows:
            session.message_count = int(count)
            sessions.append(session)
        return sessions

    def get_session(self, session_id: uuid.UUID) -> ChatSession:
        stmt = (
            select(ChatSession)
            .options(selectinload(ChatSession.messages))
            .where(ChatSession.id == session_id)
        )
        session = self.db.scalar(stmt)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} was not found.",
            )
        session.message_count = len(session.messages)
        return session

    def update_session(self, session_id: uuid.UUID, payload: SessionUpdateRequest) -> ChatSession:
        session = self._get_session_or_404(session_id)
        session.title = payload.title.strip()
        session.updated_at = datetime.now(UTC)
        self.db.commit()
        self.db.refresh(session)
        session.message_count = self._message_count(session_id)
        return session

    def add_message(self, session_id: uuid.UUID, payload: MessageCreateRequest) -> Message:
        if payload.role not in ALLOWED_MESSAGE_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Unsupported message role: {payload.role}",
            )

        session = self._get_session_or_404(session_id)
        message = Message(
            session_id=session.id,
            role=payload.role,
            content=payload.content.strip(),
            message_metadata=payload.metadata,
        )
        session.updated_at = datetime.now(UTC)
        self.db.add(message)
        self.db.commit()
        self.db.refresh(message)
        return message

    def list_messages(self, session_id: uuid.UUID) -> list[Message]:
        self._get_session_or_404(session_id)
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc())
        )
        return list(self.db.scalars(stmt).all())

    def _get_session_or_404(self, session_id: uuid.UUID) -> ChatSession:
        session = self.db.get(ChatSession, session_id)
        if session is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Session {session_id} was not found.",
            )
        return session

    def _message_count(self, session_id: uuid.UUID) -> int:
        stmt = select(func.count(Message.id)).where(Message.session_id == session_id)
        return int(self.db.scalar(stmt) or 0)
