"""Detection Rules API endpoints."""

from typing import Annotated
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import detection_rule as detection_rule_crud
from app.models.detection_rule import DEFAULT_DETECTION_RULES
from app.models.resource_families import (
    RESOURCE_FAMILIES,
    AZURE_RESOURCE_FAMILIES,
    get_resource_family,
    get_family_scenarios,
    extract_common_params,
)
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


@router.get("/defaults/all", response_model=dict[str, dict])
async def get_all_defaults(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict[str, dict]:
    """
    Get all default detection rules (no database query needed).
    """
    return DEFAULT_DETECTION_RULES


@router.get("/grouped", response_model=list[dict])
async def get_grouped_detection_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> list[dict]:
    """
    Get detection rules grouped by resource family for Basic mode.

    Groups granular resource_types (e.g. ebs_volume_unattached, ebs_volume_idle, ...)
    into logical families (e.g. ebs_volume) for simplified configuration.

    Returns:
        List of grouped rules with:
        - resource_family: Family identifier (e.g. "ebs_volume")
        - label: Human-readable label (e.g. "EBS Volumes")
        - scenarios: List of individual resource_types in this family
        - scenario_count: Number of scenarios
        - common_params: Common parameters across scenarios
        - enabled: Whether detection is enabled for the family
        - is_customized: Whether any scenario has custom rules
    """
    # Get all user rules
    user_rules = await detection_rule_crud.get_user_rules(db, current_user.id)
    user_rules_map = {rule.resource_type: rule.rules for rule in user_rules}

    # Group rules by family
    families_dict = defaultdict(lambda: {
        "scenarios": [],
        "enabled_count": 0,
        "total_count": 0,
        "is_customized": False,
    })

    # Process all resource types
    all_families = {**RESOURCE_FAMILIES, **AZURE_RESOURCE_FAMILIES}

    for family, scenario_types in all_families.items():
        family_data = families_dict[family]
        family_data["resource_family"] = family
        family_data["scenario_count"] = len(scenario_types)

        # Collect scenario details
        for resource_type in scenario_types:
            if resource_type not in DEFAULT_DETECTION_RULES:
                continue

            default_rules = DEFAULT_DETECTION_RULES[resource_type]
            current_rules = user_rules_map.get(resource_type, default_rules)

            # Check if customized
            if resource_type in user_rules_map:
                family_data["is_customized"] = True

            # Count enabled scenarios
            if current_rules.get("enabled", True):
                family_data["enabled_count"] += 1

            family_data["total_count"] += 1

            # Add scenario details
            family_data["scenarios"].append({
                "resource_type": resource_type,
                "description": default_rules.get("description", ""),
                "enabled": current_rules.get("enabled", True),
                "is_customized": resource_type in user_rules_map,
            })

        # Extract common parameters from first scenario (if exists)
        if scenario_types and scenario_types[0] in DEFAULT_DETECTION_RULES:
            first_type = scenario_types[0]
            default_rules = DEFAULT_DETECTION_RULES[first_type]
            current_rules = user_rules_map.get(first_type, default_rules)
            family_data["common_params"] = extract_common_params(current_rules)
        else:
            family_data["common_params"] = {}

        # Family is "enabled" if at least one scenario is enabled
        family_data["enabled"] = family_data["enabled_count"] > 0

        # Generate label from family name
        family_data["label"] = family.replace("_", " ").title()

    # Convert to list and sort by family name
    result = sorted(families_dict.values(), key=lambda x: x["resource_family"])

    return result


@router.post("/grouped/bulk-update", status_code=status.HTTP_200_OK)
async def bulk_update_family_rules(
    family: str,
    rules_update: dict,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> dict:
    """
    Bulk update detection rules for all scenarios in a resource family.

    Used in Basic mode when user configures a family-level setting.

    Args:
        family: Resource family identifier (e.g. "ebs_volume")
        rules_update: Common rules to apply to all scenarios in the family

    Returns:
        Summary of updated scenarios
    """
    # Get all scenarios for this family
    scenario_types = get_family_scenarios(family)

    if not scenario_types:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Resource family '{family}' not found",
        )

    # Update each scenario
    updated_count = 0
    for resource_type in scenario_types:
        if resource_type not in DEFAULT_DETECTION_RULES:
            continue

        # Get default rules for this resource type
        default_rules = DEFAULT_DETECTION_RULES[resource_type]

        # Merge: start with defaults, override with common params from update
        merged_rules = {**default_rules}

        # Only update common parameters
        for key in ["enabled", "min_age_days", "confidence_threshold_days", "min_stopped_days"]:
            if key in rules_update:
                merged_rules[key] = rules_update[key]

        # Create or update rule
        await detection_rule_crud.create_or_update_rule(
            db, current_user.id, resource_type, merged_rules
        )
        updated_count += 1

    return {
        "family": family,
        "scenarios_updated": updated_count,
        "total_scenarios": len(scenario_types),
    }


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT)
async def reset_all_detection_rules(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> None:
    """
    Reset all detection rules to defaults.
    """
    await detection_rule_crud.reset_to_defaults(db, current_user.id)


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
