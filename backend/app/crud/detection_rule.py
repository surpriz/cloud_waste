"""CRUD operations for detection rules."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.detection_rule import DEFAULT_DETECTION_RULES, DetectionRule
from app.schemas.detection_rule import DetectionRuleCreate, DetectionRuleUpdate


async def get_user_rules(
    db: AsyncSession, user_id: uuid.UUID
) -> list[DetectionRule]:
    """
    Get all detection rules for a user.

    If user has no custom rules, returns empty list (defaults will be used).

    Args:
        db: Database session
        user_id: User UUID

    Returns:
        List of detection rule objects
    """
    result = await db.execute(
        select(DetectionRule).where(DetectionRule.user_id == user_id)
    )
    return list(result.scalars().all())


async def get_rule_by_type(
    db: AsyncSession, user_id: uuid.UUID, resource_type: str
) -> DetectionRule | None:
    """
    Get detection rule for a specific resource type.

    Args:
        db: Database session
        user_id: User UUID
        resource_type: Resource type (e.g., 'ebs_volume')

    Returns:
        Detection rule object or None if not found
    """
    result = await db.execute(
        select(DetectionRule).where(
            DetectionRule.user_id == user_id,
            DetectionRule.resource_type == resource_type,
        )
    )
    return result.scalar_one_or_none()


async def get_effective_rules(
    db: AsyncSession, user_id: uuid.UUID, resource_type: str
) -> dict:
    """
    Get effective detection rules for a resource type.

    Returns user's custom rules if they exist, otherwise returns defaults.

    Args:
        db: Database session
        user_id: User UUID
        resource_type: Resource type (e.g., 'ebs_volume')

    Returns:
        Dictionary with detection rules
    """
    custom_rule = await get_rule_by_type(db, user_id, resource_type)

    if custom_rule:
        return custom_rule.rules

    # Return defaults
    return DEFAULT_DETECTION_RULES.get(resource_type, {})


async def create_or_update_rule(
    db: AsyncSession,
    user_id: uuid.UUID,
    resource_type: str,
    rules: dict,
) -> DetectionRule:
    """
    Create or update a detection rule.

    Args:
        db: Database session
        user_id: User UUID
        resource_type: Resource type
        rules: Detection rules dictionary

    Returns:
        Created or updated detection rule object
    """
    # Check if rule already exists
    existing_rule = await get_rule_by_type(db, user_id, resource_type)

    if existing_rule:
        # Update existing rule
        existing_rule.rules = rules
        await db.commit()
        await db.refresh(existing_rule)
        return existing_rule
    else:
        # Create new rule
        new_rule = DetectionRule(
            user_id=user_id,
            resource_type=resource_type,
            rules=rules,
        )
        db.add(new_rule)
        await db.commit()
        await db.refresh(new_rule)
        return new_rule


async def reset_to_defaults(
    db: AsyncSession, user_id: uuid.UUID, resource_type: str | None = None
) -> int:
    """
    Reset detection rules to defaults.

    Args:
        db: Database session
        user_id: User UUID
        resource_type: Optional resource type (if None, resets all)

    Returns:
        Number of rules deleted
    """
    if resource_type:
        # Delete specific rule
        result = await db.execute(
            select(DetectionRule).where(
                DetectionRule.user_id == user_id,
                DetectionRule.resource_type == resource_type,
            )
        )
        rule = result.scalar_one_or_none()
        if rule:
            await db.delete(rule)
            await db.commit()
            return 1
        return 0
    else:
        # Delete all user rules
        result = await db.execute(
            select(DetectionRule).where(DetectionRule.user_id == user_id)
        )
        rules = result.scalars().all()
        count = len(rules)
        for rule in rules:
            await db.delete(rule)
        await db.commit()
        return count
