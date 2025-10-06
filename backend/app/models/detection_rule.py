"""DetectionRule database model."""

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.core.database import Base


# Default detection rules (best practices)
DEFAULT_DETECTION_RULES = {
    "ebs_volume": {
        "enabled": True,
        "min_age_days": 7,  # Ignore volumes created in last 7 days
        "confidence_threshold_days": 30,  # High confidence after 30 days
        "detect_attached_unused": True,  # Also detect attached volumes with no I/O activity
        "min_idle_days_attached": 30,  # Min days of no I/O for attached volumes
        "description": "Unattached EBS volumes and attached volumes with no I/O activity",
    },
    "elastic_ip": {
        "enabled": True,
        "min_age_days": 3,  # Ignore IPs allocated in last 3 days
        "confidence_threshold_days": 7,
        "description": "Unassociated Elastic IP addresses",
    },
    "ebs_snapshot": {
        "enabled": True,
        "min_age_days": 90,  # Snapshots older than 90 days
        "require_orphaned_volume": True,  # Volume must be deleted
        "confidence_threshold_days": 180,
        "description": "Orphaned EBS snapshots (source volume deleted)",
    },
    "ec2_instance": {
        "enabled": True,
        "min_stopped_days": 30,  # Stopped for > 30 days
        "confidence_threshold_days": 60,
        "description": "EC2 instances stopped for extended periods",
    },
    "nat_gateway": {
        "enabled": True,
        "max_bytes_30d": 1_000_000,  # < 1MB traffic in 30 days
        "min_age_days": 7,
        "confidence_threshold_days": 30,
        "description": "NAT Gateways with no traffic",
    },
    "load_balancer": {
        "enabled": True,
        "require_zero_healthy_targets": True,
        "min_age_days": 7,
        "confidence_threshold_days": 14,
        "description": "Load balancers with no healthy backends",
    },
    "rds_instance": {
        "enabled": True,
        "min_stopped_days": 7,  # RDS auto-starts after 7 days
        "confidence_threshold_days": 14,
        "description": "RDS instances in stopped state",
    },
    # TOP 15 high-cost idle resources
    "fsx_file_system": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 30,
        "description": "FSx file systems with no data transfer activity",
    },
    "neptune_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Neptune clusters with no active connections",
    },
    "msk_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "MSK clusters with no data traffic",
    },
    "eks_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "EKS clusters with no worker nodes",
    },
    "sagemaker_endpoint": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "SageMaker endpoints with no invocations",
    },
    "redshift_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Redshift clusters with no database connections",
    },
    "elasticache_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "ElastiCache clusters with no cache hits",
    },
    "vpn_connection": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 30,
        "description": "VPN connections with no data transfer",
    },
    "transit_gateway_attachment": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 30,
        "description": "Transit Gateway attachments with no traffic",
    },
    "opensearch_domain": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "OpenSearch domains with no search requests",
    },
    "global_accelerator": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Global Accelerators with no endpoints",
    },
    "kinesis_stream": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "Kinesis streams with no incoming records",
    },
    "vpc_endpoint": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "VPC endpoints with no network interfaces",
    },
    "documentdb_cluster": {
        "enabled": True,
        "min_age_days": 3,
        "confidence_threshold_days": 7,
        "description": "DocumentDB clusters with no database connections",
    },
}


class DetectionRule(Base):
    """User-specific detection rule configuration."""

    __tablename__ = "detection_rules"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # 'ebs_volume', 'elastic_ip', 'ebs_snapshot', etc.

    # Custom rules (JSONB for flexibility)
    # Example: {"enabled": true, "min_age_days": 14, "confidence_threshold_days": 45}
    rules: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="detection_rules")  # type: ignore

    def __repr__(self) -> str:
        """String representation."""
        return f"<DetectionRule {self.resource_type} for user {self.user_id}>"
