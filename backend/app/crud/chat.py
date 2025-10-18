"""CRUD operations for chat conversations and messages."""

import uuid
from datetime import datetime, timedelta

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.chat import ChatConversation, ChatMessage
from app.schemas.chat import ChatConversationCreate, ChatConversationUpdate, ChatMessageCreate


async def create_conversation(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_data: ChatConversationCreate,
) -> ChatConversation:
    """
    Create a new chat conversation.

    Args:
        db: Database session
        user_id: User ID
        conversation_data: Conversation creation data

    Returns:
        Created chat conversation
    """
    conversation = ChatConversation(
        user_id=user_id,
        title=conversation_data.title,
    )
    db.add(conversation)
    await db.commit()
    await db.refresh(conversation)
    return conversation


async def get_user_conversations(
    db: AsyncSession,
    user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 20,
) -> list[ChatConversation]:
    """
    Get all conversations for a user.

    Args:
        db: Database session
        user_id: User ID
        skip: Number of records to skip
        limit: Maximum number of records to return

    Returns:
        List of chat conversations
    """
    query = (
        select(ChatConversation)
        .where(ChatConversation.user_id == user_id)
        .order_by(ChatConversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_conversation_by_id(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID | None = None,
) -> ChatConversation | None:
    """
    Get a conversation by ID with all messages.

    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: Optional user ID for authorization check

    Returns:
        Chat conversation with messages, or None if not found
    """
    query = select(ChatConversation).where(
        ChatConversation.id == conversation_id
    ).options(selectinload(ChatConversation.messages))

    if user_id:
        query = query.where(ChatConversation.user_id == user_id)

    result = await db.execute(query)
    return result.scalar_one_or_none()


async def update_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    update_data: ChatConversationUpdate,
) -> ChatConversation | None:
    """
    Update a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID for authorization
        update_data: Update data

    Returns:
        Updated conversation, or None if not found
    """
    conversation = await get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return None

    if update_data.title is not None:
        conversation.title = update_data.title

    await db.commit()
    await db.refresh(conversation)
    return conversation


async def delete_conversation(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
) -> bool:
    """
    Delete a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        user_id: User ID for authorization

    Returns:
        True if deleted, False if not found
    """
    conversation = await get_conversation_by_id(db, conversation_id, user_id)
    if not conversation:
        return False

    await db.delete(conversation)
    await db.commit()
    return True


async def add_message(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    role: str,
    content: str,
    message_metadata: dict | None = None,
) -> ChatMessage:
    """
    Add a message to a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        role: Message role ('user' or 'assistant')
        content: Message content
        message_metadata: Optional metadata (tokens, cost, etc.)

    Returns:
        Created chat message
    """
    message = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        message_metadata=message_metadata,
    )
    db.add(message)

    # Update conversation updated_at timestamp
    query = select(ChatConversation).where(ChatConversation.id == conversation_id)
    result = await db.execute(query)
    conversation = result.scalar_one_or_none()
    if conversation:
        conversation.updated_at = datetime.utcnow()

    await db.commit()
    await db.refresh(message)
    return message


async def get_conversation_messages(
    db: AsyncSession,
    conversation_id: uuid.UUID,
    limit: int = 10,
) -> list[ChatMessage]:
    """
    Get recent messages for a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID
        limit: Maximum number of messages to return (default 10 for context)

    Returns:
        List of chat messages, ordered by creation time
    """
    query = (
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
    )
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_user_message_count_today(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> int:
    """
    Get the number of messages sent by a user today (for rate limiting).

    Args:
        db: Database session
        user_id: User ID

    Returns:
        Number of messages sent today
    """
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)

    query = (
        select(func.count(ChatMessage.id))
        .join(ChatConversation)
        .where(
            and_(
                ChatConversation.user_id == user_id,
                ChatMessage.role == "user",
                ChatMessage.created_at >= today_start,
            )
        )
    )
    result = await db.execute(query)
    return result.scalar() or 0


async def get_conversation_message_count(
    db: AsyncSession,
    conversation_id: uuid.UUID,
) -> int:
    """
    Get the number of messages in a conversation.

    Args:
        db: Database session
        conversation_id: Conversation ID

    Returns:
        Number of messages in the conversation
    """
    query = select(func.count(ChatMessage.id)).where(
        ChatMessage.conversation_id == conversation_id
    )
    result = await db.execute(query)
    return result.scalar() or 0
