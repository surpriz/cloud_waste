"""Detection Rules API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import detection_rule as detection_rule_crud
from app.models.detection_rule import DEFAULT_DETECTION_RULES
from app.models.user import User
from app.schemas.detection_rule import (
    DetectionRule,
    DetectionRuleCreate,
    DetectionRuleUpdate,
    DetectionRuleWithDefaults,
)

router = APIRouter()


@router.get("/", response_model=list[DetectionRuleWithDefaults])
async def list_detection_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[DetectionRuleWithDefaults]:
    """
    Get all detection rules for the current user with defaults.

    Returns both custom rules and default rules for comparison.
    """
    user_rules = await detection_rule_crud.get_user_rules(db, current_user.id)

    # Create a map of user's custom rules
    user_rules_map = {rule.resource_type: rule.rules for rule in user_rules}

    # Build response with defaults
    result = []
    for resource_type, default_rules in DEFAULT_DETECTION_RULES.items():
        current_rules = user_rules_map.get(resource_type, default_rules)
        result.append(
            DetectionRuleWithDefaults(
                resource_type=resource_type,
                current_rules=current_rules,
                default_rules=default_rules,
                description=default_rules.get("description", ""),
            )
        )

    return result


@router.get("/{resource_type}", response_model=DetectionRuleWithDefaults)
async def get_detection_rule(
    resource_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DetectionRuleWithDefaults:
    """
    Get detection rule for a specific resource type.
    """
    if resource_type not in DEFAULT_DETECTION_RULES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource type '{resource_type}' not found",
        )

    effective_rules = await detection_rule_crud.get_effective_rules(
        db, current_user.id, resource_type
    )
    default_rules = DEFAULT_DETECTION_RULES[resource_type]

    return DetectionRuleWithDefaults(
        resource_type=resource_type,
        current_rules=effective_rules,
        default_rules=default_rules,
        description=default_rules.get("description", ""),
    )


@router.put("/{resource_type}", response_model=DetectionRule)
async def update_detection_rule(
    resource_type: str,
    rule_update: DetectionRuleUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> DetectionRule:
    """
    Update or create detection rule for a resource type.
    """
    if resource_type not in DEFAULT_DETECTION_RULES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource type '{resource_type}' not found",
        )

    if not rule_update.rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rules cannot be empty",
        )

    updated_rule = await detection_rule_crud.create_or_update_rule(
        db, current_user.id, resource_type, rule_update.rules
    )

    return updated_rule


@router.delete("/{resource_type}", status_code=status.HTTP_204_NO_CONTENT)
async def reset_detection_rule(
    resource_type: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Reset detection rule to defaults for a resource type.
    """
    if resource_type not in DEFAULT_DETECTION_RULES:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource type '{resource_type}' not found",
        )

    await detection_rule_crud.reset_to_defaults(
        db, current_user.id, resource_type
    )


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def reset_all_detection_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Reset all detection rules to defaults.
    """
    await detection_rule_crud.reset_to_defaults(db, current_user.id)


@router.get("/defaults/all", response_model=dict[str, dict])
async def get_all_defaults(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, dict]:
    """
    Get all default detection rules (no database query needed).
    """
    return DEFAULT_DETECTION_RULES
