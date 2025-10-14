"""Impact and savings API endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_user, get_db
from app.crud import impact as impact_crud
from app.models.user import User
from app.schemas.impact import (
    ImpactSummary,
    ImpactTimeline,
    QuickStats,
    UserAchievements,
)

router = APIRouter()


@router.get("/summary", response_model=ImpactSummary)
async def get_impact_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> ImpactSummary:
    """
    Get comprehensive impact summary for user.

    Returns financial savings, environmental impact (CO2), breakdowns by provider
    and resource type, and engagement metrics.

    **Financial Metrics:**
    - Total monthly/annual savings from deleted resources
    - Potential savings from active resources
    - Already wasted costs

    **Environmental Impact:**
    - CO2 emissions avoided (kg)
    - Tree planting equivalents
    - Car km equivalents
    - Home electricity equivalents

    **Engagement:**
    - Cleanup rate (% of resources deleted)
    - First scan date
    - Last cleanup date
    - Current cleanup streak
    """
    return await impact_crud.get_impact_summary(db, current_user.id)


@router.get("/timeline", response_model=ImpactTimeline)
async def get_impact_timeline(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
    period: str = Query(
        "month",
        description="Period grouping: 'day', 'week', 'month', 'year', 'all'",
        regex="^(day|week|month|year|all)$",
    ),
) -> ImpactTimeline:
    """
    Get timeline data for impact charts.

    Groups data by specified period (day/week/month/year/all) and returns
    time-series data including:
    - Resources detected/deleted per period
    - Monthly savings per period
    - CO2 saved per period
    - Cumulative values over time

    **Use Cases:**
    - Display savings trend charts
    - Show growth in environmental impact
    - Visualize user engagement over time

    **Parameters:**
    - `period`: Grouping interval
      - `day`: Daily data points (last 30 days)
      - `week`: Weekly data points (last 12 weeks)
      - `month`: Monthly data points (last 12 months)
      - `year`: Yearly data points (all years)
      - `all`: All-time data grouped by month
    """
    return await impact_crud.get_impact_timeline(db, current_user.id, period)


@router.get("/achievements", response_model=UserAchievements)
async def get_user_achievements(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> UserAchievements:
    """
    Get user achievements and badges (gamification).

    Returns all available achievements with unlock status, progress, and metadata.

    **Achievement Categories:**

    **Engagement Achievements:**
    - First Steps 🥉: Delete your first resource
    - Speed Demon ⚡: Delete 10+ resources in 24 hours
    - Perfectionist 🎯: Maintain 90%+ cleanup rate
    - Marathon Runner 🏃: Cleanup streak of 30+ days
    - Early Adopter 🚀: Delete within 1 hour of detection

    **Financial Achievements:**
    - Eco Warrior 🌱: Save $100+/month
    - Cloud Optimizer 🥇: Save $1,000+/month
    - Cost Crusher 💰: Save $5,000+/month

    **Environmental Achievements:**
    - Carbon Hero 🌍: Save 100+ kg CO2
    - Tree Planter 🌳: Equivalent to 100 trees planted

    **Response includes:**
    - All achievements with unlock status
    - Progress towards locked achievements (0-1)
    - Unlock dates for completed achievements
    - Overall completion rate
    """
    return await impact_crud.get_user_achievements(db, current_user.id)


@router.get("/quick-stats", response_model=QuickStats)
async def get_quick_stats(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> QuickStats:
    """
    Get quick interesting statistics for user.

    Returns fun and engaging stats to display on impact dashboard:
    - Biggest single cleanup (resource with highest monthly cost)
    - Most common resource type detected
    - Fastest cleanup time (detection to deletion)
    - Top region by resource count
    - Average resource age at detection

    **Use Cases:**
    - Display "Did You Know?" style facts
    - Highlight user's biggest wins
    - Show patterns in user's cloud waste
    """
    return await impact_crud.get_quick_stats(db, current_user.id)
