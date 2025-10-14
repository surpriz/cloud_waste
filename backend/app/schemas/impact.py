"""Impact and savings Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ImpactSummary(BaseModel):
    """Summary of user's impact and savings."""

    # Financial Impact
    total_resources_detected: int = Field(description="Total orphan resources detected")
    total_resources_deleted: int = Field(description="Resources marked as deleted")
    total_resources_active: int = Field(description="Active orphan resources")
    total_resources_ignored: int = Field(description="Resources ignored by user")

    total_monthly_savings: float = Field(description="Monthly $ saved from deleted resources")
    total_annual_savings: float = Field(description="Annual $ saved (monthly × 12)")
    potential_monthly_savings: float = Field(description="Potential $ saved if all active resources deleted")
    already_wasted_total: float = Field(description="Total $ wasted before detection")

    # Environmental Impact
    total_co2_saved_kg: float = Field(description="Total CO2 emissions avoided (kg)")
    trees_equivalent: float = Field(description="Equivalent trees planted for 1 year")
    car_km_equivalent: float = Field(description="Equivalent car km not driven")
    home_days_equivalent: float = Field(description="Equivalent home electricity for X days")

    # Breakdown by Provider
    savings_by_provider: dict[str, float] = Field(
        description="Savings breakdown by cloud provider (aws, azure, gcp)"
    )
    co2_by_provider: dict[str, float] = Field(
        description="CO2 saved breakdown by provider"
    )

    # Breakdown by Resource Type
    savings_by_resource_type: dict[str, float] = Field(
        description="Savings breakdown by resource type"
    )
    resources_by_resource_type: dict[str, int] = Field(
        description="Count breakdown by resource type"
    )

    # User Engagement
    cleanup_rate: float = Field(
        description="Percentage of detected resources that were deleted (0-1)"
    )
    first_scan_date: datetime | None = Field(
        description="Date of user's first scan"
    )
    days_since_first_scan: int = Field(
        description="Days since user started using CloudWaste"
    )
    last_cleanup_date: datetime | None = Field(
        description="Date of last resource deletion"
    )
    cleanup_streak_days: int = Field(
        description="Current streak of consecutive days with cleanup"
    )


class TimelineDataPoint(BaseModel):
    """Single data point in timeline."""

    date: datetime = Field(description="Date of data point")
    resources_detected: int = Field(description="Resources detected on this date")
    resources_deleted: int = Field(description="Resources deleted on this date")
    monthly_savings: float = Field(description="$ saved on this date")
    co2_saved_kg: float = Field(description="CO2 saved on this date (kg)")
    cumulative_savings: float = Field(description="Cumulative $ saved up to this date")
    cumulative_co2: float = Field(description="Cumulative CO2 saved up to this date")


class ImpactTimeline(BaseModel):
    """Timeline data for charts."""

    period: str = Field(description="Period type: day, week, month, year, all")
    data_points: list[TimelineDataPoint] = Field(description="Timeline data")
    summary: dict[str, float] = Field(
        description="Summary stats for this period (total_savings, avg_daily_savings, etc.)"
    )


class Achievement(BaseModel):
    """User achievement/badge."""

    id: str = Field(description="Achievement ID (e.g., 'first_cleanup')")
    name: str = Field(description="Achievement name")
    description: str = Field(description="Achievement description")
    icon: str = Field(description="Achievement emoji/icon")
    unlocked: bool = Field(description="Whether user has unlocked this achievement")
    unlocked_at: datetime | None = Field(description="When achievement was unlocked")
    progress: float = Field(description="Progress towards unlock (0-1)")
    threshold: float = Field(description="Value required to unlock")
    current_value: float = Field(description="User's current value")
    category: str = Field(description="Category: financial, environmental, engagement")


class UserAchievements(BaseModel):
    """All user achievements."""

    achievements: list[Achievement] = Field(description="List of all achievements")
    total_unlocked: int = Field(description="Number of achievements unlocked")
    total_available: int = Field(description="Total number of achievements")
    completion_rate: float = Field(description="Percentage of achievements unlocked (0-1)")


class QuickStats(BaseModel):
    """Quick interesting stats for user."""

    biggest_cleanup_monthly_cost: float = Field(
        description="Biggest single cleanup (monthly cost)"
    )
    biggest_cleanup_resource_type: str | None = Field(
        description="Resource type of biggest cleanup"
    )
    most_common_resource_type: str | None = Field(
        description="Most commonly detected resource type"
    )
    most_common_resource_count: int = Field(
        description="Count of most common resource type"
    )
    fastest_cleanup_hours: float | None = Field(
        description="Fastest cleanup time (hours from detection to deletion)"
    )
    top_region: str | None = Field(
        description="Region with most resources detected"
    )
    top_region_count: int = Field(
        description="Count in top region"
    )
    average_resource_age_days: float = Field(
        description="Average age of detected resources (days)"
    )
