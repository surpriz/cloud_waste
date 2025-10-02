"""Cost calculation service for cloud resources."""

from typing import Any


class CostCalculator:
    """
    Service for calculating estimated monthly costs of orphaned resources.

    Provides pricing information and cost estimation logic for various
    cloud resource types across different providers.
    """

    # AWS pricing constants (USD per month)
    AWS_PRICING = {
        # EBS Volume types
        "ebs_gp3_per_gb": 0.08,  # General Purpose SSD (gp3)
        "ebs_gp2_per_gb": 0.10,  # General Purpose SSD (gp2)
        "ebs_io1_per_gb": 0.125,  # Provisioned IOPS SSD (io1)
        "ebs_io2_per_gb": 0.125,  # Provisioned IOPS SSD (io2)
        "ebs_st1_per_gb": 0.045,  # Throughput Optimized HDD (st1)
        "ebs_sc1_per_gb": 0.015,  # Cold HDD (sc1)
        "ebs_standard_per_gb": 0.05,  # Magnetic (standard)
        # Snapshots
        "snapshot_per_gb": 0.05,  # EBS Snapshot storage
        # Networking
        "elastic_ip": 3.60,  # Unassociated Elastic IP per month
        "nat_gateway_base": 32.40,  # NAT Gateway base cost per month
        "nat_gateway_per_gb": 0.045,  # NAT Gateway data processing per GB
        # Load Balancers
        "alb_base": 22.00,  # Application Load Balancer base cost
        "nlb_base": 22.00,  # Network Load Balancer base cost
        "clb_base": 18.00,  # Classic Load Balancer base cost
        # RDS Storage
        "rds_gp2_per_gb": 0.115,  # RDS General Purpose (gp2) storage
        "rds_gp3_per_gb": 0.115,  # RDS General Purpose (gp3) storage
        "rds_io1_per_gb": 0.125,  # RDS Provisioned IOPS (io1) storage
        "rds_magnetic_per_gb": 0.10,  # RDS Magnetic storage
    }

    @staticmethod
    def calculate_ebs_volume_cost(size_gb: int, volume_type: str = "gp2") -> float:
        """
        Calculate monthly cost for an EBS volume.

        Args:
            size_gb: Volume size in gigabytes
            volume_type: EBS volume type (gp2, gp3, io1, io2, st1, sc1, standard)

        Returns:
            Estimated monthly cost in USD
        """
        price_key = f"ebs_{volume_type}_per_gb"
        price_per_gb = CostCalculator.AWS_PRICING.get(
            price_key, CostCalculator.AWS_PRICING["ebs_gp2_per_gb"]
        )
        return round(size_gb * price_per_gb, 2)

    @staticmethod
    def calculate_snapshot_cost(size_gb: int) -> float:
        """
        Calculate monthly cost for an EBS snapshot.

        Args:
            size_gb: Snapshot size in gigabytes

        Returns:
            Estimated monthly cost in USD
        """
        return round(size_gb * CostCalculator.AWS_PRICING["snapshot_per_gb"], 2)

    @staticmethod
    def calculate_elastic_ip_cost() -> float:
        """
        Calculate monthly cost for an unassociated Elastic IP.

        Returns:
            Fixed monthly cost in USD
        """
        return CostCalculator.AWS_PRICING["elastic_ip"]

    @staticmethod
    def calculate_nat_gateway_cost(data_processed_gb: float = 0.0) -> float:
        """
        Calculate monthly cost for a NAT Gateway.

        Args:
            data_processed_gb: Amount of data processed in GB (optional)

        Returns:
            Estimated monthly cost in USD
        """
        base_cost = CostCalculator.AWS_PRICING["nat_gateway_base"]
        data_cost = data_processed_gb * CostCalculator.AWS_PRICING["nat_gateway_per_gb"]
        return round(base_cost + data_cost, 2)

    @staticmethod
    def calculate_load_balancer_cost(lb_type: str = "alb") -> float:
        """
        Calculate monthly cost for a load balancer.

        Args:
            lb_type: Type of load balancer (alb, nlb, clb)

        Returns:
            Base monthly cost in USD
        """
        price_key = f"{lb_type}_base"
        return CostCalculator.AWS_PRICING.get(
            price_key, CostCalculator.AWS_PRICING["alb_base"]
        )

    @staticmethod
    def calculate_rds_storage_cost(size_gb: int, storage_type: str = "gp2") -> float:
        """
        Calculate monthly cost for RDS storage.

        Args:
            size_gb: Storage size in gigabytes
            storage_type: RDS storage type (gp2, gp3, io1, magnetic)

        Returns:
            Estimated monthly cost in USD
        """
        price_key = f"rds_{storage_type}_per_gb"
        price_per_gb = CostCalculator.AWS_PRICING.get(
            price_key, CostCalculator.AWS_PRICING["rds_gp2_per_gb"]
        )
        return round(size_gb * price_per_gb, 2)

    @staticmethod
    def calculate_total_waste(orphan_resources: list[dict[str, Any]]) -> float:
        """
        Calculate total estimated monthly waste from a list of orphan resources.

        Args:
            orphan_resources: List of orphan resource dictionaries with
                            'estimated_monthly_cost' field

        Returns:
            Total estimated monthly waste in USD
        """
        total = sum(
            resource.get("estimated_monthly_cost", 0.0) for resource in orphan_resources
        )
        return round(total, 2)

    @staticmethod
    def get_pricing_info(provider: str = "aws") -> dict[str, float]:
        """
        Get pricing information for a cloud provider.

        Args:
            provider: Cloud provider name (aws, azure, gcp)

        Returns:
            Dictionary of pricing information
        """
        if provider == "aws":
            return CostCalculator.AWS_PRICING.copy()
        # Future: Add Azure and GCP pricing
        return {}

    @staticmethod
    def estimate_annual_savings(monthly_cost: float) -> float:
        """
        Estimate annual savings from eliminating orphan resources.

        Args:
            monthly_cost: Estimated monthly cost

        Returns:
            Estimated annual savings in USD
        """
        return round(monthly_cost * 12, 2)

    @staticmethod
    def categorize_by_cost(
        orphan_resources: list[dict[str, Any]]
    ) -> dict[str, list[dict[str, Any]]]:
        """
        Categorize orphan resources by cost tiers.

        Args:
            orphan_resources: List of orphan resource dictionaries

        Returns:
            Dictionary with categories: 'high', 'medium', 'low'
        """
        high_cost = []  # > $50/month
        medium_cost = []  # $10-50/month
        low_cost = []  # < $10/month

        for resource in orphan_resources:
            cost = resource.get("estimated_monthly_cost", 0.0)
            if cost > 50:
                high_cost.append(resource)
            elif cost >= 10:
                medium_cost.append(resource)
            else:
                low_cost.append(resource)

        return {
            "high": high_cost,
            "medium": medium_cost,
            "low": low_cost,
        }

    @staticmethod
    def get_top_waste_resources(
        orphan_resources: list[dict[str, Any]], limit: int = 10
    ) -> list[dict[str, Any]]:
        """
        Get top orphan resources by monthly cost.

        Args:
            orphan_resources: List of orphan resource dictionaries
            limit: Maximum number of resources to return

        Returns:
            List of top orphan resources sorted by cost (descending)
        """
        sorted_resources = sorted(
            orphan_resources,
            key=lambda x: x.get("estimated_monthly_cost", 0.0),
            reverse=True,
        )
        return sorted_resources[:limit]
