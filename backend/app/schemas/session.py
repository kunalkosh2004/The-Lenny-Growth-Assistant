from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SessionCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class SessionUpdateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)


class SessionSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionDetail(SessionSummary):
    messages: list["MessageResponse"] = Field(default_factory=list)


class MessageCreateRequest(BaseModel):
    role: str = Field(min_length=1, max_length=32)
    content: str = Field(min_length=1)
    metadata: dict = Field(default_factory=dict)


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: str
    content: str
    metadata: dict = Field(default_factory=dict)
    created_at: datetime


SessionDetail.model_rebuild()
