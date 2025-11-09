"""Pydantic schemas for AWS SES metrics."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class SESMetrics(BaseModel):
    """AWS SES metrics schema."""

    # Send Statistics
    emails_sent_24h: int = Field(..., description="Emails sent in last 24 hours")
    emails_sent_7d: int = Field(..., description="Emails sent in last 7 days")
    emails_sent_30d: int = Field(..., description="Emails sent in last 30 days")

    # Deliverability Rates (percentages)
    delivery_rate: float = Field(..., ge=0, le=100, description="Delivery rate percentage")
    bounce_rate: float = Field(..., ge=0, le=100, description="Bounce rate percentage")
    complaint_rate: float = Field(..., ge=0, le=100, description="Complaint rate percentage")

    # Hard vs Soft Bounces
    hard_bounce_rate: float = Field(..., ge=0, le=100, description="Hard bounce rate percentage")
    soft_bounce_rate: float = Field(..., ge=0, le=100, description="Soft bounce rate percentage")

    # Send Quotas
    max_send_rate: float = Field(..., description="Maximum send rate (emails/second)")
    daily_quota: int = Field(..., description="Maximum emails per 24 hours")
    daily_sent: int = Field(..., description="Emails sent in current 24h period")
    quota_usage_percentage: float = Field(..., ge=0, le=100, description="Percentage of daily quota used")

    # Account Reputation & Status
    reputation_status: Literal["healthy", "under_review", "probation"] = Field(
        ..., description="Account reputation status"
    )
    sending_enabled: bool = Field(..., description="Whether sending is currently enabled")
    suppression_list_size: int = Field(..., description="Number of suppressed email addresses")

    # Alerts
    has_critical_alerts: bool = Field(..., description="Whether there are critical alerts")
    alerts: list[str] = Field(default_factory=list, description="List of alert messages")

    # Metadata
    last_updated: datetime = Field(..., description="When these metrics were last updated")
    region: str = Field(..., description="AWS region for this SES account")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "emails_sent_24h": 1250,
                "emails_sent_7d": 8400,
                "emails_sent_30d": 32100,
                "delivery_rate": 97.2,
                "bounce_rate": 2.1,
                "complaint_rate": 0.08,
                "hard_bounce_rate": 1.5,
                "soft_bounce_rate": 0.6,
                "max_send_rate": 14.0,
                "daily_quota": 50000,
                "daily_sent": 1250,
                "quota_usage_percentage": 2.5,
                "reputation_status": "healthy",
                "sending_enabled": True,
                "suppression_list_size": 45,
                "has_critical_alerts": False,
                "alerts": [],
                "last_updated": "2025-11-09T14:32:00Z",
                "region": "eu-north-1",
            }
        }
