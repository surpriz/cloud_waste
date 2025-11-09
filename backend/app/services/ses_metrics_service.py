"""Service for fetching AWS SES metrics and statistics."""

import logging
from datetime import datetime, timedelta
from typing import Literal

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings
from app.schemas.ses_metrics import SESMetrics

logger = logging.getLogger(__name__)


class SESMetricsService:
    """Service for retrieving AWS SES metrics."""

    def __init__(self, region: str | None = None):
        """
        Initialize SES metrics service.

        Args:
            region: AWS region (defaults to settings.AWS_SES_REGION or 'eu-north-1')
        """
        self.region = region or getattr(settings, "AWS_SES_REGION", "eu-north-1")

        # Use dedicated SES credentials if available, otherwise use default AWS credentials
        aws_access_key = getattr(settings, "AWS_SES_ACCESS_KEY_ID", None) or getattr(
            settings, "AWS_ACCESS_KEY_ID", None
        )
        aws_secret_key = getattr(settings, "AWS_SES_SECRET_ACCESS_KEY", None) or getattr(
            settings, "AWS_SECRET_ACCESS_KEY", None
        )

        session_kwargs = {"region_name": self.region}
        if aws_access_key and aws_secret_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key,
                    "aws_secret_access_key": aws_secret_key,
                }
            )

        self.ses_client = boto3.client("ses", **session_kwargs)
        self.sesv2_client = boto3.client("sesv2", **session_kwargs)
        self.cloudwatch_client = boto3.client("cloudwatch", **session_kwargs)

    async def get_ses_metrics(self) -> SESMetrics:
        """
        Get comprehensive SES metrics including send statistics, reputation, and quotas.

        Returns:
            SESMetrics object with all relevant metrics

        Raises:
            Exception: If unable to fetch SES metrics
        """
        try:
            # Fetch all metrics in parallel (synchronous boto3 calls)
            send_stats = self._get_send_statistics()
            send_quota = self._get_send_quota()
            reputation = self._get_reputation_metrics()
            suppression_count = self._get_suppression_list_size()
            sending_enabled = self._is_sending_enabled()

            # Calculate metrics
            emails_24h, emails_7d, emails_30d = self._calculate_send_volumes(send_stats)
            delivery_rate, bounce_rate, complaint_rate = self._calculate_rates(send_stats)
            hard_bounce_rate, soft_bounce_rate = self._calculate_bounce_breakdown(send_stats)

            # Determine reputation status
            reputation_status = self._determine_reputation_status(
                bounce_rate, complaint_rate, reputation
            )

            # Generate alerts
            alerts, has_critical_alerts = self._generate_alerts(
                bounce_rate, complaint_rate, reputation_status, sending_enabled
            )

            # Calculate quota usage
            quota_usage_percentage = (send_quota["daily_sent"] / send_quota["daily_quota"] * 100) if send_quota["daily_quota"] > 0 else 0.0

            return SESMetrics(
                emails_sent_24h=emails_24h,
                emails_sent_7d=emails_7d,
                emails_sent_30d=emails_30d,
                delivery_rate=delivery_rate,
                bounce_rate=bounce_rate,
                complaint_rate=complaint_rate,
                hard_bounce_rate=hard_bounce_rate,
                soft_bounce_rate=soft_bounce_rate,
                max_send_rate=send_quota["max_send_rate"],
                daily_quota=send_quota["daily_quota"],
                daily_sent=send_quota["daily_sent"],
                quota_usage_percentage=round(quota_usage_percentage, 2),
                reputation_status=reputation_status,
                sending_enabled=sending_enabled,
                suppression_list_size=suppression_count,
                has_critical_alerts=has_critical_alerts,
                alerts=alerts,
                last_updated=datetime.utcnow(),
                region=self.region,
            )

        except (BotoCoreError, ClientError) as e:
            logger.error(f"Error fetching SES metrics: {e}")
            raise Exception(f"Failed to fetch SES metrics: {str(e)}")

    def _get_send_statistics(self) -> list[dict]:
        """
        Get send statistics from SES (last 14 days).

        Returns:
            List of send data points
        """
        try:
            response = self.ses_client.get_send_statistics()
            return response.get("SendDataPoints", [])
        except (BotoCoreError, ClientError) as e:
            logger.warning(f"Could not fetch send statistics: {e}")
            return []

    def _get_send_quota(self) -> dict:
        """
        Get SES send quota information.

        Returns:
            Dictionary with max_send_rate, daily_quota, and daily_sent
        """
        try:
            response = self.ses_client.get_send_quota()
            return {
                "max_send_rate": response.get("MaxSendRate", 0),
                "daily_quota": int(response.get("Max24HourSend", 0)),
                "daily_sent": int(response.get("SentLast24Hours", 0)),
            }
        except (BotoCoreError, ClientError) as e:
            logger.warning(f"Could not fetch send quota: {e}")
            return {"max_send_rate": 0, "daily_quota": 0, "daily_sent": 0}

    def _is_sending_enabled(self) -> bool:
        """
        Check if sending is enabled for the account.

        Returns:
            True if sending is enabled, False otherwise
        """
        try:
            response = self.ses_client.get_account_sending_enabled()
            return response.get("Enabled", False)
        except (BotoCoreError, ClientError) as e:
            logger.warning(f"Could not check sending status: {e}")
            return False

    def _get_reputation_metrics(self) -> dict:
        """
        Get reputation metrics from CloudWatch.

        Returns:
            Dictionary with bounce_rate and complaint_rate from CloudWatch
        """
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(days=7)

            # Get bounce rate
            bounce_response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/SES",
                MetricName="Reputation.BounceRate",
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,  # 1 day
                Statistics=["Average"],
            )

            # Get complaint rate
            complaint_response = self.cloudwatch_client.get_metric_statistics(
                Namespace="AWS/SES",
                MetricName="Reputation.ComplaintRate",
                StartTime=start_time,
                EndTime=end_time,
                Period=86400,
                Statistics=["Average"],
            )

            # Extract latest values
            bounce_datapoints = bounce_response.get("Datapoints", [])
            complaint_datapoints = complaint_response.get("Datapoints", [])

            latest_bounce = (
                sorted(bounce_datapoints, key=lambda x: x["Timestamp"], reverse=True)[0][
                    "Average"
                ]
                if bounce_datapoints
                else 0.0
            )

            latest_complaint = (
                sorted(complaint_datapoints, key=lambda x: x["Timestamp"], reverse=True)[0][
                    "Average"
                ]
                if complaint_datapoints
                else 0.0
            )

            return {
                "bounce_rate": latest_bounce * 100,  # Convert to percentage
                "complaint_rate": latest_complaint * 100,
            }

        except (BotoCoreError, ClientError) as e:
            logger.warning(f"Could not fetch reputation metrics from CloudWatch: {e}")
            return {"bounce_rate": 0.0, "complaint_rate": 0.0}

    def _get_suppression_list_size(self) -> int:
        """
        Get the number of suppressed email addresses.

        Returns:
            Count of suppressed addresses
        """
        try:
            # Note: ListSuppressedDestinations requires pagination for large lists
            response = self.sesv2_client.list_suppressed_destinations(PageSize=1)
            # AWS doesn't directly return count, we'd need to paginate
            # For simplicity, return 0 if API call succeeds but no direct count available
            # In production, you might want to implement full pagination
            return 0  # Placeholder - would need pagination to get accurate count
        except (BotoCoreError, ClientError) as e:
            logger.warning(f"Could not fetch suppression list: {e}")
            return 0

    def _calculate_send_volumes(self, send_stats: list[dict]) -> tuple[int, int, int]:
        """
        Calculate send volumes for different time periods.

        Args:
            send_stats: List of send data points

        Returns:
            Tuple of (emails_24h, emails_7d, emails_30d)
        """
        now = datetime.utcnow()
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)
        cutoff_30d = now - timedelta(days=30)

        emails_24h = sum(
            int(dp.get("DeliveryAttempts", 0))
            for dp in send_stats
            if dp.get("Timestamp") and dp["Timestamp"].replace(tzinfo=None) >= cutoff_24h
        )

        emails_7d = sum(
            int(dp.get("DeliveryAttempts", 0))
            for dp in send_stats
            if dp.get("Timestamp") and dp["Timestamp"].replace(tzinfo=None) >= cutoff_7d
        )

        emails_30d = sum(
            int(dp.get("DeliveryAttempts", 0))
            for dp in send_stats
            if dp.get("Timestamp") and dp["Timestamp"].replace(tzinfo=None) >= cutoff_30d
        )

        return emails_24h, emails_7d, emails_30d

    def _calculate_rates(self, send_stats: list[dict]) -> tuple[float, float, float]:
        """
        Calculate delivery, bounce, and complaint rates.

        Args:
            send_stats: List of send data points

        Returns:
            Tuple of (delivery_rate, bounce_rate, complaint_rate) as percentages
        """
        if not send_stats:
            return 0.0, 0.0, 0.0

        # Aggregate last 7 days
        now = datetime.utcnow()
        cutoff_7d = now - timedelta(days=7)

        recent_stats = [
            dp
            for dp in send_stats
            if dp.get("Timestamp") and dp["Timestamp"].replace(tzinfo=None) >= cutoff_7d
        ]

        if not recent_stats:
            return 0.0, 0.0, 0.0

        total_attempts = sum(int(dp.get("DeliveryAttempts", 0)) for dp in recent_stats)
        total_bounces = sum(int(dp.get("Bounces", 0)) for dp in recent_stats)
        total_complaints = sum(int(dp.get("Complaints", 0)) for dp in recent_stats)
        total_rejects = sum(int(dp.get("Rejects", 0)) for dp in recent_stats)

        if total_attempts == 0:
            return 0.0, 0.0, 0.0

        delivery_rate = ((total_attempts - total_bounces - total_rejects) / total_attempts) * 100
        bounce_rate = (total_bounces / total_attempts) * 100
        complaint_rate = (total_complaints / total_attempts) * 100

        return round(delivery_rate, 2), round(bounce_rate, 2), round(complaint_rate, 2)

    def _calculate_bounce_breakdown(self, send_stats: list[dict]) -> tuple[float, float]:
        """
        Calculate hard bounce vs soft bounce rates.

        Note: AWS SES doesn't directly differentiate hard/soft bounces in send statistics.
        This is an approximation based on total bounces.

        Args:
            send_stats: List of send data points

        Returns:
            Tuple of (hard_bounce_rate, soft_bounce_rate) as percentages
        """
        # Simplified approximation: assume 70% hard bounces, 30% soft bounces
        # In production, you'd need to parse SNS notifications for accurate breakdown
        _, bounce_rate, _ = self._calculate_rates(send_stats)
        hard_bounce_rate = bounce_rate * 0.7
        soft_bounce_rate = bounce_rate * 0.3

        return round(hard_bounce_rate, 2), round(soft_bounce_rate, 2)

    def _determine_reputation_status(
        self, bounce_rate: float, complaint_rate: float, reputation: dict
    ) -> Literal["healthy", "under_review", "probation"]:
        """
        Determine account reputation status based on metrics.

        Args:
            bounce_rate: Current bounce rate
            complaint_rate: Current complaint rate
            reputation: Reputation metrics from CloudWatch

        Returns:
            Reputation status
        """
        # AWS thresholds (approximate):
        # Bounce rate: >5% = warning, >10% = probation
        # Complaint rate: >0.1% = warning, >0.5% = probation

        if bounce_rate > 10 or complaint_rate > 0.5:
            return "probation"
        elif bounce_rate > 5 or complaint_rate > 0.1:
            return "under_review"
        else:
            return "healthy"

    def _generate_alerts(
        self,
        bounce_rate: float,
        complaint_rate: float,
        reputation_status: str,
        sending_enabled: bool,
    ) -> tuple[list[str], bool]:
        """
        Generate alert messages based on metrics.

        Args:
            bounce_rate: Current bounce rate
            complaint_rate: Current complaint rate
            reputation_status: Account reputation status
            sending_enabled: Whether sending is enabled

        Returns:
            Tuple of (alerts list, has_critical_alerts boolean)
        """
        alerts = []
        has_critical = False

        # Critical alerts
        if not sending_enabled:
            alerts.append("🚨 CRITICAL: Sending is DISABLED for this account")
            has_critical = True

        if bounce_rate > 10:
            alerts.append(f"🚨 CRITICAL: Bounce rate is {bounce_rate}% (threshold: 10%)")
            has_critical = True

        if complaint_rate > 0.5:
            alerts.append(f"🚨 CRITICAL: Complaint rate is {complaint_rate}% (threshold: 0.5%)")
            has_critical = True

        if reputation_status == "probation":
            alerts.append("🚨 CRITICAL: Account reputation is on PROBATION")
            has_critical = True

        # Warning alerts
        if bounce_rate > 5 and bounce_rate <= 10:
            alerts.append(f"⚠️ WARNING: Bounce rate is {bounce_rate}% (threshold: 5%)")

        if complaint_rate > 0.1 and complaint_rate <= 0.5:
            alerts.append(f"⚠️ WARNING: Complaint rate is {complaint_rate}% (threshold: 0.1%)")

        if reputation_status == "under_review":
            alerts.append("⚠️ WARNING: Account reputation is under review")

        # Success message if no alerts
        if not alerts:
            alerts.append("✅ All metrics within safe thresholds")

        return alerts, has_critical
