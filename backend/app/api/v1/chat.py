"""Chat API endpoints with AI assistant."""

import uuid
from typing import Annotated, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

from app.api.deps import get_current_active_user, get_db
from app.core.config import settings
from app.crud import chat as chat_crud
from app.models.chat import ChatConversation, ChatMessage
from app.models.user import User
from app.schemas.chat import (
    ChatConversationCreate,
    ChatConversationListItem,
    ChatConversationResponse,
    ChatConversationUpdate,
    ChatMessageCreate,
)
from app.services import chat_service

router = APIRouter()


@router.post("/conversations", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conversation_data: ChatConversationCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ChatConversationResponse:
    """
    Create a new chat conversation.
    """
    conversation = await chat_crud.create_conversation(
        db, current_user.id, conversation_data
    )
    return ChatConversationResponse(
        id=conversation.id,
        user_id=conversation.user_id,
        title=conversation.title,
        created_at=conversation.created_at,
        updated_at=conversation.updated_at,
        messages=[],
    )


@router.get("/conversations", response_model=list[ChatConversationListItem])
async def list_conversations(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    skip: int = 0,
    limit: int = 20,
) -> list[ChatConversationListItem]:
    """
    List all conversations for the current user.
    """
    conversations = await chat_crud.get_user_conversations(
        db, current_user.id, skip, limit
    )

    # Get message counts for each conversation
    result = []
    for conv in conversations:
        msg_count = await chat_crud.get_conversation_message_count(db, conv.id)
        result.append(
            ChatConversationListItem(
                id=conv.id,
                user_id=conv.user_id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count,
            )
        )

    return result


@router.get("/conversations/{conversation_id}", response_model=ChatConversationResponse)
async def get_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ChatConversationResponse:
    """
    Get a specific conversation with all messages.
    """
    conversation = await chat_crud.get_conversation_by_id(
        db, conversation_id, current_user.id
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.patch("/conversations/{conversation_id}", response_model=ChatConversationResponse)
async def update_conversation(
    conversation_id: uuid.UUID,
    update_data: ChatConversationUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ChatConversationResponse:
    """
    Update a conversation (e.g., change title).
    """
    conversation = await chat_crud.update_conversation(
        db, conversation_id, current_user.id, update_data
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    return conversation


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Delete a conversation and all its messages.
    """
    success = await chat_crud.delete_conversation(
        db, conversation_id, current_user.id
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )


@router.post("/conversations/{conversation_id}/messages")
async def send_message(
    conversation_id: uuid.UUID,
    message_data: ChatMessageCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> EventSourceResponse:
    """
    Send a message and stream the AI response using Server-Sent Events.

    Returns a stream of text chunks as the AI generates the response.
    """
    # Verify conversation exists and belongs to user
    conversation = await chat_crud.get_conversation_by_id(
        db, conversation_id, current_user.id
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # Check rate limit
    message_count_today = await chat_crud.get_user_message_count_today(
        db, current_user.id
    )

    if message_count_today >= settings.CHAT_MAX_MESSAGES_PER_USER_PER_DAY:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Daily message limit reached ({settings.CHAT_MAX_MESSAGES_PER_USER_PER_DAY} messages/day)",
        )

    # Build user context
    context = await chat_service.build_user_context(db, current_user.id)

    # Stream response generator
    async def event_generator() -> AsyncGenerator[dict, None]:
        """Generate SSE events from Claude's streaming response."""
        try:
            async for chunk in chat_service.stream_chat_response(
                db=db,
                user_id=current_user.id,
                conversation_id=conversation_id,
                message=message_data.content,
                context=context,
            ):
                # Send each chunk as an SSE event
                yield {
                    "event": "message",
                    "data": chunk,
                }

            # Send completion event
            yield {
                "event": "done",
                "data": "complete",
            }

        except Exception as e:
            # Send error event
            yield {
                "event": "error",
                "data": str(e),
            }

    return EventSourceResponse(event_generator())
