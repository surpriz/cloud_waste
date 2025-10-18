"""Chat conversation and message Pydantic schemas."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ChatMessageBase(BaseModel):
    """Base chat message schema."""

    content: str = Field(min_length=1, max_length=4000, description="Message content")


class ChatMessageCreate(ChatMessageBase):
    """Schema for creating a chat message."""

    pass


class ChatMessageResponse(ChatMessageBase):
    """Schema for chat message response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: str  # 'user' or 'assistant'
    message_metadata: dict[str, Any] | None = None
    created_at: datetime


class ChatConversationBase(BaseModel):
    """Base chat conversation schema."""

    title: str = Field(min_length=1, max_length=255, description="Conversation title")


class ChatConversationCreate(ChatConversationBase):
    """Schema for creating a chat conversation."""

    pass


class ChatConversationUpdate(BaseModel):
    """Schema for updating a chat conversation."""

    title: str | None = Field(None, min_length=1, max_length=255)


class ChatConversationResponse(ChatConversationBase):
    """Schema for chat conversation response."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    messages: list[ChatMessageResponse] = []


class ChatConversationListItem(ChatConversationBase):
    """Schema for chat conversation list item (without messages)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ChatContextData(BaseModel):
    """Schema for user context data injected into chat."""

    total_waste_monthly: float = 0.0
    total_orphan_resources: int = 0
    last_scan_date: datetime | None = None
    top_resources: list[dict[str, Any]] = []
    by_type_summary: dict[str, int] = {}
    by_region_summary: dict[str, int] = {}


class ChatStreamChunk(BaseModel):
    """Schema for chat stream chunk (SSE)."""

    type: str = "content"  # 'content', 'done', 'error'
    content: str = ""
    metadata: dict[str, Any] | None = None
