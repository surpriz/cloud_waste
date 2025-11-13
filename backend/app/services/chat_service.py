"""Chat service with Anthropic Claude integration and context building."""

import json
import uuid
from typing import Any, AsyncGenerator

import structlog
from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.crud import chat as chat_crud
from app.models.cloud_account import CloudAccount
from app.models.orphan_resource import OrphanResource
from app.models.scan import Scan
from app.schemas.chat import ChatContextData

logger = structlog.get_logger()


async def build_user_context(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> ChatContextData:
    """
    Build context data about user's cloud resources for the AI assistant.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        ChatContextData with user's resource summary
    """
    # Get latest scan summary across all user's accounts
    latest_scan_query = (
        select(Scan)
        .join(CloudAccount)
        .where(CloudAccount.user_id == user_id)
        .where(Scan.status == "completed")
        .order_by(Scan.created_at.desc())
        .limit(1)
    )
    result = await db.execute(latest_scan_query)
    latest_scan = result.scalar_one_or_none()

    # Get all orphan resources from latest scans per account
    latest_scan_subquery = (
        select(
            Scan.cloud_account_id,
            func.max(Scan.created_at).label("max_created_at")
        )
        .where(Scan.status == "completed")
        .group_by(Scan.cloud_account_id)
        .subquery()
    )

    latest_scan_ids = (
        select(Scan.id)
        .join(
            latest_scan_subquery,
            (Scan.cloud_account_id == latest_scan_subquery.c.cloud_account_id) &
            (Scan.created_at == latest_scan_subquery.c.max_created_at)
        )
        .join(CloudAccount)
        .where(CloudAccount.user_id == user_id)
        .subquery()
    )

    # Get all active orphan resources
    orphan_resources_query = (
        select(OrphanResource)
        .where(OrphanResource.scan_id.in_(select(latest_scan_ids)))
        .where(OrphanResource.status == "active")
        .order_by(OrphanResource.estimated_monthly_cost.desc())
        .limit(settings.CHAT_CONTEXT_MAX_RESOURCES)
    )
    result = await db.execute(orphan_resources_query)
    top_resources = list(result.scalars().all())

    # Calculate aggregates
    total_waste = sum(r.estimated_monthly_cost for r in top_resources)

    # Group by type and region
    by_type: dict[str, int] = {}
    by_region: dict[str, int] = {}

    for resource in top_resources:
        by_type[resource.resource_type] = by_type.get(resource.resource_type, 0) + 1
        by_region[resource.region] = by_region.get(resource.region, 0) + 1

    # Build context
    context = ChatContextData(
        total_waste_monthly=round(total_waste, 2),
        total_orphan_resources=len(top_resources),
        last_scan_date=latest_scan.created_at if latest_scan else None,
        top_resources=[
            {
                "type": r.resource_type,
                "id": r.resource_id[:20] + "..." if len(r.resource_id) > 20 else r.resource_id,
                "name": r.resource_name,
                "region": r.region,
                "cost_monthly": round(r.estimated_monthly_cost, 2),
                "metadata": r.resource_metadata or {},
            }
            for r in top_resources[:10]  # Top 10 only
        ],
        by_type_summary=by_type,
        by_region_summary=by_region,
    )

    return context


def build_system_prompt(context: ChatContextData) -> str:
    """
    Build the system prompt with user context.

    Args:
        context: User context data

    Returns:
        System prompt string
    """
    return f"""You are a FinOps AI Assistant for CutCosts, a platform that detects orphaned and unused cloud resources.

Your role is to help users understand their cloud waste, prioritize cost optimization actions, and explain technical findings in clear, actionable language.

# User's Current Context

**Total Orphan Resources:** {context.total_orphan_resources}
**Estimated Monthly Waste:** ${context.total_waste_monthly:.2f}
**Last Scan:** {context.last_scan_date.strftime('%Y-%m-%d %H:%M UTC') if context.last_scan_date else 'Never'}

**Resources by Type:**
{json.dumps(context.by_type_summary, indent=2)}

**Resources by Region:**
{json.dumps(context.by_region_summary, indent=2)}

**Top Cost Resources:**
{json.dumps(context.top_resources[:5], indent=2)}

# Guidelines

1. **Be Concise**: Provide clear, actionable answers. Use bullet points for clarity.
2. **Prioritize by Impact**: When recommending actions, focus on highest cost savings first.
3. **Explain Technical Terms**: If using cloud terminology (EBS, ALB, etc.), briefly explain.
4. **Add Context**: When analyzing resources, explain WHY they were detected (e.g., "no traffic for 90+ days").
5. **Risk Assessment**: Always mention risk level when recommending deletions (Safe, Low, Medium, High).
6. **No Hallucinations**: Only reference data from the context above. If you don't have specific information, say so.
7. **French-friendly**: User may ask questions in French - respond in the same language as the question.

# Example Response Format

When asked about cost optimization:
> **🎯 Quick Wins ($XXX/month):**
>
> 1. **Resource Type** - $XX/month
>    - Detection reason
>    - ✅ Action recommendation
>    - Risk: Low/Medium/High
>
> **📊 Next Steps:**
> - Prioritized action list

Remember: Your goal is to make cloud cost optimization accessible to both technical and non-technical users.
"""


async def stream_chat_response(
    db: AsyncSession,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    message: str,
    context: ChatContextData,
) -> AsyncGenerator[str, None]:
    """
    Stream a chat response from Claude with user context.

    Args:
        db: Database session
        user_id: User ID
        conversation_id: Conversation ID
        message: User message
        context: User context data

    Yields:
        Text chunks from Claude's response
    """
    try:
        # Get conversation history (last 10 messages for context window)
        history = await chat_crud.get_conversation_messages(
            db, conversation_id, limit=10
        )

        # Build messages array for Claude
        messages = []
        for msg in history:
            messages.append({
                "role": msg.role,
                "content": msg.content,
            })

        # Add current user message
        messages.append({
            "role": "user",
            "content": message,
        })

        # Initialize Anthropic client
        client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

        # Build system prompt with context
        system_prompt = build_system_prompt(context)

        logger.info(
            "chat.request",
            user_id=str(user_id),
            conversation_id=str(conversation_id),
            message_length=len(message),
            history_length=len(messages) - 1,
        )

        # Stream response from Claude
        full_response = ""
        input_tokens = 0
        output_tokens = 0

        async with client.messages.stream(
            model=settings.CHAT_MODEL,
            max_tokens=2048,
            system=system_prompt,
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                full_response += text
                yield text

            # Get final message for token counts
            final_message = await stream.get_final_message()
            input_tokens = final_message.usage.input_tokens
            output_tokens = final_message.usage.output_tokens

        # Calculate cost (Haiku 4.5 pricing)
        cost_input = (input_tokens / 1_000_000) * 0.25  # $0.25 per 1M tokens
        cost_output = (output_tokens / 1_000_000) * 1.25  # $1.25 per 1M tokens
        total_cost = cost_input + cost_output

        # Save user message to DB
        await chat_crud.add_message(
            db,
            conversation_id=conversation_id,
            role="user",
            content=message,
        )

        # Save assistant response to DB with message_metadata
        await chat_crud.add_message(
            db,
            conversation_id=conversation_id,
            role="assistant",
            content=full_response,
            message_metadata={
                "tokens_input": input_tokens,
                "tokens_output": output_tokens,
                "cost_usd": round(total_cost, 6),
                "model": settings.CHAT_MODEL,
            },
        )

        logger.info(
            "chat.response",
            user_id=str(user_id),
            conversation_id=str(conversation_id),
            tokens_input=input_tokens,
            tokens_output=output_tokens,
            cost_usd=round(total_cost, 6),
        )

    except Exception as e:
        logger.error(
            "chat.error",
            user_id=str(user_id),
            conversation_id=str(conversation_id),
            error=str(e),
        )
        yield f"\n\n⚠️ Error: {str(e)}"
