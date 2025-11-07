"""
ML Data Anonymization Service.

Provides functions to anonymize sensitive data before storing in ML training tables.
Ensures GDPR compliance and user privacy while maintaining data utility for ML.
"""

import hashlib
from datetime import datetime
from typing import Any, Dict, List

from app.core.config import settings


def anonymize_account_id(account_id: str) -> str:
    """
    Create anonymized hash of account ID.

    Args:
        account_id: Cloud account ID or user ID to anonymize

    Returns:
        SHA256 hash (first 16 chars) for consistent anonymization
    """
    salt = settings.SECRET_KEY
    hash_input = f"{account_id}{salt}".encode()
    return hashlib.sha256(hash_input).hexdigest()[:16]


def anonymize_user_id(user_id: str) -> str:
    """
    Create anonymized hash of user ID.

    Args:
        user_id: User UUID to anonymize

    Returns:
        SHA256 hash for user tracking without identity exposure
    """
    salt = settings.SECRET_KEY
    hash_input = f"{user_id}{salt}".encode()
    return hashlib.sha256(hash_input).hexdigest()


def anonymize_resource_id(resource_id: str) -> str:
    """
    Create anonymized hash of cloud resource ID.

    Args:
        resource_id: Cloud resource ID (e.g., vol-abc123, i-xyz789)

    Returns:
        SHA256 hash for resource lifecycle tracking
    """
    salt = settings.SECRET_KEY
    hash_input = f"{resource_id}{salt}".encode()
    return hashlib.sha256(hash_input).hexdigest()


def anonymize_region(region: str) -> str:
    """
    Generalize AWS/Azure/GCP region to broader category.

    Args:
        region: Full region name (e.g., 'us-east-1', 'westeurope', 'asia-southeast1')

    Returns:
        Generalized region (e.g., 'us-*', 'eu-*', 'ap-*', 'other')

    Examples:
        >>> anonymize_region('us-east-1')
        'us-*'
        >>> anonymize_region('eu-west-3')
        'eu-*'
        >>> anonymize_region('westeurope')
        'eu-*'
        >>> anonymize_region('asia-southeast1')
        'ap-*'
    """
    region_lower = region.lower()

    # AWS regions
    if region_lower.startswith("us-"):
        return "us-*"
    elif region_lower.startswith("eu-"):
        return "eu-*"
    elif region_lower.startswith("ap-"):
        return "ap-*"
    elif region_lower.startswith("ca-"):
        return "ca-*"
    elif region_lower.startswith("sa-"):
        return "sa-*"
    elif region_lower.startswith("af-"):
        return "af-*"
    elif region_lower.startswith("me-"):
        return "me-*"

    # Azure regions
    elif "us" in region_lower or "america" in region_lower:
        return "us-*"
    elif "europe" in region_lower or "uk" in region_lower or "france" in region_lower:
        return "eu-*"
    elif "asia" in region_lower or "japan" in region_lower or "korea" in region_lower:
        return "ap-*"
    elif "australia" in region_lower:
        return "au-*"
    elif "india" in region_lower:
        return "in-*"
    elif "canada" in region_lower:
        return "ca-*"
    elif "brazil" in region_lower:
        return "sa-*"

    # GCP regions
    elif region_lower.startswith("us-"):
        return "us-*"
    elif region_lower.startswith("europe-"):
        return "eu-*"
    elif region_lower.startswith("asia-"):
        return "ap-*"
    elif region_lower.startswith("australia-"):
        return "au-*"
    elif region_lower.startswith("southamerica-"):
        return "sa-*"

    return "other"


def anonymize_metrics(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anonymize CloudWatch/Azure metrics by keeping only statistical aggregates.

    Removes absolute values that could identify specific resources,
    keeps only patterns useful for ML training.

    Args:
        metrics: Raw metrics dictionary from cloud provider

    Returns:
        Anonymized metrics with only aggregates and trends

    Examples:
        Input:
        {
            "CPUUtilization": {
                "timeseries": [5.2, 6.1, 4.8, ...],
                "avg": 5.3,
                "max": 12.4
            }
        }

        Output:
        {
            "CPUUtilization": {
                "avg": 5.3,
                "p50": 5.1,
                "p95": 8.2,
                "p99": 11.2,
                "trend": "stable"
            }
        }
    """
    if not metrics:
        return {}

    anonymized = {}

    for metric_name, values in metrics.items():
        if not isinstance(values, dict):
            continue

        # Extract timeseries if available
        timeseries = values.get("timeseries", [])

        anonymized[metric_name] = {
            "avg": values.get("avg"),
            "p50": values.get("p50"),
            "p95": values.get("p95"),
            "p99": values.get("p99"),
            "min": values.get("min"),
            "max": values.get("max"),
        }

        # Calculate trend if timeseries available
        if timeseries and len(timeseries) >= 2:
            anonymized[metric_name]["trend"] = calculate_trend(timeseries)
        else:
            anonymized[metric_name]["trend"] = "unknown"

        # Remove None values
        anonymized[metric_name] = {k: v for k, v in anonymized[metric_name].items() if v is not None}

    return anonymized


def calculate_trend(timeseries: List[float]) -> str:
    """
    Calculate trend direction from time series data.

    Args:
        timeseries: List of metric values over time

    Returns:
        Trend classification: 'increasing', 'decreasing', 'stable', 'volatile'

    Examples:
        >>> calculate_trend([10, 12, 15, 18, 20])
        'increasing'
        >>> calculate_trend([20, 18, 15, 12, 10])
        'decreasing'
        >>> calculate_trend([10, 11, 10, 11, 10])
        'stable'
    """
    if not timeseries or len(timeseries) < 2:
        return "unknown"

    # Calculate simple moving average slope
    n = len(timeseries)
    if n < 3:
        # Too few points, compare first and last
        change = (timeseries[-1] - timeseries[0]) / (timeseries[0] + 0.001)
        if abs(change) < 0.1:
            return "stable"
        return "increasing" if change > 0 else "decreasing"

    # Calculate slope using linear regression
    x_mean = (n - 1) / 2
    y_mean = sum(timeseries) / n

    numerator = sum((i - x_mean) * (timeseries[i] - y_mean) for i in range(n))
    denominator = sum((i - x_mean) ** 2 for i in range(n))

    if denominator == 0:
        return "stable"

    slope = numerator / denominator

    # Calculate coefficient of variation for volatility
    std_dev = (sum((x - y_mean) ** 2 for x in timeseries) / n) ** 0.5
    cv = std_dev / (y_mean + 0.001)  # Coefficient of variation

    # Classify trend
    if cv > 0.5:  # High variability
        return "volatile"
    elif abs(slope) < 0.01:  # Minimal change
        return "stable"
    elif slope > 0:
        return "increasing"
    else:
        return "decreasing"


def anonymize_resource_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Anonymize resource configuration by removing identifiable information.

    Keeps: size, type, SKU, pricing tier
    Removes: names, IDs, tags with PII, custom labels

    Args:
        config: Resource configuration dictionary

    Returns:
        Anonymized configuration safe for ML training
    """
    if not config:
        return {}

    # Fields to keep (whitelist approach)
    safe_fields = {
        # Size/capacity
        "size_gb",
        "size",
        "capacity",
        "storage_gb",
        "memory_gb",
        "vcpus",
        "cpu_count",
        # Type/SKU
        "volume_type",
        "instance_type",
        "sku",
        "tier",
        "size_name",
        "vm_size",
        "disk_type",
        # Performance
        "iops",
        "throughput",
        "performance_tier",
        # Pricing
        "pricing_tier",
        "billing_mode",
        # Age
        "created_date",
        "age_days",
        "last_activity_date",
        # State
        "state",
        "status",
        "lifecycle_state",
        # Detection
        "detection_scenario",
        "confidence",
        "confidence_level",
    }

    anonymized = {}

    for key, value in config.items():
        if key in safe_fields:
            # Keep dates as age in days only
            if "date" in key.lower() and isinstance(value, (str, datetime)):
                if isinstance(value, str):
                    try:
                        date_obj = datetime.fromisoformat(value.replace("Z", "+00:00"))
                        age_days = (datetime.now() - date_obj).days
                        anonymized["age_days"] = age_days
                    except Exception:
                        pass
                elif isinstance(value, datetime):
                    age_days = (datetime.now() - value).days
                    anonymized["age_days"] = age_days
            else:
                anonymized[key] = value

    return anonymized


def get_company_size_bucket(employee_count: int) -> str:
    """
    Convert employee count to anonymized company size bucket.

    Args:
        employee_count: Number of employees

    Returns:
        Size bucket: 'small', 'medium', 'large', 'enterprise'
    """
    if employee_count < 50:
        return "small"
    elif employee_count < 500:
        return "medium"
    elif employee_count < 5000:
        return "large"
    else:
        return "enterprise"


def calculate_resource_age_days(created_date: datetime | str | None) -> int:
    """
    Calculate resource age in days from creation date.

    Args:
        created_date: Resource creation timestamp

    Returns:
        Age in days, or 0 if date is None or invalid
    """
    if not created_date:
        return 0

    try:
        if isinstance(created_date, str):
            # Parse ISO format datetime string
            date_obj = datetime.fromisoformat(created_date.replace("Z", "+00:00"))
        elif isinstance(created_date, datetime):
            date_obj = created_date
        else:
            return 0

        age = (datetime.now() - date_obj.replace(tzinfo=None)).days
        return max(0, age)  # Ensure non-negative
    except Exception:
        return 0
