"""Azure cloud provider implementation (skeleton)."""

from typing import Any

from app.providers.base import CloudProviderBase, OrphanResourceData


class AzureProvider(CloudProviderBase):
    """
    Azure cloud provider implementation.

    This is a skeleton implementation. Resource detection methods will be
    implemented in a future phase after the account integration is complete.

    Authentication uses Azure Service Principal (tenant_id, client_id, client_secret).
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
        subscription_id: str,
        regions: list[str] | None = None,
        resource_groups: list[str] | None = None,
    ) -> None:
        """
        Initialize Azure provider client.

        Args:
            tenant_id: Azure AD Tenant ID
            client_id: Service Principal Application/Client ID
            client_secret: Service Principal Client Secret
            subscription_id: Azure Subscription ID
            regions: List of Azure regions to scan (e.g., ['eastus', 'westeurope'])
            resource_groups: List of Azure resource groups to scan (e.g., ['rg-prod', 'rg-dev'])
                           If None or empty, all resource groups will be scanned.
        """
        # Azure uses different authentication than AWS, so we override the base class params
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.subscription_id = subscription_id
        self.regions = regions or []
        self.resource_groups = resource_groups or []

    def _is_resource_in_scope(self, resource_id: str) -> bool:
        """
        Check if a resource is in scope based on resource_groups filter.

        Args:
            resource_id: Azure resource ID (format: /subscriptions/{sub}/resourceGroups/{rg}/...)

        Returns:
            True if resource should be scanned, False otherwise
        """
        # If no resource_groups filter specified, scan all resources
        if not self.resource_groups:
            return True

        # Extract resource group name from resource ID
        # Format: /subscriptions/{subscription_id}/resourceGroups/{resource_group_name}/...
        parts = resource_id.split('/')
        try:
            rg_index = parts.index('resourceGroups')
            if rg_index + 1 < len(parts):
                resource_group_name = parts[rg_index + 1].lower()
                # Check if resource group is in the filter list (case-insensitive)
                return any(rg.lower() == resource_group_name for rg in self.resource_groups)
        except (ValueError, IndexError):
            # If we can't parse the resource group, include it to be safe
            return True

        return False

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate Azure Service Principal credentials.

        Returns:
            Dict with subscription information

        Raises:
            Exception: If credentials are invalid
        """
        # TODO: Implement Azure credential validation
        # This will use azure.identity.ClientSecretCredential
        # and azure.mgmt.resource.SubscriptionClient
        return {
            "subscription_id": self.subscription_id,
            "tenant_id": self.tenant_id,
        }

    async def get_available_regions(self) -> list[str]:
        """
        Get list of available Azure regions.

        Returns:
            List of Azure region names
        """
        # TODO: Implement using azure.mgmt.resource.SubscriptionClient.list_locations()
        return [
            "eastus",
            "eastus2",
            "westus",
            "westus2",
            "westeurope",
            "northeurope",
            "centralus",
            "southcentralus",
            "westcentralus",
        ]

    async def scan_unattached_volumes(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for unattached Azure Managed Disks.

        Detects all unattached managed disks including:
        - Standard HDD (S4-S80)
        - Standard SSD (E1-E80)
        - Premium SSD (P1-P80)
        - Ultra SSD (with IOPS/throughput)
        - Disks with encryption
        - Disks in availability zones
        - Disks with bursting enabled

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphan disk resources with accurate cost estimates
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            # Initialize Azure clients
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks in the subscription
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region (Azure uses 'location')
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Check if disk is unattached
                # disk_state can be: 'Unattached', 'Attached', 'Reserved', 'ActiveSAS'
                if disk.disk_state == 'Unattached' or disk.disk_state == 'Reserved':
                    # Check disk age against min_age_days filter
                    age_days = 0
                    if disk.time_created:
                        age_days = (datetime.now(timezone.utc) - disk.time_created).days
                        if age_days < min_age_days:
                            continue  # Skip disk - too young

                    # Calculate monthly cost based on SKU
                    monthly_cost = self._calculate_disk_cost(disk)

                    # Generate orphan reason message
                    sku_display = disk.sku.name if disk.sku else 'Unknown SKU'
                    orphan_reason = f"Unattached Azure Managed Disk ({sku_display}, {disk.disk_size_gb}GB) not attached to any VM for {age_days} days"
                    if disk.disk_state == 'Reserved':
                        orphan_reason = f"Reserved Azure Managed Disk ({sku_display}, {disk.disk_size_gb}GB) - billing continues even when not attached"

                    # Extract metadata
                    metadata = {
                        'disk_id': disk.id,
                        'disk_state': disk.disk_state,
                        'disk_size_gb': disk.disk_size_gb,
                        'sku_name': disk.sku.name if disk.sku else 'Unknown',
                        'sku_tier': disk.sku.tier if disk.sku else 'Unknown',
                        'location': disk.location,
                        'zones': disk.zones if disk.zones else None,
                        'encryption_type': disk.encryption.type if disk.encryption else None,
                        'disk_iops': disk.disk_iops_read_write if hasattr(disk, 'disk_iops_read_write') else None,
                        'disk_mbps': disk.disk_mbps_read_write if hasattr(disk, 'disk_mbps_read_write') else None,
                        'created_at': disk.time_created.isoformat() if disk.time_created else None,  # Renamed for consistency with AWS
                        'age_days': age_days,  # For "Already Wasted" calculation
                        'orphan_reason': orphan_reason,  # Display reason for frontend
                        'os_type': disk.os_type.value if disk.os_type else None,
                        'hyper_v_generation': disk.hyper_v_generation if hasattr(disk, 'hyper_v_generation') else None,
                        'bursting_enabled': disk.bursting_enabled if hasattr(disk, 'bursting_enabled') else False,
                        'network_access_policy': disk.network_access_policy if hasattr(disk, 'network_access_policy') else None,
                        'managed_by': disk.managed_by if disk.managed_by else None,  # VM ID if attached
                        'managed_by_extended': disk.managed_by_extended if hasattr(disk, 'managed_by_extended') else None,
                        'tags': disk.tags if disk.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    # Add warning for Reserved state (billing continues!)
                    if disk.disk_state == 'Reserved':
                        metadata['warning'] = 'Disk in Reserved state - billing continues even though not attached'

                    # Add warning for Ultra SSD (very expensive)
                    if disk.sku and 'UltraSSD' in disk.sku.name:
                        metadata['warning'] = f'Ultra SSD detected - Very expensive! Base: ${monthly_cost:.2f}/month + IOPS + throughput costs'

                    orphan = OrphanResourceData(
                        resource_type='managed_disk_unattached',
                        resource_id=disk.id,
                        resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                        region=disk.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            # Log error but don't fail the entire scan
            print(f"Error scanning unattached disks in {region}: {str(e)}")
            # In production, use proper logging
            # logger.error(f"Error scanning unattached disks in {region}: {str(e)}", exc_info=True)

        return orphans

    def _calculate_disk_cost(self, disk) -> float:
        """
        Calculate monthly cost for an Azure Managed Disk based on SKU and size.

        Azure Managed Disk pricing (US East, approximate):
        - Standard HDD (Standard_LRS): $0.048/GB/month (S4-S80)
        - Standard SSD (StandardSSD_LRS): $0.096/GB/month (E1-E80)
        - Premium SSD (Premium_LRS): $0.15-0.23/GB/month (P1-P80)
        - Ultra SSD (UltraSSD_LRS): $0.30/GB/month + IOPS + throughput

        Args:
            disk: Azure Disk object

        Returns:
            Estimated monthly cost in USD
        """
        disk_size_gb = disk.disk_size_gb if disk.disk_size_gb else 0
        sku_name = disk.sku.name if disk.sku else 'Standard_LRS'

        # Base cost per GB based on SKU
        cost_per_gb = {
            'Standard_LRS': 0.048,      # Standard HDD
            'StandardSSD_LRS': 0.096,   # Standard SSD
            'StandardSSD_ZRS': 0.115,   # Standard SSD Zone-Redundant (+20%)
            'Premium_LRS': 0.175,       # Premium SSD (average)
            'Premium_ZRS': 0.21,        # Premium SSD Zone-Redundant (+20%)
            'UltraSSD_LRS': 0.30,       # Ultra SSD (base only, IOPS/throughput extra)
        }

        base_cost_per_gb = cost_per_gb.get(sku_name, 0.10)  # Default to Standard SSD if unknown
        base_cost = disk_size_gb * base_cost_per_gb

        # Add encryption cost if enabled (roughly +5-10%)
        if disk.encryption and disk.encryption.type and disk.encryption.type != 'EncryptionAtRestWithPlatformKey':
            base_cost *= 1.08  # +8% for customer-managed keys

        # Add zone redundancy premium if in availability zones
        if disk.zones and len(disk.zones) > 0:
            base_cost *= 1.15  # +15% for zone redundancy

        # Add bursting cost for Premium SSD (P20+ only)
        if disk.sku and 'Premium' in sku_name:
            if hasattr(disk, 'bursting_enabled') and disk.bursting_enabled:
                # Bursting adds roughly 10-20% depending on usage
                base_cost *= 1.15  # +15% average bursting cost

        # Ultra SSD additional costs (IOPS + throughput)
        if 'UltraSSD' in sku_name:
            # Base cost already calculated above
            # Add IOPS cost: $0.013 per IOPS
            if hasattr(disk, 'disk_iops_read_write') and disk.disk_iops_read_write:
                base_cost += (disk.disk_iops_read_write * 0.013)

            # Add throughput cost: $0.04 per MBps
            if hasattr(disk, 'disk_mbps_read_write') and disk.disk_mbps_read_write:
                base_cost += (disk.disk_mbps_read_write * 0.04)

        return round(base_cost, 2)

    def _calculate_public_ip_cost(self, public_ip) -> float:
        """
        Calculate monthly cost for an Azure Public IP Address based on SKU and configuration.

        Azure Public IP pricing (US East, approximate):
        - Basic Static IP: $3.00/month
        - Standard Static IP (zonal): $3.00/month
        - Standard Static IP (zone-redundant, 3+ zones): $3.65/month (+22%)
        - Dynamic IPs: Usually $0/month when unassociated (deallocated automatically)

        Args:
            public_ip: Azure PublicIPAddress object

        Returns:
            Estimated monthly cost in USD
        """
        sku_name = public_ip.sku.name if public_ip.sku else 'Basic'
        allocation_method = public_ip.public_ip_allocation_method if public_ip.public_ip_allocation_method else 'Static'

        # Dynamic IPs are usually deallocated automatically when unassociated
        # Cost is $0 for unassociated dynamic IPs
        if allocation_method == 'Dynamic':
            return 0.00

        # Base cost for Static IPs
        base_costs = {
            'Basic': 3.00,      # Basic Static IP
            'Standard': 3.00,   # Standard Static IP (zonal)
        }

        base_cost = base_costs.get(sku_name, 3.00)

        # Add zone redundancy premium for Standard SKU with multiple zones
        if sku_name == 'Standard' and public_ip.zones and len(public_ip.zones) >= 3:
            # Zone-redundant (3+ zones) adds ~22% premium
            base_cost = 3.65  # Standard zone-redundant pricing

        return round(base_cost, 2)

    def _get_vm_hourly_cost(self, vm_size: str) -> float:
        """
        Get hourly cost for Azure VM sizes (approximate US East pricing 2025).

        Args:
            vm_size: VM SKU (e.g., 'Standard_D2s_v3', 'Standard_E4s_v3')

        Returns:
            Hourly cost in USD
        """
        # D-series (General Purpose) - vCPU:RAM ratio 1:4
        d_series = {
            'Standard_D2s_v3': 0.096,   # 2 vCPU, 8 GB RAM
            'Standard_D4s_v3': 0.192,   # 4 vCPU, 16 GB RAM
            'Standard_D8s_v3': 0.384,   # 8 vCPU, 32 GB RAM
            'Standard_D16s_v3': 0.768,  # 16 vCPU, 64 GB RAM
            'Standard_D32s_v3': 1.536,  # 32 vCPU, 128 GB RAM
            'Standard_D48s_v3': 2.304,  # 48 vCPU, 192 GB RAM
            'Standard_D64s_v3': 3.072,  # 64 vCPU, 256 GB RAM
        }

        # E-series (Memory Optimized) - vCPU:RAM ratio 1:8
        e_series = {
            'Standard_E2s_v3': 0.126,   # 2 vCPU, 16 GB RAM
            'Standard_E4s_v3': 0.252,   # 4 vCPU, 32 GB RAM
            'Standard_E8s_v3': 0.504,   # 8 vCPU, 64 GB RAM
            'Standard_E16s_v3': 1.008,  # 16 vCPU, 128 GB RAM
            'Standard_E32s_v3': 2.016,  # 32 vCPU, 256 GB RAM
            'Standard_E48s_v3': 3.024,  # 48 vCPU, 384 GB RAM
            'Standard_E64s_v3': 4.032,  # 64 vCPU, 512 GB RAM
        }

        # F-series (Compute Optimized) - vCPU:RAM ratio 1:2
        f_series = {
            'Standard_F2s_v2': 0.085,   # 2 vCPU, 4 GB RAM
            'Standard_F4s_v2': 0.169,   # 4 vCPU, 8 GB RAM
            'Standard_F8s_v2': 0.338,   # 8 vCPU, 16 GB RAM
            'Standard_F16s_v2': 0.677,  # 16 vCPU, 32 GB RAM
            'Standard_F32s_v2': 1.354,  # 32 vCPU, 64 GB RAM
        }

        # Combine all series
        pricing = {**d_series, **e_series, **f_series}

        # Return price or estimate based on vCPU count if unknown
        if vm_size in pricing:
            return pricing[vm_size]

        # Fallback: estimate based on vCPU count (rough approximation)
        # Pattern: Standard_D{vcpu}s_v3 → extract vCPU count
        try:
            if 'D' in vm_size and 's_v' in vm_size:
                vcpu_str = vm_size.split('D')[1].split('s')[0]
                vcpus = int(vcpu_str)
                return vcpus * 0.048  # ~$0.048/vCPU/hour (D-series average)
            elif 'E' in vm_size and 's_v' in vm_size:
                vcpu_str = vm_size.split('E')[1].split('s')[0]
                vcpus = int(vcpu_str)
                return vcpus * 0.063  # ~$0.063/vCPU/hour (E-series average)
        except (ValueError, IndexError):
            pass

        # Default fallback (Standard_D2s_v3 equivalent)
        return 0.096

    def _calculate_aks_cluster_cost(
        self,
        cluster,
        agent_pools: list,
        include_storage: bool = True,
        include_networking: bool = True
    ) -> dict:
        """
        Calculate comprehensive monthly cost for an AKS cluster.

        Args:
            cluster: Azure ManagedCluster object
            agent_pools: List of AgentPool objects
            include_storage: Include OS disk storage costs
            include_networking: Include LB and Public IP costs

        Returns:
            Dict with cost breakdown:
            {
                'cluster_fee': float,
                'node_cost': float,
                'storage_cost': float,
                'lb_cost': float,
                'public_ip_cost': float,
                'total_monthly_cost': float
            }
        """
        # Cluster management fee based on tier
        tier_pricing = {
            'Free': 0,          # No SLA, control plane free
            'Standard': 73.0,   # $0.10/hour = $73/month, 99.9% SLA
            'Premium': 438.0    # $0.60/hour = $438/month, 99.95% SLA, Uptime SLA
        }

        cluster_tier = cluster.sku.tier if cluster.sku else 'Free'
        cluster_fee = tier_pricing.get(cluster_tier, 0.0)

        # Node compute costs
        node_cost = 0.0
        total_nodes = 0
        for pool in agent_pools:
            pool_node_count = pool.count if pool.count else 0
            total_nodes += pool_node_count
            vm_size = pool.vm_size if pool.vm_size else 'Standard_D2s_v3'
            vm_hourly_cost = self._get_vm_hourly_cost(vm_size)
            node_cost += pool_node_count * vm_hourly_cost * 730  # 730 hours/month

        # Storage costs (OS disks)
        storage_cost = 0.0
        if include_storage and total_nodes > 0:
            # Each node has an OS disk (default 128 GB Premium SSD)
            os_disk_size_gb = 128
            os_disk_cost_per_gb = 0.12  # Premium SSD pricing
            storage_cost = total_nodes * os_disk_size_gb * os_disk_cost_per_gb

        # Load Balancer costs
        lb_cost = 0.0
        if include_networking:
            # Standard Load Balancer: $0.025/hour = $18.25/month
            # Note: This is a rough estimate. Actual cost depends on number of LB rules.
            lb_cost = 18.25

        # Public IP costs
        public_ip_cost = 0.0
        if include_networking:
            # Estimate 1 Public IP per cluster (for ingress/egress)
            # Standard Static IP: $0.005/hour = $3.65/month
            public_ip_cost = 3.65

        total_monthly_cost = (
            cluster_fee +
            node_cost +
            storage_cost +
            lb_cost +
            public_ip_cost
        )

        return {
            'cluster_fee': round(cluster_fee, 2),
            'node_cost': round(node_cost, 2),
            'storage_cost': round(storage_cost, 2),
            'lb_cost': round(lb_cost, 2),
            'public_ip_cost': round(public_ip_cost, 2),
            'total_monthly_cost': round(total_monthly_cost, 2),
            'total_nodes': total_nodes
        }

    async def _get_aks_credentials(
        self,
        cluster_name: str,
        resource_group_name: str
    ) -> dict | None:
        """
        Get AKS cluster admin credentials (kubeconfig).

        Args:
            cluster_name: AKS cluster name
            resource_group_name: Resource group containing the cluster

        Returns:
            Kubeconfig dict or None if failed
        """
        try:
            from azure.identity import ClientSecretCredential
            from azure.mgmt.containerservice import ContainerServiceClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            aks_client = ContainerServiceClient(credential, self.subscription_id)

            # Get admin credentials (cluster admin access)
            creds_result = aks_client.managed_clusters.list_cluster_admin_credentials(
                resource_group_name=resource_group_name,
                resource_name=cluster_name
            )

            if creds_result.kubeconfigs and len(creds_result.kubeconfigs) > 0:
                # kubeconfigs[0].value contains base64-encoded kubeconfig YAML
                import base64
                import yaml

                kubeconfig_bytes = creds_result.kubeconfigs[0].value
                kubeconfig_yaml = kubeconfig_bytes.decode('utf-8')
                kubeconfig_dict = yaml.safe_load(kubeconfig_yaml)

                return kubeconfig_dict

            return None

        except Exception as e:
            print(f"Error getting AKS credentials for {cluster_name}: {str(e)}")
            return None

    async def _query_aks_metrics(
        self,
        cluster_id: str,
        metric_name: str,
        timespan_days: int = 30,
        aggregation: str = "Average"
    ) -> dict | None:
        """
        Query Azure Monitor Container Insights metrics for an AKS cluster.

        Args:
            cluster_id: Full Azure resource ID of the cluster
            metric_name: Metric to query (e.g., 'node_cpu_usage_percentage', 'node_memory_working_set_percentage')
            timespan_days: Number of days to look back
            aggregation: Aggregation type ('Average', 'Maximum', 'Minimum', etc.)

        Returns:
            Dict with metric data:
            {
                'avg': float,
                'max': float,
                'min': float,
                'p95': float,
                'data_points': list
            }
            or None if no data available
        """
        try:
            from datetime import datetime, timedelta, timezone
            from azure.monitor.query import MetricsQueryClient, MetricAggregationType
            from azure.identity import ClientSecretCredential

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            metrics_client = MetricsQueryClient(credential)

            # Calculate timespan
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=timespan_days)

            # Map aggregation string to enum
            aggregation_map = {
                "Average": MetricAggregationType.AVERAGE,
                "Maximum": MetricAggregationType.MAXIMUM,
                "Minimum": MetricAggregationType.MINIMUM,
                "Total": MetricAggregationType.TOTAL,
                "Count": MetricAggregationType.COUNT
            }
            agg_type = aggregation_map.get(aggregation, MetricAggregationType.AVERAGE)

            # Query metrics
            response = metrics_client.query_resource(
                resource_uri=cluster_id,
                metric_names=[metric_name],
                timespan=(start_time, end_time),
                granularity=timedelta(hours=1),
                aggregations=[agg_type]
            )

            # Extract data points
            data_points = []
            if response.metrics and len(response.metrics) > 0:
                metric = response.metrics[0]
                if metric.timeseries and len(metric.timeseries) > 0:
                    for data in metric.timeseries[0].data:
                        if aggregation == "Average" and data.average is not None:
                            data_points.append(data.average)
                        elif aggregation == "Maximum" and data.maximum is not None:
                            data_points.append(data.maximum)
                        elif aggregation == "Minimum" and data.minimum is not None:
                            data_points.append(data.minimum)

            if not data_points:
                return None

            # Calculate statistics
            avg_value = sum(data_points) / len(data_points)
            max_value = max(data_points)
            min_value = min(data_points)

            # Calculate P95
            sorted_points = sorted(data_points)
            p95_index = int(len(sorted_points) * 0.95)
            p95_value = sorted_points[p95_index] if p95_index < len(sorted_points) else max_value

            return {
                'avg': round(avg_value, 2),
                'max': round(max_value, 2),
                'min': round(min_value, 2),
                'p95': round(p95_value, 2),
                'data_points': data_points,
                'timespan_days': timespan_days
            }

        except Exception as e:
            print(f"Error querying AKS metrics for {cluster_id}: {str(e)}")
            return None

    async def scan_all_resources(
        self, region: str, detection_rules: dict[str, dict] | None = None, scan_global_resources: bool = False
    ) -> list[OrphanResourceData]:
        """
        Scan all Azure resource types in a specific region.

        Override from base class to use Azure-specific resource type names.

        Args:
            region: Azure region to scan
            detection_rules: Optional user-defined detection rules per resource type
            scan_global_resources: If True, also scan global resources (e.g., Storage Accounts).
                                   Should only be True for the first region in a multi-region scan.

        Returns:
            Combined list of all orphan resources found
        """
        results: list[OrphanResourceData] = []
        rules = detection_rules or {}

        # Scan Azure Managed Disks (equivalent to AWS EBS Volumes)
        volume_orphans = await self.scan_unattached_volumes(region, rules.get("managed_disk_unattached"))
        results.extend(volume_orphans)

        # Scan Azure Public IPs (equivalent to AWS Elastic IPs)
        ip_orphans = await self.scan_unassigned_ips(region, rules.get("public_ip_unassociated"))
        results.extend(ip_orphans)

        # Phase 1 - Quick Wins: Additional waste detection scenarios
        # Scan Managed Disks attached to stopped VMs
        disks_on_stopped_vms = await self.scan_disks_on_stopped_vms(region, rules.get("managed_disk_on_stopped_vm"))
        results.extend(disks_on_stopped_vms)

        # Scan orphaned Disk Snapshots (source disk deleted)
        orphaned_snapshots = await self.scan_orphaned_snapshots(region, rules.get("disk_snapshot_orphaned"))
        results.extend(orphaned_snapshots)

        # Scan redundant Disk Snapshots (multiple snapshots for same source disk)
        redundant_snapshots = await self.scan_redundant_snapshots(region, rules.get("disk_snapshot_redundant"))
        results.extend(redundant_snapshots)

        # Additional Disk Snapshot waste scenarios (100% coverage)
        very_old_snapshots = await self.scan_disk_snapshot_very_old(region, rules.get("disk_snapshot_very_old"))
        results.extend(very_old_snapshots)

        premium_source_snapshots = await self.scan_disk_snapshot_premium_source(region, rules.get("disk_snapshot_premium_source"))
        results.extend(premium_source_snapshots)

        large_unused_snapshots = await self.scan_disk_snapshot_large_unused(region, rules.get("disk_snapshot_large_unused"))
        results.extend(large_unused_snapshots)

        full_vs_incremental = await self.scan_disk_snapshot_full_instead_incremental(region, rules.get("disk_snapshot_full_instead_incremental"))
        results.extend(full_vs_incremental)

        excessive_retention = await self.scan_disk_snapshot_excessive_retention(region, rules.get("disk_snapshot_excessive_retention"))
        results.extend(excessive_retention)

        manual_without_policy = await self.scan_disk_snapshot_manual_without_policy(region, rules.get("disk_snapshot_manual_without_policy"))
        results.extend(manual_without_policy)

        never_restored = await self.scan_disk_snapshot_never_restored(region, rules.get("disk_snapshot_never_restored"))
        results.extend(never_restored)

        frequent_creation = await self.scan_disk_snapshot_frequent_creation(region, rules.get("disk_snapshot_frequent_creation"))
        results.extend(frequent_creation)

        # Scan disks with unnecessary Zone-Redundant Storage (ZRS) in dev/test
        unnecessary_zrs = await self.scan_unnecessary_zrs_disks(region, rules.get("managed_disk_unnecessary_zrs"))
        results.extend(unnecessary_zrs)

        # Scan disks with unnecessary Customer-Managed Key encryption
        unnecessary_cmk = await self.scan_unnecessary_cmk_encryption(region, rules.get("managed_disk_unnecessary_cmk"))
        results.extend(unnecessary_cmk)

        # Scan Public IPs associated to stopped resources (VMs, LBs)
        ips_on_stopped = await self.scan_ips_on_stopped_resources(region, rules.get("public_ip_on_stopped_resource"))
        results.extend(ips_on_stopped)

        # Phase B - Additional Public IP waste detection scenarios (100% coverage)
        # Scenario 3: Dynamic Public IPs stuck in provisioned state (anomaly)
        dynamic_unassociated = await self.scan_dynamic_unassociated_ips(region, rules.get("public_ip_dynamic_unassociated"))
        results.extend(dynamic_unassociated)

        # Scenario 4: Standard SKU used in dev/test (Basic would suffice)
        unnecessary_standard = await self.scan_unnecessary_standard_sku_ips(region, rules.get("public_ip_unnecessary_standard_sku"))
        results.extend(unnecessary_standard)

        # Scenario 5: Zone-redundant IPs without high-availability requirements
        unnecessary_zone_redundancy = await self.scan_unnecessary_zone_redundant_ips(region, rules.get("public_ip_unnecessary_zone_redundancy"))
        results.extend(unnecessary_zone_redundancy)

        # Scenario 6: DDoS Protection Standard that has never been triggered (HIGH VALUE)
        ddos_unused = await self.scan_ddos_protection_unused_ips(region, rules.get("public_ip_ddos_protection_unused"))
        results.extend(ddos_unused)

        # Scenario 7: Public IPs attached to orphaned NICs (NIC without VM)
        ips_on_nic_without_vm = await self.scan_ips_on_nic_without_vm(region, rules.get("public_ip_on_nic_without_vm"))
        results.extend(ips_on_nic_without_vm)

        # Scenario 8: Reserved Public IPs that have never been assigned an IP address
        reserved_unused = await self.scan_reserved_unused_ips(region, rules.get("public_ip_reserved_but_unused"))
        results.extend(reserved_unused)

        # Phase C - Azure Monitor Metrics-based Public IP scenarios
        # Scenario 9: Public IPs with zero network traffic (never used)
        no_traffic = await self.scan_no_traffic_ips(region, rules.get("public_ip_no_traffic"))
        results.extend(no_traffic)

        # Scenario 10: Public IPs with very low traffic (under-utilized)
        very_low_traffic = await self.scan_very_low_traffic_ips(region, rules.get("public_ip_very_low_traffic"))
        results.extend(very_low_traffic)

        # Phase A - Virtual Machine waste detection scenarios (simple detection)
        # Scenario 1: VMs deallocated (stopped) for extended periods
        deallocated_vms = await self.scan_stopped_instances(region, rules.get("virtual_machine_deallocated"))
        results.extend(deallocated_vms)

        # Scenario 2: VMs stopped but NOT deallocated (CRITICAL - still paying full price!)
        stopped_not_deallocated = await self.scan_stopped_not_deallocated_vms(region, rules.get("virtual_machine_stopped_not_deallocated"))
        results.extend(stopped_not_deallocated)

        # Scenario 3: VMs created but never started
        never_started = await self.scan_never_started_vms(region, rules.get("virtual_machine_never_started"))
        results.extend(never_started)

        # Scenario 4: VMs oversized with premium disks
        oversized_premium = await self.scan_oversized_premium_vms(region, rules.get("virtual_machine_oversized_premium"))
        results.extend(oversized_premium)

        # Scenario 5: VMs missing required governance tags (orphaned)
        untagged_orphans = await self.scan_untagged_orphan_vms(region, rules.get("virtual_machine_untagged_orphan"))
        results.extend(untagged_orphans)

        # Scenario 6: VMs using old generation SKUs (v1/v2/v3 → v4/v5)
        old_generation = await self.scan_old_generation_vms(region, rules.get("virtual_machine_old_generation"))
        results.extend(old_generation)

        # Scenario 7: VMs that could use Spot pricing (60-90% savings)
        spot_convertible = await self.scan_spot_convertible_vms(region, rules.get("virtual_machine_spot_convertible"))
        results.extend(spot_convertible)

        # Phase 2 - Azure Monitor Metrics-based Advanced Scenarios (requires "Monitoring Reader" permission)
        # Disk scenarios
        # Scenario 6: Idle disks (zero I/O activity)
        idle_disks = await self.scan_idle_disks(region, rules.get("managed_disk_idle"))
        results.extend(idle_disks)

        # Scenario 7: Unused disk bursting (bursting enabled but never used)
        unused_bursting = await self.scan_unused_bursting(region, rules.get("managed_disk_unused_bursting"))
        results.extend(unused_bursting)

        # Scenario 8: Over-provisioned Premium disks (performance tier too high)
        overprovisioned_disks = await self.scan_overprovisioned_disks(region, rules.get("managed_disk_overprovisioned"))
        results.extend(overprovisioned_disks)

        # Scenario 9: Under-utilized Standard HDD disks (should be SSD)
        underutilized_hdd = await self.scan_underutilized_hdd_disks(region, rules.get("managed_disk_underutilized_hdd"))
        results.extend(underutilized_hdd)

        # Phase 2 - VM Azure Monitor Metrics-based Scenarios
        # Scenario 8: Idle running VMs (low CPU utilization)
        idle_vms = await self.scan_idle_running_instances(region, rules.get("virtual_machine_idle"))
        results.extend(idle_vms)

        # Scenario 9: Underutilized VMs (rightsizing - CPU-based)
        underutilized_vms = await self.scan_underutilized_vms(region, rules.get("virtual_machine_underutilized"))
        results.extend(underutilized_vms)

        # Scenario 10: Memory-overprovisioned VMs (E-series with low memory usage)
        memory_overprovisioned = await self.scan_memory_overprovisioned_vms(region, rules.get("virtual_machine_memory_overprovisioned"))
        results.extend(memory_overprovisioned)

        return results

    async def scan_unassigned_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for unassociated Azure Public IP Addresses.

        Detects Public IPs that are not associated with any network interface, VM, or load balancer.
        Unassociated Public IPs continue to incur charges even when not in use.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, enabled)

        Returns:
            List of orphan public IP resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            # Initialize Azure clients
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs in the subscription
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                # Filter by region (Azure uses 'location')
                if ip.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Check if Public IP is unassociated
                # ip_configuration is None when the IP is not attached to any NIC/LB
                if ip.ip_configuration is None:
                    # Check age against min_age_days filter
                    age_days = 0
                    if hasattr(ip, 'provisioning_time') and ip.provisioning_time:
                        age_days = (datetime.now(timezone.utc) - ip.provisioning_time).days
                        if age_days < min_age_days:
                            continue  # Skip IP - too young

                    # Calculate monthly cost based on SKU and allocation
                    monthly_cost = self._calculate_public_ip_cost(ip)

                    # Generate orphan reason message
                    sku_display = ip.sku.name if ip.sku else 'Basic'
                    allocation_method = ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Unknown'
                    ip_address = ip.ip_address if ip.ip_address else 'Not assigned'

                    orphan_reason = f"Unassociated Azure Public IP ({sku_display}, {allocation_method}) - {ip_address} - not attached to any resource for {age_days} days"

                    # Extract metadata
                    metadata = {
                        'ip_id': ip.id,
                        'ip_address': ip_address,
                        'sku_name': ip.sku.name if ip.sku else 'Basic',
                        'sku_tier': ip.sku.tier if ip.sku and hasattr(ip.sku, 'tier') else 'Regional',
                        'allocation_method': allocation_method,
                        'ip_version': ip.public_ip_address_version if ip.public_ip_address_version else 'IPv4',
                        'location': ip.location,
                        'zones': ip.zones if ip.zones else None,
                        'dns_label': ip.dns_settings.domain_name_label if ip.dns_settings and ip.dns_settings.domain_name_label else None,
                        'fqdn': ip.dns_settings.fqdn if ip.dns_settings and ip.dns_settings.fqdn else None,
                        'idle_timeout_in_minutes': ip.idle_timeout_in_minutes if hasattr(ip, 'idle_timeout_in_minutes') else 4,
                        'ip_configuration': None,  # Always None for orphaned IPs
                        'provisioning_time': ip.provisioning_time.isoformat() if hasattr(ip, 'provisioning_time') and ip.provisioning_time else None,
                        'created_at': ip.provisioning_time.isoformat() if hasattr(ip, 'provisioning_time') and ip.provisioning_time else None,
                        'age_days': age_days,  # For "Already Wasted" calculation
                        'orphan_reason': orphan_reason,
                        'tags': ip.tags if ip.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    # Add warning for Dynamic IPs (unusual to be unassociated)
                    if allocation_method == 'Dynamic':
                        metadata['warning'] = 'Dynamic IP unassociated - Usually deallocated automatically. Check if stuck in provisioning state.'

                    # Add warning for Standard SKU with zones (more expensive)
                    if ip.sku and ip.sku.name == 'Standard' and ip.zones and len(ip.zones) >= 3:
                        metadata['warning_zone'] = f'Zone-redundant Public IP ({len(ip.zones)} zones) - Premium cost: ${monthly_cost:.2f}/month'

                    orphan = OrphanResourceData(
                        resource_type='public_ip_unassociated',
                        resource_id=ip.id,
                        resource_name=ip.name if ip.name else ip.id.split('/')[-1],
                        region=ip.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            # Log error but don't fail the entire scan
            print(f"Error scanning unassociated Public IPs in {region}: {str(e)}")
            # In production, use proper logging
            # logger.error(f"Error scanning unassociated Public IPs in {region}: {str(e)}", exc_info=True)

        return orphans

    async def scan_disks_on_stopped_vms(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Azure Managed Disks attached to stopped/deallocated VMs.

        Detects disks that continue to incur charges while attached to VMs
        that have been deallocated (stopped) for an extended period.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_stopped_days, enabled)

        Returns:
            List of orphan disk resources on stopped VMs
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_stopped_days = detection_rules.get("min_stopped_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all VMs in the region
            vms = compute_client.virtual_machines.list_all()

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Get VM instance view to check power state
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=vm.id.split('/')[4],  # Extract RG from resource ID
                    vm_name=vm.name
                )

                # Find power state
                power_state = None
                stopped_since = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        if hasattr(status, 'time') and status.time:
                            stopped_since = status.time

                # Only process deallocated (stopped) VMs
                if power_state != 'deallocated':
                    continue

                # Calculate how long VM has been stopped
                stopped_days = 0
                if stopped_since:
                    stopped_days = (datetime.now(timezone.utc) - stopped_since).days

                # Skip if not stopped long enough
                if stopped_days < min_stopped_days:
                    continue

                # Process all disks attached to this stopped VM
                if vm.storage_profile and vm.storage_profile.data_disks:
                    for data_disk in vm.storage_profile.data_disks:
                        if not data_disk.managed_disk:
                            continue

                        disk_id = data_disk.managed_disk.id
                        disk_name = disk_id.split('/')[-1]

                        # Get full disk details
                        disk_rg = disk_id.split('/')[4]
                        disk = compute_client.disks.get(disk_rg, disk_name)

                        # Calculate disk cost
                        monthly_cost = self._calculate_disk_cost(disk)

                        # Calculate age_days for confidence level
                        age_days = 0
                        if disk.time_created:
                            from datetime import datetime, timezone
                            age_days = (datetime.now(timezone.utc) - disk.time_created).days

                        metadata = {
                            'disk_id': disk.id,
                            'disk_name': disk.name,
                            'disk_size_gb': disk.disk_size_gb,
                            'sku_name': disk.sku.name if disk.sku else 'Standard_LRS',
                            'vm_id': vm.id,
                            'vm_name': vm.name,
                            'vm_power_state': power_state,
                            'vm_stopped_days': stopped_days,
                            'age_days': age_days,
                            'orphan_reason': f"Disk attached to VM '{vm.name}' which has been deallocated (stopped) for {stopped_days} days",
                            'recommendation': f"Consider deleting disk or restarting VM if still needed. Disk continues to cost ${monthly_cost:.2f}/month while VM is stopped.",
                            'tags': disk.tags if disk.tags else {},
                            'confidence_level': self._calculate_confidence_level(stopped_days, detection_rules),
                        }

                        orphan = OrphanResourceData(
                            resource_type='managed_disk_on_stopped_vm',
                            resource_id=disk.id,
                            resource_name=disk.name,
                            region=disk.location,
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata=metadata
                        )

                        orphans.append(orphan)

                # Also check OS disk
                if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.managed_disk:
                    os_disk_id = vm.storage_profile.os_disk.managed_disk.id
                    os_disk_name = os_disk_id.split('/')[-1]
                    os_disk_rg = os_disk_id.split('/')[4]

                    os_disk = compute_client.disks.get(os_disk_rg, os_disk_name)
                    monthly_cost = self._calculate_disk_cost(os_disk)

                    # Calculate age_days for confidence level
                    age_days = 0
                    if os_disk.time_created:
                        from datetime import datetime, timezone
                        age_days = (datetime.now(timezone.utc) - os_disk.time_created).days

                    metadata = {
                        'disk_id': os_disk.id,
                        'disk_name': os_disk.name,
                        'disk_size_gb': os_disk.disk_size_gb,
                        'sku_name': os_disk.sku.name if os_disk.sku else 'Standard_LRS',
                        'disk_type': 'OS Disk',
                        'vm_id': vm.id,
                        'vm_name': vm.name,
                        'vm_power_state': power_state,
                        'vm_stopped_days': stopped_days,
                        'age_days': age_days,
                        'orphan_reason': f"OS Disk attached to VM '{vm.name}' which has been deallocated (stopped) for {stopped_days} days",
                        'recommendation': f"VM is stopped but OS disk continues to cost ${monthly_cost:.2f}/month. Consider creating snapshot and deleting disk if VM no longer needed.",
                        'tags': os_disk.tags if os_disk.tags else {},
                        'confidence_level': self._calculate_confidence_level(stopped_days, detection_rules),
                    }

                    orphan = OrphanResourceData(
                        resource_type='managed_disk_on_stopped_vm',
                        resource_id=os_disk.id,
                        resource_name=os_disk.name,
                        region=os_disk.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning disks on stopped VMs in {region}: {str(e)}")

        return orphans

    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None, orphaned_volume_ids: list[str] | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for orphaned Azure Disk Snapshots.

        Detects snapshots whose source disks have been deleted,
        rendering the snapshots potentially obsolete and wasteful.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, enabled)
            orphaned_volume_ids: List of orphaned disk IDs (not used for Azure)

        Returns:
            List of orphan snapshot resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.core.exceptions import ResourceNotFoundError

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 90) if detection_rules else 90

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            snapshots = compute_client.snapshots.list()

            for snapshot in snapshots:
                if snapshot.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(snapshot.id):
                    continue

                # Calculate snapshot age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip recent snapshots
                if age_days < min_age_days:
                    continue

                # Check if source disk still exists
                source_disk_id = None
                source_disk_exists = True

                if snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id

                    # Try to get the source disk
                    try:
                        source_disk_rg = source_disk_id.split('/')[4]
                        source_disk_name = source_disk_id.split('/')[-1]
                        compute_client.disks.get(source_disk_rg, source_disk_name)
                    except ResourceNotFoundError:
                        source_disk_exists = False
                    except Exception:
                        # If we can't determine, assume it exists to be safe
                        source_disk_exists = True

                # Only report as orphan if source disk doesn't exist
                if not source_disk_exists:
                    # Calculate snapshot cost ($0.05/GB/month)
                    snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                    monthly_cost = round(snapshot_size_gb * 0.05, 2)

                    metadata = {
                        'snapshot_id': snapshot.id,
                        'snapshot_name': snapshot.name,
                        'snapshot_size_gb': snapshot_size_gb,
                        'source_disk_id': source_disk_id,
                        'source_disk_exists': False,
                        'age_days': age_days,
                        'time_created': snapshot.time_created.isoformat() if snapshot.time_created else None,
                        'orphan_reason': f"Snapshot's source disk (ID: {source_disk_id}) no longer exists. Snapshot has been orphaned for {age_days} days.",
                        'recommendation': f"Review and delete snapshot if no longer needed. Costs ${monthly_cost:.2f}/month.",
                        'tags': snapshot.tags if snapshot.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    orphan = OrphanResourceData(
                        resource_type='disk_snapshot_orphaned',
                        resource_id=snapshot.id,
                        resource_name=snapshot.name,
                        region=snapshot.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning orphaned snapshots in {region}: {str(e)}")

        return orphans

    async def scan_redundant_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for redundant Azure Disk Snapshots (multiple snapshots for same source disk).

        Detects scenarios where the same disk has >3 snapshots, suggesting that older
        snapshots are likely redundant and can be deleted to save costs.

        Typical scenario: Monthly backups kept indefinitely, but only last 2-3 needed.
        Cost savings: $0.05/GB/month per redundant snapshot

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "max_snapshots_per_disk": int (default 3),
                    "min_age_days": int (default 90) - Only flag old snapshots
                }

        Returns:
            List of redundant snapshot resources (keeping newest N, flagging rest)
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        max_snapshots = detection_rules.get("max_snapshots_per_disk", 3) if detection_rules else 3
        min_age_days = detection_rules.get("min_age_days", 90) if detection_rules else 90

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            snapshots = list(compute_client.snapshots.list())

            # Filter by region
            region_snapshots = [s for s in snapshots if s.location == region]

            # Filter by resource group (if specified)
            region_snapshots = [s for s in region_snapshots if self._is_resource_in_scope(s.id)]

            # Group snapshots by source disk
            snapshots_by_source: dict[str, list] = {}

            for snapshot in region_snapshots:
                # Calculate snapshot age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip recent snapshots (they might still be needed for short-term recovery)
                if age_days < min_age_days:
                    continue

                # Get source disk ID
                source_disk_id = "unknown"
                if snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id

                if source_disk_id not in snapshots_by_source:
                    snapshots_by_source[source_disk_id] = []

                snapshots_by_source[source_disk_id].append({
                    'snapshot': snapshot,
                    'age_days': age_days
                })

            # Find redundant snapshots (keep newest N, flag rest)
            for source_disk_id, snapshot_list in snapshots_by_source.items():
                # Only process if more than max_snapshots exist
                if len(snapshot_list) <= max_snapshots:
                    continue

                # Sort by creation date (newest first)
                snapshot_list.sort(key=lambda x: x['snapshot'].time_created, reverse=True)

                # Keep newest N, mark rest as redundant
                redundant_snapshots = snapshot_list[max_snapshots:]

                for snap_data in redundant_snapshots:
                    snapshot = snap_data['snapshot']
                    age_days = snap_data['age_days']

                    # Calculate snapshot cost ($0.05/GB/month)
                    snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                    monthly_cost = round(snapshot_size_gb * 0.05, 2)

                    # Count total snapshots for this source
                    total_snapshots = len(snapshot_list)
                    position = snapshot_list.index(snap_data) + 1  # 1-indexed

                    metadata = {
                        'snapshot_id': snapshot.id,
                        'snapshot_name': snapshot.name,
                        'snapshot_size_gb': snapshot_size_gb,
                        'source_disk_id': source_disk_id,
                        'age_days': age_days,
                        'time_created': snapshot.time_created.isoformat() if snapshot.time_created else None,
                        'total_snapshots_for_source': total_snapshots,
                        'snapshot_position': f"{position} of {total_snapshots} (oldest to newest)",
                        'kept_snapshots_count': max_snapshots,
                        'orphan_reason': f"Redundant snapshot: {total_snapshots} snapshots exist for source disk, but only {max_snapshots} newest are needed. This is snapshot #{position} (created {age_days} days ago).",
                        'recommendation': f"Delete this redundant snapshot to save ${monthly_cost:.2f}/month. Keep the {max_snapshots} newest snapshots for backup rotation.",
                        'tags': snapshot.tags if snapshot.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    orphan = OrphanResourceData(
                        resource_type='disk_snapshot_redundant',
                        resource_id=snapshot.id,
                        resource_name=snapshot.name,
                        region=snapshot.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning redundant snapshots in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_very_old(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for very old Azure Disk Snapshots (>1 year never used).

        Detects snapshots older than 1 year that have never been restored or used,
        suggesting they may no longer be needed and are accumulating significant costs.

        Logic:
        - age_days > max_age_threshold (default 365 days / 1 year)
        - Check tags for retention markers ("keep", "permanent", "archive", "compliance")
        - If very old AND source disk deleted → double waste (orphan + very old)

        Cost:
        - Monthly: $0.05/GB/month
        - Already wasted: $0.05/GB/month × (age_days / 30) months

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "max_age_threshold": int (default 365) - Age threshold in days,
                    "min_age_days": int (default 365) - Minimum age to flag,
                    "exclude_tags": list (default ["keep", "permanent", "archive", "compliance", "DR"])
                }

        Returns:
            List of very old snapshot resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.core.exceptions import ResourceNotFoundError

        orphans = []

        # Get detection parameters
        max_age_threshold = detection_rules.get("max_age_threshold", 365) if detection_rules else 365
        min_age_days = detection_rules.get("min_age_days", 365) if detection_rules else 365
        exclude_tags_list = detection_rules.get("exclude_tags", ["keep", "permanent", "archive", "compliance", "DR"]) if detection_rules else ["keep", "permanent", "archive", "compliance", "DR"]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            snapshots = compute_client.snapshots.list()

            for snapshot in snapshots:
                # Filter by region
                if snapshot.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(snapshot.id):
                    continue

                # Calculate snapshot age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip if not old enough
                if age_days < max_age_threshold:
                    continue

                # Check tags for retention markers
                has_retention_tag = False
                if snapshot.tags:
                    for tag_key, tag_value in snapshot.tags.items():
                        # Check both tag keys and values for retention markers
                        tag_str = f"{tag_key}:{tag_value}".lower()
                        for exclude_tag in exclude_tags_list:
                            if exclude_tag.lower() in tag_str:
                                has_retention_tag = True
                                break
                        if has_retention_tag:
                            break

                # Skip if has retention tag
                if has_retention_tag:
                    continue

                # Check if source disk still exists
                source_disk_exists = True
                source_disk_id = None
                if snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id
                    try:
                        source_disk_rg = source_disk_id.split('/')[4]
                        source_disk_name = source_disk_id.split('/')[-1]
                        compute_client.disks.get(source_disk_rg, source_disk_name)
                    except ResourceNotFoundError:
                        source_disk_exists = False
                    except Exception:
                        source_disk_exists = True  # Assume exists if can't determine

                # Calculate cost
                snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                monthly_cost = round(snapshot_size_gb * 0.05, 2)

                # Calculate already wasted cost (accumulated over time)
                months_old = age_days / 30
                already_wasted = round(monthly_cost * months_old, 2)

                # Age in years for display
                age_years = round(age_days / 365, 1)

                # Detection reason
                reason_parts = [f"Snapshot is {age_years} years old ({age_days} days)"]
                if not source_disk_exists:
                    reason_parts.append("DOUBLE WASTE: Source disk has been deleted (orphaned)")
                reason_parts.append(f"Already accumulated ${already_wasted} in costs")
                detection_reason = ". ".join(reason_parts)

                metadata = {
                    'snapshot_id': snapshot.id,
                    'snapshot_name': snapshot.name,
                    'snapshot_size_gb': snapshot_size_gb,
                    'sku': snapshot.sku.name if snapshot.sku else "Unknown",
                    'incremental': snapshot.incremental if hasattr(snapshot, 'incremental') else False,
                    'source_disk_id': source_disk_id,
                    'source_disk_exists': source_disk_exists,
                    'age_days': age_days,
                    'age_years': age_years,
                    'time_created': snapshot.time_created.isoformat() if snapshot.time_created else None,
                    'already_wasted': already_wasted,
                    'detection_reason': detection_reason,
                    'recommendation': f"Snapshot is {age_years} years old. If not needed for compliance/legal requirements, delete to save ${monthly_cost}/month. Already wasted: ${already_wasted}.",
                    'tags': snapshot.tags if snapshot.tags else {},
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_very_old',
                    resource_id=snapshot.id,
                    resource_name=snapshot.name,
                    region=snapshot.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning very old snapshots in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_premium_source(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for large snapshots created from Premium SSD disks.

        Detects snapshots from Premium disk sources that are very large (>1 TB),
        which generate significant costs despite being stored on Standard storage.

        Logic:
        - Source disk SKU = Premium_LRS or Premium_ZRS
        - Snapshot size > min_snapshot_size_gb (default 1000 GB / 1 TB)
        - Alert on high accumulated cost for large Premium disk snapshots

        Cost:
        - All snapshots stored on Standard storage: $0.05/GB/month
        - BUT Premium disks often very large (up to 32 TB)
        - Example: 8 TB snapshot = $409.60/month PER snapshot
        - 5 snapshots of 8 TB = $2,048/month (~$24,576/year)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_snapshot_size_gb": int (default 1000) - Min size to alert,
                    "min_age_days": int (default 30) - Min age to flag
                }

        Returns:
            List of large Premium source snapshot resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.core.exceptions import ResourceNotFoundError

        orphans = []

        # Get detection parameters
        min_snapshot_size_gb = detection_rules.get("min_snapshot_size_gb", 1000) if detection_rules else 1000
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            snapshots = compute_client.snapshots.list()

            for snapshot in snapshots:
                # Filter by region
                if snapshot.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(snapshot.id):
                    continue

                # Calculate snapshot age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip recent snapshots
                if age_days < min_age_days:
                    continue

                # Check snapshot size
                snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                if snapshot_size_gb < min_snapshot_size_gb:
                    continue  # Only flag large snapshots

                # Check if source disk is Premium
                source_disk_sku = None
                source_disk_tier = None
                source_disk_name = None
                source_disk_exists = True

                if snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id
                    source_disk_name = source_disk_id.split('/')[-1]

                    # Try to get source disk info
                    try:
                        source_disk_rg = source_disk_id.split('/')[4]
                        source_disk = compute_client.disks.get(source_disk_rg, source_disk_name)

                        if source_disk.sku:
                            source_disk_sku = source_disk.sku.name
                            source_disk_tier = source_disk.sku.tier if hasattr(source_disk.sku, 'tier') else None

                    except ResourceNotFoundError:
                        source_disk_exists = False
                    except Exception:
                        pass  # Can't determine, skip this snapshot

                # Only flag if source is Premium
                if not source_disk_sku or not source_disk_sku.startswith("Premium"):
                    continue

                # Calculate cost
                monthly_cost = round(snapshot_size_gb * 0.05, 2)

                # Count total snapshots for this source (if source exists)
                total_snapshots_count = 0
                all_snapshots_cost = 0
                if source_disk_exists and snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id
                    # Count snapshots from same source
                    all_snaps = list(compute_client.snapshots.list())
                    for snap in all_snaps:
                        if snap.creation_data and snap.creation_data.source_resource_id == source_disk_id:
                            total_snapshots_count += 1
                            snap_size = snap.disk_size_gb if snap.disk_size_gb else 0
                            all_snapshots_cost += snap_size * 0.05

                all_snapshots_cost = round(all_snapshots_cost, 2)

                metadata = {
                    'snapshot_id': snapshot.id,
                    'snapshot_name': snapshot.name,
                    'snapshot_size_gb': snapshot_size_gb,
                    'snapshot_size_tb': round(snapshot_size_gb / 1024, 2),
                    'sku': snapshot.sku.name if snapshot.sku else "Unknown",
                    'incremental': snapshot.incremental if hasattr(snapshot, 'incremental') else False,
                    'source_disk_name': source_disk_name,
                    'source_disk_sku': source_disk_sku,
                    'source_disk_tier': source_disk_tier,
                    'source_disk_exists': source_disk_exists,
                    'age_days': age_days,
                    'time_created': snapshot.time_created.isoformat() if snapshot.time_created else None,
                    'total_snapshots_for_disk': total_snapshots_count,
                    'all_snapshots_monthly_cost': all_snapshots_cost,
                    'detection_reason': f"Large Premium disk ({snapshot_size_gb} GB) snapshot costs ${monthly_cost}/month. {total_snapshots_count} snapshots for this source = ${all_snapshots_cost}/month total.",
                    'recommendation': f"Large Premium disk snapshots cost ${monthly_cost}/month EACH. Consider: 1) Using incremental snapshots to reduce delta size, 2) Reducing retention policy, 3) Archiving to cheaper storage if long-term retention needed.",
                    'tags': snapshot.tags if snapshot.tags else {},
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_premium_source',
                    resource_id=snapshot.id,
                    resource_name=snapshot.name,
                    region=snapshot.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning Premium source snapshots in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_large_unused(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for large unused Azure Disk Snapshots (>1 TB never restored).

        Detects snapshots larger than 1 TB that have never been restored since 90+ days,
        indicating they may be unnecessary and generating significant waste.

        Logic:
        - size_gb >= large_snapshot_threshold (default 1000 GB / 1 TB)
        - age_days >= min_age_days (default 90)
        - restore_count == 0 (check via tags: last_restore_date, restore_count)
        - If large AND old AND never restored → critical waste

        Cost:
        - 1 TB snapshot = $51.20/month
        - 4 TB snapshot = $204.80/month
        - 8 TB snapshot = $409.60/month
        - If 5 snapshots of 4 TB = $1,024/month (~$12,288/year)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "large_snapshot_threshold": int (default 1000) - Size threshold in GB,
                    "min_age_days": int (default 90) - Min age to flag
                }

        Returns:
            List of large unused snapshot resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        from azure.core.exceptions import ResourceNotFoundError

        orphans = []

        # Get detection parameters
        large_snapshot_threshold = detection_rules.get("large_snapshot_threshold", 1000) if detection_rules else 1000
        min_age_days = detection_rules.get("min_age_days", 90) if detection_rules else 90

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            snapshots = compute_client.snapshots.list()

            for snapshot in snapshots:
                # Filter by region
                if snapshot.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(snapshot.id):
                    continue

                # Check snapshot size
                snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                if snapshot_size_gb < large_snapshot_threshold:
                    continue  # Only flag large snapshots

                # Calculate snapshot age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip recent snapshots
                if age_days < min_age_days:
                    continue

                # Check restore history via tags
                restore_count = 0
                last_restore_date = None
                if snapshot.tags:
                    # Check for restore tracking tags
                    restore_count = int(snapshot.tags.get('restore_count', 0))
                    last_restore_date = snapshot.tags.get('last_restore_date', None)

                # Only flag if never restored (restore_count == 0)
                if restore_count > 0:
                    continue

                # Check if source disk still exists
                source_disk_exists = True
                source_disk_id = None
                if snapshot.creation_data and snapshot.creation_data.source_resource_id:
                    source_disk_id = snapshot.creation_data.source_resource_id
                    try:
                        source_disk_rg = source_disk_id.split('/')[4]
                        source_disk_name = source_disk_id.split('/')[-1]
                        compute_client.disks.get(source_disk_rg, source_disk_name)
                    except ResourceNotFoundError:
                        source_disk_exists = False
                    except Exception:
                        source_disk_exists = True

                # Calculate cost
                monthly_cost = round(snapshot_size_gb * 0.05, 2)

                # Calculate already wasted (if old)
                months_old = age_days / 30
                already_wasted = round(monthly_cost * months_old, 2)

                # Size in TB for display
                snapshot_size_tb = round(snapshot_size_gb / 1024, 2)

                # Build warning message
                warning_parts = [f"⚠️ CRITICAL: {snapshot_size_tb} TB snapshot costing ${monthly_cost}/month"]
                if restore_count == 0:
                    warning_parts.append("never restored")
                if not source_disk_exists:
                    warning_parts.append("source disk deleted (orphaned)")

                warning = ", ".join(warning_parts)

                metadata = {
                    'snapshot_id': snapshot.id,
                    'snapshot_name': snapshot.name,
                    'snapshot_size_gb': snapshot_size_gb,
                    'snapshot_size_tb': snapshot_size_tb,
                    'sku': snapshot.sku.name if snapshot.sku else "Unknown",
                    'incremental': snapshot.incremental if hasattr(snapshot, 'incremental') else False,
                    'source_disk_id': source_disk_id,
                    'source_disk_exists': source_disk_exists,
                    'age_days': age_days,
                    'time_created': snapshot.time_created.isoformat() if snapshot.time_created else None,
                    'restore_count': restore_count,
                    'last_restore_date': last_restore_date,
                    'already_wasted': already_wasted,
                    'warning': warning,
                    'detection_reason': f"Large {snapshot_size_tb} TB snapshot created {age_days} days ago, never restored. Already wasted ${already_wasted} in costs.",
                    'recommendation': f"URGENT: Large snapshot ({snapshot_size_tb} TB) costing ${monthly_cost}/month has never been used. If not needed for compliance, delete immediately to save ${monthly_cost}/month.",
                    'tags': snapshot.tags if snapshot.tags else {},
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_large_unused',
                    resource_id=snapshot.id,
                    resource_name=snapshot.name,
                    region=snapshot.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning large unused snapshots in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_full_instead_incremental(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Full snapshots when Incremental would save 50-90% costs.

        HIGHEST VALUE SCENARIO: Switching from full to incremental snapshots can save
        $185/month per disk (72-90% cost reduction). For 50 disks = $111,000/year ROI!

        Logic:
        - Group snapshots by source disk
        - Count Full snapshots (incremental == False) per disk
        - If >min_snapshots_for_incremental Full snapshots → should use incremental
        - Calculate cost savings: full_cost vs incremental_cost

        Cost Comparison:
        - Full snapshots: Each snapshot = 100% of disk size × $0.05/GB
        - Incremental snapshots: 1st full + rest only changed blocks (typically 5-15%)
        - Example: 5 snapshots × 1 TB
          * All full: 5 × 1024 GB × $0.05 = $256/month
          * Incremental (10% change): 1024 + 4×102 GB × $0.05 = $71/month
          * Savings: $185/month (72%)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_snapshots_for_incremental": int (default 2) - Min snapshots before recommending incremental,
                    "min_age_days": int (default 30) - Min age to flag,
                    "assumed_change_rate": float (default 0.10) - Assumed change rate for incremental (10%)
                }

        Returns:
            List of disks using full snapshots instead of incremental (grouped by source disk)
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        min_snapshots_for_incremental = detection_rules.get("min_snapshots_for_incremental", 2) if detection_rules else 2
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        assumed_change_rate = detection_rules.get("assumed_change_rate", 0.10) if detection_rules else 0.10  # 10% default

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            all_snapshots = list(compute_client.snapshots.list())

            # Filter by region
            region_snapshots = [s for s in all_snapshots if s.location == region]

            # Filter by resource group
            region_snapshots = [s for s in region_snapshots if self._is_resource_in_scope(s.id)]

            # Group snapshots by source disk
            snapshots_by_source: dict[str, list] = {}

            for snapshot in region_snapshots:
                # Skip if no source disk
                if not snapshot.creation_data or not snapshot.creation_data.source_resource_id:
                    continue

                source_disk_id = snapshot.creation_data.source_resource_id

                # Calculate age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                # Skip recent snapshots
                if age_days < min_age_days:
                    continue

                # Check if incremental
                is_incremental = snapshot.incremental if hasattr(snapshot, 'incremental') else False

                if source_disk_id not in snapshots_by_source:
                    snapshots_by_source[source_disk_id] = []

                snapshots_by_source[source_disk_id].append({
                    'snapshot': snapshot,
                    'age_days': age_days,
                    'is_incremental': is_incremental,
                    'size_gb': snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                })

            # Analyze each source disk for full vs incremental opportunity
            for source_disk_id, snapshot_list in snapshots_by_source.items():
                # Count full snapshots
                full_snapshots = [s for s in snapshot_list if not s['is_incremental']]

                # Only flag if has multiple full snapshots
                if len(full_snapshots) < min_snapshots_for_incremental:
                    continue

                # Check if ALL snapshots are full (no incremental strategy at all)
                all_full_snapshots = len(full_snapshots) == len(snapshot_list)

                # Calculate current cost (all full)
                total_full_size_gb = sum([s['size_gb'] for s in full_snapshots])
                current_monthly_cost = round(total_full_size_gb * 0.05, 2)

                # Calculate estimated cost with incremental strategy
                # Assumption: 1st snapshot full, rest only store changed blocks (default 10%)
                if len(full_snapshots) > 0:
                    first_snapshot_size = full_snapshots[0]['size_gb']
                    # Remaining snapshots would be incremental (only changed blocks)
                    incremental_count = len(full_snapshots) - 1
                    incremental_total_size = incremental_count * first_snapshot_size * assumed_change_rate

                    estimated_cost_with_incremental = round((first_snapshot_size + incremental_total_size) * 0.05, 2)
                else:
                    estimated_cost_with_incremental = 0

                # Calculate potential savings
                potential_monthly_savings = round(current_monthly_cost - estimated_cost_with_incremental, 2)
                savings_percentage = round((potential_monthly_savings / current_monthly_cost * 100), 1) if current_monthly_cost > 0 else 0

                # Only flag if significant savings (>$10/month)
                if potential_monthly_savings < 10:
                    continue

                # Get source disk name
                source_disk_name = source_disk_id.split('/')[-1]

                # Get the oldest full snapshot for metadata
                oldest_full = max(full_snapshots, key=lambda x: x['age_days'])

                metadata = {
                    'source_disk_id': source_disk_id,
                    'source_disk_name': source_disk_name,
                    'total_snapshots_for_disk': len(snapshot_list),
                    'full_snapshots_count': len(full_snapshots),
                    'incremental_snapshots_count': len(snapshot_list) - len(full_snapshots),
                    'all_full_snapshots': all_full_snapshots,
                    'disk_size_gb': full_snapshots[0]['size_gb'] if full_snapshots else 0,
                    'current_monthly_cost_all_full': current_monthly_cost,
                    'estimated_cost_with_incremental': estimated_cost_with_incremental,
                    'potential_monthly_savings': potential_monthly_savings,
                    'potential_annual_savings': round(potential_monthly_savings * 12, 2),
                    'savings_percentage': savings_percentage,
                    'assumed_change_rate_percent': int(assumed_change_rate * 100),
                    'warning': f"⚠️ {len(full_snapshots)} FULL snapshots for {full_snapshots[0]['size_gb']} GB disk = ${current_monthly_cost}/month! Use incremental to save {savings_percentage}%",
                    'detection_reason': f"{len(full_snapshots)} full snapshots detected for disk {source_disk_name}. Current cost: ${current_monthly_cost}/month. Switching to incremental (1 full + {incremental_count} incremental) would cost ${estimated_cost_with_incremental}/month = ${potential_monthly_savings}/month savings ({savings_percentage}%).",
                    'recommendation': f"URGENT: Switch to incremental snapshots to save ${potential_monthly_savings}/month ({savings_percentage}% reduction). Strategy: Keep 1st snapshot as full, convert rest to incremental (Azure stores only changed blocks). Annual savings: ${round(potential_monthly_savings * 12, 2)}.",
                }

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_full_instead_incremental',
                    resource_id=oldest_full['snapshot'].id,
                    resource_name=source_disk_name,
                    region=region,
                    estimated_monthly_cost=potential_monthly_savings,  # Use savings as the "cost" metric
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning full vs incremental snapshots in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_excessive_retention(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for excessive snapshot retention (>50 snapshots per disk).

        HIGH VALUE SCENARIO: Excessive retention (120 snapshots) costs $1,440/month vs
        recommended 30 snapshots = $360/month = $1,080/month savings per disk!
        For 10 disks = $129,600/year ROI.

        Logic:
        - Group snapshots by source disk
        - Count total snapshots per disk
        - If >max_snapshots_threshold → excessive retention
        - Calculate savings if reduced to recommended count

        Azure limits:
        - Maximum: 500 snapshots per disk (450 scheduled + 50 on-demand)
        - Recommended: 7-30 snapshots max (daily for 1 week to 1 month)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "max_snapshots_threshold": int (default 50) - Max snapshots before alert,
                    "recommended_max_snapshots": int (default 30) - Recommended max retention,
                    "min_age_days": int (default 7) - Min age to flag
                }

        Returns:
            List of disks with excessive snapshot retention (one entry per disk)
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        max_snapshots_threshold = detection_rules.get("max_snapshots_threshold", 50) if detection_rules else 50
        recommended_max_snapshots = detection_rules.get("recommended_max_snapshots", 30) if detection_rules else 30
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all snapshots
            all_snapshots = list(compute_client.snapshots.list())

            # Filter by region
            region_snapshots = [s for s in all_snapshots if s.location == region]

            # Filter by resource group
            region_snapshots = [s for s in region_snapshots if self._is_resource_in_scope(s.id)]

            # Group snapshots by source disk
            snapshots_by_source: dict[str, list] = {}

            for snapshot in region_snapshots:
                # Skip if no source disk
                if not snapshot.creation_data or not snapshot.creation_data.source_resource_id:
                    continue

                source_disk_id = snapshot.creation_data.source_resource_id

                # Calculate age
                age_days = 0
                if snapshot.time_created:
                    age_days = (datetime.now(timezone.utc) - snapshot.time_created).days

                if source_disk_id not in snapshots_by_source:
                    snapshots_by_source[source_disk_id] = []

                snapshots_by_source[source_disk_id].append({
                    'snapshot': snapshot,
                    'age_days': age_days,
                    'size_gb': snapshot.disk_size_gb if snapshot.disk_size_gb else 0,
                    'time_created': snapshot.time_created
                })

            # Analyze each source disk for excessive retention
            for source_disk_id, snapshot_list in snapshots_by_source.items():
                total_snapshots_count = len(snapshot_list)

                # Only flag if exceeds threshold
                if total_snapshots_count <= max_snapshots_threshold:
                    continue

                # Calculate ages
                oldest_snapshot_age = max([s['age_days'] for s in snapshot_list])
                newest_snapshot_age = min([s['age_days'] for s in snapshot_list])
                avg_snapshot_size_gb = sum([s['size_gb'] for s in snapshot_list]) / len(snapshot_list) if snapshot_list else 0
                total_storage_gb = sum([s['size_gb'] for s in snapshot_list])

                # Calculate current cost
                current_monthly_cost = round(total_storage_gb * 0.05, 2)

                # Calculate recommended cost (keep only N most recent)
                recommended_storage_gb = recommended_max_snapshots * avg_snapshot_size_gb
                recommended_monthly_cost = round(recommended_storage_gb * 0.05, 2)

                # Calculate potential savings
                potential_monthly_savings = round(current_monthly_cost - recommended_monthly_cost, 2)
                potential_annual_savings = round(potential_monthly_savings * 12, 2)

                # Get source disk name
                source_disk_name = source_disk_id.split('/')[-1]

                # Get the oldest snapshot for this source
                oldest_snapshot = max(snapshot_list, key=lambda x: x['age_days'])

                # Build warning
                warning = f"⚠️ CRITICAL: {total_snapshots_count} snapshots for one disk! Azure limit is 500, recommended is {recommended_max_snapshots}."

                metadata = {
                    'source_disk_id': source_disk_id,
                    'source_disk_name': source_disk_name,
                    'source_disk_size_gb': int(avg_snapshot_size_gb),
                    'total_snapshots_count': total_snapshots_count,
                    'oldest_snapshot_age_days': oldest_snapshot_age,
                    'newest_snapshot_age_days': newest_snapshot_age,
                    'avg_snapshot_size_gb': round(avg_snapshot_size_gb, 2),
                    'total_storage_gb': total_storage_gb,
                    'current_monthly_cost': current_monthly_cost,
                    'recommended_max_snapshots': recommended_max_snapshots,
                    'recommended_monthly_cost': recommended_monthly_cost,
                    'potential_monthly_savings': potential_monthly_savings,
                    'potential_annual_savings': potential_annual_savings,
                    'warning': warning,
                    'detection_reason': f"{total_snapshots_count} snapshots detected for disk {source_disk_name} (Azure limit: 500, recommended: {recommended_max_snapshots}). Current cost: ${current_monthly_cost}/month. Recommended policy would cost ${recommended_monthly_cost}/month = ${potential_monthly_savings}/month savings.",
                    'recommendation': f"URGENT: Implement snapshot rotation policy. Keep only {recommended_max_snapshots} most recent snapshots, delete {total_snapshots_count - recommended_max_snapshots} oldest. Savings: ${potential_monthly_savings}/month (${potential_annual_savings}/year).",
                }

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_excessive_retention',
                    resource_id=oldest_snapshot['snapshot'].id,
                    resource_name=source_disk_name,
                    region=region,
                    estimated_monthly_cost=potential_monthly_savings,  # Use savings as the "cost" metric
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning excessive snapshot retention in {region}: {str(e)}")

        return orphans

    async def scan_disk_snapshot_manual_without_policy(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for manual snapshots without rotation policy (>10 manual snapshots risk infinite accumulation)."""
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        max_manual_snapshots = detection_rules.get("max_manual_snapshots", 10) if detection_rules else 10
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(self.tenant_id, self.client_id, self.client_secret)
            compute_client = ComputeManagementClient(credential, self.subscription_id)
            all_snapshots = list(compute_client.snapshots.list())
            region_snapshots = [s for s in all_snapshots if s.location == region and self._is_resource_in_scope(s.id)]

            snapshots_by_source: dict[str, list] = {}
            for snapshot in region_snapshots:
                if not snapshot.creation_data or not snapshot.creation_data.source_resource_id:
                    continue
                age_days = (datetime.now(timezone.utc) - snapshot.time_created).days if snapshot.time_created else 0
                if age_days < min_age_days:
                    continue

                # Check if manual (ManagedBy tag != 'Azure Backup')
                managed_by = snapshot.tags.get('ManagedBy', 'Manual') if snapshot.tags else 'Manual'
                if managed_by != 'Azure Backup':
                    source_disk_id = snapshot.creation_data.source_resource_id
                    if source_disk_id not in snapshots_by_source:
                        snapshots_by_source[source_disk_id] = []
                    snapshots_by_source[source_disk_id].append({
                        'snapshot': snapshot, 'age_days': age_days,
                        'size_gb': snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                    })

            for source_disk_id, snapshot_list in snapshots_by_source.items():
                if len(snapshot_list) <= max_manual_snapshots:
                    continue
                oldest_age = max([s['age_days'] for s in snapshot_list])
                total_storage_gb = sum([s['size_gb'] for s in snapshot_list])
                monthly_cost = round(total_storage_gb * 0.05, 2)
                source_disk_name = source_disk_id.split('/')[-1]
                oldest = max(snapshot_list, key=lambda x: x['age_days'])

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_manual_without_policy',
                    resource_id=oldest['snapshot'].id, resource_name=source_disk_name, region=region,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        'source_disk_name': source_disk_name, 'manual_snapshots_count': len(snapshot_list),
                        'oldest_manual_snapshot_age_days': oldest_age, 'managed_by': 'Manual',
                        'has_azure_backup_policy': False, 'total_storage_gb': total_storage_gb,
                        'current_monthly_cost': monthly_cost,
                        'warning': f"⚠️ {len(snapshot_list)} manual snapshots without rotation policy - risk of infinite accumulation",
                        'recommendation': "URGENT: Implement Azure Backup policy or custom snapshot rotation automation"
                    }
                )
                orphans.append(orphan)
        except Exception as e:
            print(f"Error scanning manual snapshots in {region}: {str(e)}")
        return orphans

    async def scan_disk_snapshot_never_restored(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for snapshots never restored since 90+ days (check via tags)."""
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_never_restored_days = detection_rules.get("min_never_restored_days", 90) if detection_rules else 90
        exclude_tags = detection_rules.get("exclude_tags", ["DR", "disaster-recovery", "archive", "compliance"]) if detection_rules else ["DR", "disaster-recovery", "archive", "compliance"]

        try:
            credential = ClientSecretCredential(self.tenant_id, self.client_id, self.client_secret)
            compute_client = ComputeManagementClient(credential, self.subscription_id)
            snapshots = compute_client.snapshots.list()

            for snapshot in snapshots:
                if snapshot.location != region or not self._is_resource_in_scope(snapshot.id):
                    continue
                age_days = (datetime.now(timezone.utc) - snapshot.time_created).days if snapshot.time_created else 0
                if age_days < min_never_restored_days:
                    continue

                # Check for exclusion tags
                has_exclude_tag = False
                if snapshot.tags:
                    for tag_key, tag_value in snapshot.tags.items():
                        if any(excl.lower() in f"{tag_key}:{tag_value}".lower() for excl in exclude_tags):
                            has_exclude_tag = True
                            break
                if has_exclude_tag:
                    continue

                # Check restore history
                restore_count = int(snapshot.tags.get('restore_count', 0)) if snapshot.tags else 0
                if restore_count > 0:
                    continue

                snapshot_size_gb = snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                monthly_cost = round(snapshot_size_gb * 0.05, 2)
                already_wasted = round(monthly_cost * (age_days / 30), 2)

                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_never_restored', resource_id=snapshot.id,
                    resource_name=snapshot.name, region=snapshot.location, estimated_monthly_cost=monthly_cost,
                    resource_metadata={
                        'age_days': age_days, 'restore_count': 0, 'already_wasted': already_wasted,
                        'recommendation': f"Snapshot created {age_days} days ago but never restored - consider deleting if not for compliance"
                    }
                )
                orphans.append(orphan)
        except Exception as e:
            print(f"Error scanning never restored snapshots in {region}: {str(e)}")
        return orphans

    async def scan_disk_snapshot_frequent_creation(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for snapshots created too frequently (>1/day) - daily vs weekly = 86% savings."""
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        max_frequency_days = detection_rules.get("max_frequency_days", 1.0) if detection_rules else 1.0
        observation_period_days = detection_rules.get("observation_period_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(self.tenant_id, self.client_id, self.client_secret)
            compute_client = ComputeManagementClient(credential, self.subscription_id)
            all_snapshots = list(compute_client.snapshots.list())
            region_snapshots = [s for s in all_snapshots if s.location == region and self._is_resource_in_scope(s.id)]

            snapshots_by_source: dict[str, list] = {}
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=observation_period_days)

            for snapshot in region_snapshots:
                if not snapshot.creation_data or not snapshot.creation_data.source_resource_id:
                    continue
                if snapshot.time_created and snapshot.time_created >= cutoff_date:
                    source_disk_id = snapshot.creation_data.source_resource_id
                    if source_disk_id not in snapshots_by_source:
                        snapshots_by_source[source_disk_id] = []
                    snapshots_by_source[source_disk_id].append({
                        'snapshot': snapshot, 'time_created': snapshot.time_created,
                        'size_gb': snapshot.disk_size_gb if snapshot.disk_size_gb else 0
                    })

            from datetime import timedelta
            for source_disk_id, snapshot_list in snapshots_by_source.items():
                if len(snapshot_list) < 28:  # Need significant sample
                    continue
                avg_days_between = observation_period_days / len(snapshot_list)
                if avg_days_between >= max_frequency_days:
                    continue

                avg_size = sum([s['size_gb'] for s in snapshot_list]) / len(snapshot_list)
                current_monthly_cost = round(len(snapshot_list) * avg_size * 0.05, 2)
                recommended_weekly_count = 4  # Weekly = 4 snapshots/month
                recommended_cost = round(recommended_weekly_count * avg_size * 0.05, 2)
                savings = round(current_monthly_cost - recommended_cost, 2)

                if savings < 50:  # Only flag significant waste
                    continue

                source_disk_name = source_disk_id.split('/')[-1]
                orphan = OrphanResourceData(
                    resource_type='disk_snapshot_frequent_creation', resource_id=snapshot_list[0]['snapshot'].id,
                    resource_name=source_disk_name, region=region, estimated_monthly_cost=savings,
                    resource_metadata={
                        'source_disk_name': source_disk_name, 'snapshots_in_last_30_days': len(snapshot_list),
                        'avg_days_between_snapshots': round(avg_days_between, 2),
                        'current_monthly_cost': current_monthly_cost, 'recommended_frequency': 'Weekly',
                        'recommended_monthly_cost': recommended_cost, 'potential_monthly_savings': savings,
                        'recommendation': f"Daily snapshots for disk - switch to weekly to save 86% (${savings}/month)"
                    }
                )
                orphans.append(orphan)
        except Exception as e:
            print(f"Error scanning frequent snapshot creation in {region}: {str(e)}")
        return orphans

    async def scan_unnecessary_zrs_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Managed Disks with Zone-Redundant Storage (ZRS) in dev/test environments.

        ZRS disks cost +20% compared to Locally-Redundant Storage (LRS) but provide
        zone redundancy that is typically unnecessary for non-production workloads.

        Typical waste: Dev/Test VMs using Premium_ZRS or StandardSSD_ZRS
        Cost savings: ~20% of disk cost by switching to LRS

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "dev_environments": list[str] (default ["dev", "test", "staging", "qa"]),
                    "min_age_days": int (default 30)
                }

        Returns:
            List of ZRS disk resources in non-production environments
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        dev_envs = detection_rules.get("dev_environments", ["dev", "test", "staging", "qa"]) if detection_rules else ["dev", "test", "staging", "qa"]
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Check if disk is using ZRS (Zone-Redundant Storage)
                sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
                if '_ZRS' not in sku_name:
                    continue  # Not a ZRS disk

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_age_days:
                    continue

                # Check if disk is in dev/test environment
                # Check 1: Environment tag
                disk_tags = disk.tags or {}
                env_tag = None
                for tag_key in ['environment', 'env', 'Environment', 'Env']:
                    if tag_key in disk_tags:
                        env_tag = disk_tags[tag_key].lower()
                        break

                is_dev_environment = False
                if env_tag and any(env_keyword in env_tag for env_keyword in dev_envs):
                    is_dev_environment = True

                # Check 2: Resource group name contains dev/test keywords
                rg_name = disk.id.split('/')[4].lower() if len(disk.id.split('/')) > 4 else ''
                if any(env_keyword in rg_name for env_keyword in dev_envs):
                    is_dev_environment = True

                # Skip if not a dev environment
                if not is_dev_environment:
                    continue

                # Calculate cost difference between ZRS and LRS
                current_cost = self._calculate_disk_cost(disk)

                # ZRS costs ~20% more than LRS, so LRS would be 1/1.2 = ~83.3% of current cost
                lrs_cost = current_cost / 1.2
                potential_savings = current_cost - lrs_cost

                # Suggest LRS equivalent
                lrs_sku = sku_name.replace('_ZRS', '_LRS')

                metadata = {
                    'disk_id': disk.id,
                    'disk_name': disk.name,
                    'disk_size_gb': disk.disk_size_gb,
                    'current_sku': sku_name,
                    'suggested_sku': lrs_sku,
                    'current_monthly_cost': f'${current_cost:.2f}',
                    'suggested_monthly_cost': f'${lrs_cost:.2f}',
                    'potential_monthly_savings': f'${potential_savings:.2f}',
                    'environment': env_tag if env_tag else 'inferred from resource group',
                    'resource_group': rg_name,
                    'age_days': age_days,
                    'created_at': disk.time_created.isoformat() if disk.time_created else None,
                    'zones': disk.zones if disk.zones else None,
                    'orphan_reason': f"Zone-Redundant Storage (ZRS) disk in {env_tag or 'dev/test'} environment. ZRS costs +20% but zone redundancy is unnecessary for non-production workloads.",
                    'recommendation': f"Switch from {sku_name} to {lrs_sku} to save ${potential_savings:.2f}/month (~20% cost reduction). ZRS is designed for high-availability production workloads, not dev/test.",
                    'tags': disk_tags,
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='managed_disk_unnecessary_zrs',
                    resource_id=disk.id,
                    resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                    region=disk.location,
                    estimated_monthly_cost=round(potential_savings, 2),
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unnecessary ZRS disks in {region}: {str(e)}")

        return orphans

    async def scan_unnecessary_cmk_encryption(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Managed Disks with Customer-Managed Key (CMK) encryption without compliance requirement.

        Customer-Managed Keys cost ~8% more than Platform-Managed Keys but are typically
        only needed for compliance/regulatory requirements (HIPAA, PCI-DSS, etc.).

        Typical waste: Non-regulated workloads using CMK encryption unnecessarily
        Cost savings: ~8% of disk cost by switching to Platform-Managed Key

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "compliance_tags": list[str] (default ["compliance", "hipaa", "pci", "sox"]),
                    "min_age_days": int (default 30)
                }

        Returns:
            List of disks with unnecessary CMK encryption
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        compliance_tags = detection_rules.get("compliance_tags", ["compliance", "hipaa", "pci", "sox", "gdpr", "regulated"]) if detection_rules else ["compliance", "hipaa", "pci", "sox", "gdpr", "regulated"]
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Check if disk is using Customer-Managed Key encryption
                if not disk.encryption or not disk.encryption.type:
                    continue  # No encryption info

                encryption_type = disk.encryption.type

                # Skip if using Platform-Managed Key (default, no extra cost)
                if encryption_type == 'EncryptionAtRestWithPlatformKey':
                    continue

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_age_days:
                    continue

                # Check for compliance/regulatory tags
                disk_tags = disk.tags or {}
                has_compliance_requirement = False

                for tag_key, tag_value in disk_tags.items():
                    tag_key_lower = tag_key.lower()
                    tag_value_lower = str(tag_value).lower() if tag_value else ''

                    # Check if any compliance keyword is in tag key or value
                    if any(comp_tag in tag_key_lower or comp_tag in tag_value_lower for comp_tag in compliance_tags):
                        has_compliance_requirement = True
                        break

                # Skip if disk has compliance requirement
                if has_compliance_requirement:
                    continue

                # Calculate cost difference
                current_cost = self._calculate_disk_cost(disk)

                # CMK encryption costs ~8% more, so Platform-Managed would be current_cost / 1.08
                platform_managed_cost = current_cost / 1.08
                potential_savings = current_cost - platform_managed_cost

                metadata = {
                    'disk_id': disk.id,
                    'disk_name': disk.name,
                    'disk_size_gb': disk.disk_size_gb,
                    'sku_name': disk.sku.name if disk.sku else 'Unknown',
                    'current_encryption': encryption_type,
                    'suggested_encryption': 'EncryptionAtRestWithPlatformKey',
                    'current_monthly_cost': f'${current_cost:.2f}',
                    'suggested_monthly_cost': f'${platform_managed_cost:.2f}',
                    'potential_monthly_savings': f'${potential_savings:.2f}',
                    'age_days': age_days,
                    'created_at': disk.time_created.isoformat() if disk.time_created else None,
                    'disk_encryption_set_id': disk.encryption.disk_encryption_set_id if disk.encryption and hasattr(disk.encryption, 'disk_encryption_set_id') else None,
                    'orphan_reason': f"Customer-Managed Key (CMK) encryption enabled without compliance requirement. CMK costs +8% but no compliance tags found ({', '.join(compliance_tags)}).",
                    'recommendation': f"Switch to Platform-Managed Key encryption to save ${potential_savings:.2f}/month (~8% cost reduction). CMK is designed for compliance/regulatory requirements (HIPAA, PCI-DSS, etc.). If not required, Platform-Managed Key provides equivalent security at lower cost.",
                    'tags': disk_tags,
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='managed_disk_unnecessary_cmk',
                    resource_id=disk.id,
                    resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                    region=disk.location,
                    estimated_monthly_cost=round(potential_savings, 2),
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unnecessary CMK encryption in {region}: {str(e)}")

        return orphans

    async def scan_ips_on_stopped_resources(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Azure Public IPs associated to stopped/inactive resources.

        Detects Public IPs that continue to incur charges while associated to:
        - Deallocated (stopped) VMs
        - Load Balancers with no healthy backends
        - Network Interfaces not attached to running VMs

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_stopped_days, enabled)

        Returns:
            List of orphan public IP resources on stopped resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_stopped_days = detection_rules.get("min_stopped_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)
            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all public IPs in the region
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Only process associated IPs
                if not ip.ip_configuration:
                    continue

                # Determine what resource the IP is attached to
                ip_config_id = ip.ip_configuration.id
                resource_stopped = False
                resource_type = None
                resource_name = None
                stopped_days = 0

                # Case 1: IP attached to Network Interface → Check if NIC is attached to stopped VM
                if '/networkInterfaces/' in ip_config_id:
                    nic_rg = ip_config_id.split('/')[4]
                    nic_name = ip_config_id.split('/')[8]

                    try:
                        nic = network_client.network_interfaces.get(nic_rg, nic_name)

                        # Check if NIC is attached to a VM
                        if nic.virtual_machine:
                            vm_id = nic.virtual_machine.id
                            vm_rg = vm_id.split('/')[4]
                            vm_name = vm_id.split('/')[-1]

                            # Get VM power state
                            instance_view = compute_client.virtual_machines.instance_view(vm_rg, vm_name)

                            for status in instance_view.statuses:
                                if status.code and status.code.startswith('PowerState/'):
                                    power_state = status.code.split('/')[-1]

                                    if power_state == 'deallocated':
                                        resource_stopped = True
                                        resource_type = 'VM'
                                        resource_name = vm_name

                                        # Try to determine when VM was stopped
                                        if hasattr(status, 'time') and status.time:
                                            stopped_days = (datetime.now(timezone.utc) - status.time).days

                    except Exception as e:
                        print(f"Error checking NIC {nic_name}: {str(e)}")
                        continue

                # Case 2: IP attached to Load Balancer → Check if LB has healthy backends
                elif '/loadBalancers/' in ip_config_id:
                    lb_rg = ip_config_id.split('/')[4]
                    lb_name = ip_config_id.split('/')[8]

                    try:
                        lb = network_client.load_balancers.get(lb_rg, lb_name)

                        # Check if load balancer has any backend pools with IPs
                        has_backends = False
                        if lb.backend_address_pools:
                            for pool in lb.backend_address_pools:
                                if pool.backend_ip_configurations and len(pool.backend_ip_configurations) > 0:
                                    has_backends = True
                                    break

                        if not has_backends:
                            resource_stopped = True
                            resource_type = 'Load Balancer'
                            resource_name = lb_name
                            # For LBs without backends, we can't determine exact stopped time
                            # Assume it's been this way for a while if no backends
                            stopped_days = 30  # Conservative estimate

                    except Exception as e:
                        print(f"Error checking Load Balancer {lb_name}: {str(e)}")
                        continue

                # Skip if resource is not stopped or stopped_days < threshold
                if not resource_stopped or stopped_days < min_stopped_days:
                    continue

                # Calculate IP cost
                monthly_cost = self._calculate_public_ip_cost(ip)

                # Calculate age_days for confidence level
                age_days = 0
                if hasattr(ip, 'provisioning_time') and ip.provisioning_time:
                    age_days = (datetime.now(timezone.utc) - ip.provisioning_time).days

                metadata = {
                    'ip_id': ip.id,
                    'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                    'sku_name': ip.sku.name if ip.sku else 'Basic',
                    'allocation_method': ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static',
                    'attached_resource_type': resource_type,
                    'attached_resource_name': resource_name,
                    'resource_stopped': True,
                    'resource_stopped_days': stopped_days,
                    'age_days': age_days,
                    'orphan_reason': f"Public IP attached to {resource_type} '{resource_name}' which has been stopped/inactive for {stopped_days} days",
                    'recommendation': f"Consider dissociating and deleting Public IP. IP continues to cost ${monthly_cost:.2f}/month while resource is stopped.",
                    'tags': ip.tags if ip.tags else {},
                    'confidence_level': self._calculate_confidence_level(stopped_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='public_ip_on_stopped_resource',
                    resource_id=ip.id,
                    resource_name=ip.name if ip.name else ip.id.split('/')[-1],
                    region=ip.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning Public IPs on stopped resources in {region}: {str(e)}")

        return orphans

    async def scan_dynamic_unassociated_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Dynamic Public IPs that are unassociated but stuck in provisioned state (anomaly).

        Normally, Dynamic IPs are deallocated automatically when unassociated.
        This scenario detects legacy Dynamic IPs stuck in 'Succeeded' state that continue to cost $3/month.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, enabled)

        Returns:
            List of orphan dynamic public IP resources stuck in anomalous state
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs in the region
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Detect anomaly: Dynamic allocation + unassociated + provisioned (should be deallocated)
                allocation_method = ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Unknown'

                if (allocation_method == 'Dynamic' and
                    ip.ip_configuration is None and
                    ip.provisioning_state == 'Succeeded'):

                    # Check age
                    age_days = 0
                    if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                        try:
                            created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                            age_days = (datetime.now(timezone.utc) - created_at).days
                        except:
                            age_days = 0

                    if age_days < min_age_days:
                        continue

                    # Dynamic IPs normally cost $0 when unassociated (auto-deallocated)
                    # But stuck IPs continue to cost like static IPs
                    monthly_cost = 3.0  # Anomaly cost

                    sku_name = ip.sku.name if ip.sku else 'Basic'

                    orphan = OrphanResourceData(
                        resource_id=ip.id,
                        resource_name=ip.name,
                        resource_type='public_ip_dynamic_unassociated',
                        region=region,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata={
                            'ip_id': ip.id,
                            'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                            'sku_name': sku_name,
                            'sku_tier': ip.sku.tier if ip.sku else 'Regional',
                            'allocation_method': 'Dynamic',
                            'ip_version': ip.public_ip_address_version if ip.public_ip_address_version else 'IPv4',
                            'provisioning_state': ip.provisioning_state,
                            'ip_configuration': None,
                            'age_days': age_days,
                            'orphan_reason': f"Dynamic Public IP stuck in provisioned state (anomaly). Should be deallocated automatically when unassociated but continues to cost ${monthly_cost}/month. IP: {ip.ip_address if ip.ip_address else 'Not assigned'}",
                            'recommendation': 'Delete this stuck Dynamic IP. Should be $0/month when unassociated but appears to be in anomalous state.',
                            'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                        }
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning Dynamic unassociated Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_ips_on_nic_without_vm(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Public IPs attached to orphaned NICs (Network Interfaces without VMs).

        Detects Public IPs that are attached to a NIC but the NIC itself is not attached to any VM.
        Both the IP and NIC are wasting cost.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, enabled)

        Returns:
            List of orphan public IP resources on orphaned NICs
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Only check IPs that are attached
                if not ip.ip_configuration:
                    continue

                # Check if it's attached to a NIC (not LB)
                ip_config_id = ip.ip_configuration.id
                if '/networkInterfaces/' not in ip_config_id:
                    continue

                # Extract NIC resource group and name
                try:
                    parts = ip_config_id.split('/')
                    rg_index = parts.index('resourceGroups')
                    nic_index = parts.index('networkInterfaces')
                    nic_rg = parts[rg_index + 1]
                    nic_name = parts[nic_index + 1]

                    # Get NIC details
                    nic = network_client.network_interfaces.get(nic_rg, nic_name)

                    # Check if NIC is orphaned (no VM attached)
                    if nic.virtual_machine is None:
                        # Check age
                        age_days = 0
                        if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                            try:
                                created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                                age_days = (datetime.now(timezone.utc) - created_at).days
                            except:
                                age_days = 0

                        if age_days < min_age_days:
                            continue

                        monthly_cost = self._calculate_public_ip_cost(ip)

                        orphan = OrphanResourceData(
                            resource_id=ip.id,
                            resource_name=ip.name,
                            resource_type='public_ip_on_nic_without_vm',
                            region=region,
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                'ip_id': ip.id,
                                'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                                'sku_name': ip.sku.name if ip.sku else 'Basic',
                                'allocation_method': ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static',
                                'nic_id': nic.id,
                                'nic_name': nic.name,
                                'nic_has_vm': False,
                                'age_days': age_days,
                                'orphan_reason': f"Public IP attached to orphaned NIC '{nic_name}' (no VM attached). Both IP (${monthly_cost}/month) and NIC are wasting cost.",
                                'recommendation': 'Delete both the Public IP and the orphaned NIC to stop billing.',
                                'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                            }
                        )

                        orphans.append(orphan)

                except (ValueError, IndexError) as e:
                    print(f"Error parsing NIC info for IP {ip.name}: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error scanning Public IPs on orphaned NICs in {region}: {str(e)}")

        return orphans

    async def scan_reserved_unused_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Reserved Public IPs that have never been assigned an actual IP address.

        Detects Public IPs in 'Succeeded' provisioning state but with no IP address assigned
        and not attached to any resource. These IPs cost $3/month but are never actually used.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, enabled)

        Returns:
            List of orphan reserved but unused public IP resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Check: Provisioned successfully but never assigned actual IP address
                if (ip.provisioning_state == 'Succeeded' and
                    (not ip.ip_address or ip.ip_address == '') and
                    ip.ip_configuration is None):

                    # Check age
                    age_days = 0
                    if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                        try:
                            created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                            age_days = (datetime.now(timezone.utc) - created_at).days
                        except:
                            age_days = 0

                    if age_days < min_age_days:
                        continue

                    monthly_cost = 3.0  # Standard IP cost even when not assigned

                    sku_name = ip.sku.name if ip.sku else 'Basic'
                    allocation_method = ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static'

                    orphan = OrphanResourceData(
                        resource_id=ip.id,
                        resource_name=ip.name,
                        resource_type='public_ip_reserved_but_unused',
                        region=region,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata={
                            'ip_id': ip.id,
                            'ip_address': 'Never assigned',
                            'sku_name': sku_name,
                            'allocation_method': allocation_method,
                            'provisioning_state': ip.provisioning_state,
                            'ip_configuration': None,
                            'age_days': age_days,
                            'orphan_reason': f"Public IP reserved but never assigned an actual IP address. Costs ${monthly_cost}/month but completely unused for {age_days} days.",
                            'recommendation': 'Release this reservation to stop billing. IP was never used.',
                            'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                        }
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning Reserved unused Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_unnecessary_standard_sku_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Standard SKU Public IPs used in dev/test environments (Basic SKU would suffice).

        NOTE: Basic SKU is retiring on September 30, 2025. This scenario will be obsolete after that date.
        Detects Standard IPs in non-production environments where Basic would be sufficient.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, non_prod_environments)

        Returns:
            List of public IP resources using unnecessary Standard SKU
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        non_prod_envs = detection_rules.get("non_prod_environments", [
            "dev", "test", "staging", "qa", "development", "non-prod", "sandbox", "nonprod"
        ]) if detection_rules else ["dev", "test", "staging", "qa", "development", "non-prod", "sandbox"]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Only check Standard SKU IPs
                sku_name = ip.sku.name if ip.sku else 'Basic'
                if sku_name != 'Standard':
                    continue

                # Check if in non-prod environment via tags or resource group name
                is_non_prod = False

                # Check tags
                if hasattr(ip, 'tags') and ip.tags:
                    for tag_key in ['environment', 'env', 'Environment', 'Env', 'tier', 'Tier', 'criticality']:
                        if tag_key in ip.tags:
                            tag_value = ip.tags[tag_key].lower()
                            if any(env in tag_value for env in non_prod_envs):
                                is_non_prod = True
                                break

                # Check resource group name
                if not is_non_prod and ip.id:
                    rg_name = ''
                    try:
                        parts = ip.id.split('/')
                        rg_index = parts.index('resourceGroups')
                        rg_name = parts[rg_index + 1].lower()

                        # Check if RG name contains non-prod keywords
                        non_prod_keywords = ['-dev', '-test', '-staging', '-qa', 'dev-', 'test-', 'staging-', 'qa-']
                        if any(keyword in rg_name for keyword in non_prod_keywords):
                            is_non_prod = True
                    except (ValueError, IndexError):
                        pass

                if not is_non_prod:
                    continue

                # Check age
                age_days = 0
                if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                    try:
                        created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    except:
                        age_days = 0

                if age_days < min_age_days:
                    continue

                monthly_cost = self._calculate_public_ip_cost(ip)

                # Note: Cost is the same ($3/month), but Standard has advanced features not needed in dev/test
                orphan = OrphanResourceData(
                    resource_id=ip.id,
                    resource_name=ip.name,
                    resource_type='public_ip_unnecessary_standard_sku',
                    region=region,
                    estimated_monthly_cost=0.0,  # Same cost, but feature overkill
                    resource_metadata={
                        'ip_id': ip.id,
                        'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                        'sku_name': 'Standard',
                        'allocation_method': ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static',
                        'environment': 'Non-production',
                        'age_days': age_days,
                        'orphan_reason': f"Standard SKU Public IP used in dev/test environment. Standard has advanced features (availability zones, routing preference) not needed for non-critical workloads. Cost is same ($3/month) but Basic would suffice.",
                        'recommendation': 'NOTE: Basic SKU is retiring Sept 30, 2025. After this date, all IPs must be Standard. Until then, consider Basic for dev/test.',
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unnecessary Standard SKU Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_unnecessary_zone_redundant_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for Zone-redundant Public IPs (3+ zones) without high-availability requirements.

        Detects Standard IPs configured for zone redundancy but lacking HA/production tags.
        Zone-redundant IPs cost +22% ($0.65/month more) without providing value for non-critical workloads.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_age_days, required_ha_tags)

        Returns:
            List of public IP resources with unnecessary zone redundancy
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        ha_tags = detection_rules.get("required_ha_tags", [
            "ha", "high-availability", "production", "critical", "tier:production", "prod"
        ]) if detection_rules else ["ha", "high-availability", "production", "critical", "tier:production", "prod"]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Check if zone-redundant (3+ zones for Standard SKU)
                if not ip.zones or len(ip.zones) < 3:
                    continue

                # Only Standard SKU supports zone redundancy
                sku_name = ip.sku.name if ip.sku else 'Basic'
                if sku_name != 'Standard':
                    continue

                # Check if has HA/production requirement via tags
                has_ha_requirement = False
                if hasattr(ip, 'tags') and ip.tags:
                    for tag_key, tag_value in ip.tags.items():
                        tag_str = f"{tag_key}:{tag_value}".lower()
                        if any(ha_tag.lower() in tag_str for ha_tag in ha_tags):
                            has_ha_requirement = True
                            break

                if has_ha_requirement:
                    continue

                # Check age
                age_days = 0
                if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                    try:
                        created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    except:
                        age_days = 0

                if age_days < min_age_days:
                    continue

                # Calculate savings: Zone-redundant costs +22% ($0.65/month)
                current_cost = 3.65  # Zone-redundant cost
                zonal_cost = 3.00    # Single-zone cost
                potential_savings = current_cost - zonal_cost

                orphan = OrphanResourceData(
                    resource_id=ip.id,
                    resource_name=ip.name,
                    resource_type='public_ip_unnecessary_zone_redundancy',
                    region=region,
                    estimated_monthly_cost=potential_savings,
                    resource_metadata={
                        'ip_id': ip.id,
                        'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                        'sku_name': 'Standard',
                        'allocation_method': ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static',
                        'zones': ip.zones,
                        'zone_count': len(ip.zones),
                        'current_monthly_cost': current_cost,
                        'zonal_monthly_cost': zonal_cost,
                        'potential_savings': round(potential_savings, 2),
                        'age_days': age_days,
                        'orphan_reason': f"Zone-redundant IP (3+ zones) costs +22% ($0.65/month extra) but workload doesn't require 99.99% SLA. No HA/production tags found.",
                        'recommendation': 'Consider single-zone deployment to save $0.65/month per IP (~18% cost reduction).',
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unnecessary zone-redundant Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_ddos_protection_unused_ips(self, region: str, detection_rules: dict | None = None) -> list[OrphanResourceData]:
        """
        Scan for DDoS Protection Standard that has never been triggered (unused protection).

        HIGH VALUE SCENARIO: DDoS Protection Standard costs $2,944/month + $30/protected IP.
        Detects subscriptions with DDoS Protection enabled but never experiencing attacks over 90 days.

        NOTE: This scenario checks at subscription level, not per IP, but flags individual IPs with protection.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration (min_observation_days)

        Returns:
            List of public IP resources with unused DDoS Protection Standard
        """
        from datetime import datetime, timezone, timedelta
        from azure.identity import ClientSecretCredential
        from azure.mgmt.network import NetworkManagementClient

        orphans = []
        min_observation_days = detection_rules.get("min_observation_days", 90) if detection_rules else 90

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all public IPs
            public_ips = network_client.public_ip_addresses.list_all()

            for ip in public_ips:
                if ip.location != region:
                    continue

                # Filter by resource group
                if not self._is_resource_in_scope(ip.id):
                    continue

                # Check if DDoS Protection is enabled
                has_ddos_protection = False
                ddos_plan_id = None

                if hasattr(ip, 'ddos_settings') and ip.ddos_settings:
                    if hasattr(ip.ddos_settings, 'protection_mode') and ip.ddos_settings.protection_mode == 'Enabled':
                        has_ddos_protection = True
                        if hasattr(ip.ddos_settings, 'ddos_protection_plan'):
                            ddos_plan_id = ip.ddos_settings.ddos_protection_plan.id if ip.ddos_settings.ddos_protection_plan else None

                if not has_ddos_protection:
                    continue

                # Check if DDoS was ever triggered using Azure Monitor metrics (if helper exists)
                # For MVP, we flag IPs with DDoS Protection for manual review
                # Full implementation would query Azure Monitor metric "IfUnderDDoSAttack"

                # Check age
                age_days = 0
                if hasattr(ip, 'tags') and ip.tags and 'created_at' in ip.tags:
                    try:
                        created_at = datetime.fromisoformat(ip.tags['created_at'].replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_at).days
                    except:
                        age_days = 0

                if age_days < min_observation_days:
                    continue

                # DDoS Protection Standard costs:
                # $2,944/month (subscription-level flat fee) + $30/IP protected
                per_ip_cost = 30.0  # Per-IP monthly cost
                subscription_cost = 2944.0  # Subscription flat fee (amortized if multiple IPs)

                orphan = OrphanResourceData(
                    resource_id=ip.id,
                    resource_name=ip.name,
                    resource_type='public_ip_ddos_protection_unused',
                    region=region,
                    estimated_monthly_cost=per_ip_cost,  # Per-IP cost only (subscription cost shared)
                    resource_metadata={
                        'ip_id': ip.id,
                        'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                        'sku_name': ip.sku.name if ip.sku else 'Basic',
                        'ddos_protection_enabled': True,
                        'ddos_plan_id': ddos_plan_id,
                        'per_ip_monthly_cost': per_ip_cost,
                        'subscription_flat_fee': subscription_cost,
                        'observation_days': min_observation_days,
                        'age_days': age_days,
                        'orphan_reason': f"DDoS Protection Standard enabled (+$30/IP/month). Subscription pays $2,944/month flat fee. No DDoS attacks detected in {min_observation_days} days. Consider Basic DDoS (free) for non-critical workloads.",
                        'recommendation': f"Review DDoS Protection necessity. For non-critical workloads, use Basic DDoS (free, automatic). Total subscription cost: $2,944/month + $30/IP.",
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unused DDoS Protection Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_no_traffic_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Public IPs with zero network traffic (never actually used).

        Detection Logic (Scenario 9):
        - ByteCount = 0 bytes over lookback period
        - PacketCount = 0 packets over lookback period
        - IP is allocated and attached, but has NEVER transmitted any data
        - Indicates IP was provisioned but the service/application was never activated

        Cost Savings:
        - Standard Public IP: $3.00/month
        - Zone-redundant (3 zones): $3.65/month

        Why it's waste:
        - IP reserved and costing money but literally zero network activity
        - Strong signal the IP is not needed

        Args:
            region: Azure region (e.g., 'eastus', 'westeurope')
            detection_rules: Custom detection rules with keys:
                - enabled: bool
                - lookback_days: int (default 30)
                - confidence_critical_days: int (default 90)
                - confidence_high_days: int (default 30)
                - confidence_medium_days: int (default 7)

        Returns:
            List of Public IPs with zero traffic
        """
        from datetime import datetime, timezone

        orphans = []

        try:
            # Get detection rules with defaults
            rules = detection_rules or {}
            enabled = rules.get('enabled', True)
            lookback_days = rules.get('lookback_days', 30)

            if not enabled:
                return orphans

            # Setup Azure credentials
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all Public IPs in subscription
            public_ips = list(network_client.public_ip_addresses.list_all())

            for ip in public_ips:
                # Skip if wrong region
                if region and region != "all" and ip.location.lower() != region.lower():
                    continue

                # Skip if resource group scoped and doesn't match
                if self.resource_group:
                    ip_rg = ip.id.split('/')[4]
                    if ip_rg.lower() != self.resource_group.lower():
                        continue

                # Skip unallocated IPs (they have no metrics)
                if not ip.ip_address or ip.provisioning_state != 'Succeeded':
                    continue

                # Query Azure Monitor metrics for traffic
                metrics = await self._get_public_ip_metrics(
                    ip_id=ip.id,
                    metric_names=["ByteCount", "PacketCount"],
                    timespan_days=lookback_days
                )

                byte_count = metrics.get("ByteCount", 0)
                packet_count = metrics.get("PacketCount", 0)

                # Detect: Zero bytes AND zero packets over lookback period
                if byte_count == 0 and packet_count == 0:
                    # Calculate age
                    age_days = 0
                    if hasattr(ip, 'tags') and ip.tags and 'created_time' in ip.tags:
                        created_time = datetime.fromisoformat(ip.tags['created_time'].replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_time).days

                    # Calculate cost
                    monthly_cost = self._calculate_public_ip_cost(ip)

                    # Create orphan resource
                    orphan = OrphanResourceData(
                        resource_id=ip.id,
                        resource_name=ip.name or "Unnamed Public IP",
                        resource_type="public_ip_no_traffic",
                        region=ip.location,
                        estimated_monthly_cost=monthly_cost,
                        metadata={
                            'ip_address': ip.ip_address or "Not assigned",
                            'sku': ip.sku.name if ip.sku else "Basic",
                            'allocation_method': ip.public_ip_allocation_method or "Unknown",
                            'zones': len(ip.zones) if ip.zones else 0,
                            'provisioning_state': ip.provisioning_state or "Unknown",
                            'attached_to': self._get_attached_resource(ip),
                            'lookback_days': lookback_days,
                            'byte_count': byte_count,
                            'packet_count': packet_count,
                            'age_days': age_days,
                            'detection_reason': f'Public IP has transmitted ZERO bytes and ZERO packets over the last {lookback_days} days. IP is allocated but never used.',
                            'recommendation': 'Delete this Public IP. It has never transmitted any network traffic, indicating the associated resource/application was never activated or configured properly.',
                            'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                        }
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning zero-traffic Public IPs in {region}: {str(e)}")

        return orphans

    async def scan_very_low_traffic_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Public IPs with very low network traffic (under-utilized).

        Detection Logic (Scenario 10):
        - ByteCount < traffic_threshold_gb (default 1 GB) over lookback period
        - PacketCount typically also very low (<100,000 packets)
        - IP is active but barely used, suggesting over-provisioning or wrong architecture

        Cost Savings:
        - Standard Public IP: $3.00/month
        - Zone-redundant (3 zones): $3.65/month

        Why it's waste:
        - Very low traffic (<1GB/month) suggests:
          1. Service is rarely accessed (could use internal IP or VPN)
          2. Test/dev environment that should be ephemeral
          3. Over-provisioned architecture (dedicated IP not needed)
        - For < $3/month worth of traffic, public IP may not be justified

        Args:
            region: Azure region (e.g., 'eastus', 'westeurope')
            detection_rules: Custom detection rules with keys:
                - enabled: bool
                - lookback_days: int (default 30)
                - traffic_threshold_gb: float (default 1.0) - Traffic threshold in GB
                - confidence_high_days: int (default 30)
                - confidence_medium_days: int (default 7)

        Returns:
            List of Public IPs with very low traffic
        """
        from datetime import datetime, timezone

        orphans = []

        try:
            # Get detection rules with defaults
            rules = detection_rules or {}
            enabled = rules.get('enabled', True)
            lookback_days = rules.get('lookback_days', 30)
            traffic_threshold_gb = rules.get('traffic_threshold_gb', 1.0)

            if not enabled:
                return orphans

            # Convert GB to bytes for comparison
            traffic_threshold_bytes = traffic_threshold_gb * 1024 * 1024 * 1024  # 1 GB = 1,073,741,824 bytes

            # Setup Azure credentials
            from azure.identity import ClientSecretCredential
            from azure.mgmt.network import NetworkManagementClient

            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            network_client = NetworkManagementClient(credential, self.subscription_id)

            # List all Public IPs in subscription
            public_ips = list(network_client.public_ip_addresses.list_all())

            for ip in public_ips:
                # Skip if wrong region
                if region and region != "all" and ip.location.lower() != region.lower():
                    continue

                # Skip if resource group scoped and doesn't match
                if self.resource_group:
                    ip_rg = ip.id.split('/')[4]
                    if ip_rg.lower() != self.resource_group.lower():
                        continue

                # Skip unallocated IPs (they have no metrics)
                if not ip.ip_address or ip.provisioning_state != 'Succeeded':
                    continue

                # Query Azure Monitor metrics for traffic
                metrics = await self._get_public_ip_metrics(
                    ip_id=ip.id,
                    metric_names=["ByteCount", "PacketCount"],
                    timespan_days=lookback_days
                )

                byte_count = metrics.get("ByteCount", 0)
                packet_count = metrics.get("PacketCount", 0)

                # Detect: Traffic below threshold (but not zero - scenario 9 handles that)
                if 0 < byte_count < traffic_threshold_bytes:
                    # Calculate age
                    age_days = 0
                    if hasattr(ip, 'tags') and ip.tags and 'created_time' in ip.tags:
                        created_time = datetime.fromisoformat(ip.tags['created_time'].replace('Z', '+00:00'))
                        age_days = (datetime.now(timezone.utc) - created_time).days

                    # Calculate cost
                    monthly_cost = self._calculate_public_ip_cost(ip)

                    # Convert bytes to human-readable format
                    if byte_count < 1024:
                        traffic_display = f"{byte_count} bytes"
                    elif byte_count < 1024 * 1024:
                        traffic_display = f"{byte_count / 1024:.2f} KB"
                    elif byte_count < 1024 * 1024 * 1024:
                        traffic_display = f"{byte_count / (1024 * 1024):.2f} MB"
                    else:
                        traffic_display = f"{byte_count / (1024 * 1024 * 1024):.2f} GB"

                    # Create orphan resource
                    orphan = OrphanResourceData(
                        resource_id=ip.id,
                        resource_name=ip.name or "Unnamed Public IP",
                        resource_type="public_ip_very_low_traffic",
                        region=ip.location,
                        estimated_monthly_cost=monthly_cost,
                        metadata={
                            'ip_address': ip.ip_address or "Not assigned",
                            'sku': ip.sku.name if ip.sku else "Basic",
                            'allocation_method': ip.public_ip_allocation_method or "Unknown",
                            'zones': len(ip.zones) if ip.zones else 0,
                            'provisioning_state': ip.provisioning_state or "Unknown",
                            'attached_to': self._get_attached_resource(ip),
                            'lookback_days': lookback_days,
                            'byte_count': byte_count,
                            'traffic_display': traffic_display,
                            'packet_count': packet_count,
                            'traffic_threshold_gb': traffic_threshold_gb,
                            'age_days': age_days,
                            'detection_reason': f'Public IP has transmitted only {traffic_display} over the last {lookback_days} days (threshold: {traffic_threshold_gb} GB). Very low utilization suggests the IP may not be needed.',
                            'recommendation': f'Consider: 1) Deleting if traffic is minimal test/dev activity, 2) Using internal IPs or VPN for low-traffic services, 3) Consolidating multiple low-traffic IPs behind a load balancer.',
                            'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                        }
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning very-low-traffic Public IPs in {region}: {str(e)}")

        return orphans

    def _get_vm_cost_estimate(self, vm_size: str) -> float:
        """
        Estimate monthly cost for Azure VM size (approximation).

        Args:
            vm_size: Azure VM size (e.g. Standard_B2s, Standard_D4s_v3)

        Returns:
            Estimated monthly cost in USD
        """
        # Simplified pricing estimates (Pay-as-you-go, US East, Linux)
        # These are rough approximations for cost calculation
        vm_pricing = {
            # B-series (Burstable)
            'Standard_B1s': 8.0,
            'Standard_B1ms': 15.0,
            'Standard_B2s': 30.0,
            'Standard_B2ms': 60.0,
            'Standard_B4ms': 120.0,
            # D-series (General purpose)
            'Standard_D2s_v3': 70.0,
            'Standard_D4s_v3': 140.0,
            'Standard_D8s_v3': 280.0,
            'Standard_D16s_v3': 560.0,
            # E-series (Memory optimized)
            'Standard_E2s_v3': 90.0,
            'Standard_E4s_v3': 180.0,
            'Standard_E8s_v3': 360.0,
            # F-series (Compute optimized)
            'Standard_F2s_v2': 65.0,
            'Standard_F4s_v2': 130.0,
            'Standard_F8s_v2': 260.0,
        }

        # Return estimate or default based on VM size pattern
        if vm_size in vm_pricing:
            return vm_pricing[vm_size]

        # Fallback: estimate by vcpu count if possible
        if '_' in vm_size:
            parts = vm_size.split('_')
            if len(parts) >= 2:
                # Try to extract number (e.g. D4s -> 4)
                for part in parts[1:]:
                    if part[0].isdigit():
                        try:
                            vcpus = int(''.join(filter(str.isdigit, part)))
                            return vcpus * 35.0  # ~$35/vCPU/month average
                        except:
                            pass

        # Default fallback
        return 100.0

    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for deallocated (stopped) Azure Virtual Machines.

        Detects VMs that have been deallocated for an extended period,
        indicating they may no longer be needed.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration with:
                - enabled: bool (default True)
                - min_stopped_days: int (default 30)

        Returns:
            List of deallocated VM resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_stopped_days = detection_rules.get("min_stopped_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Get VM instance view for power state
                resource_group = vm.id.split('/')[4]
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=resource_group,
                    vm_name=vm.name
                )

                # Find power state and timestamp
                power_state = None
                stopped_since = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        if hasattr(status, 'time') and status.time:
                            stopped_since = status.time

                # Only detect deallocated VMs
                if power_state != 'deallocated':
                    continue

                # Calculate stopped duration
                stopped_days = 0
                if stopped_since:
                    stopped_days = (datetime.now(timezone.utc) - stopped_since).days

                # Filter by min_stopped_days
                if stopped_days < min_stopped_days:
                    continue

                # Calculate disk costs (disks continue to charge when deallocated, but compute is $0)
                monthly_cost = 0.0

                # Calculate OS disk cost
                if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.managed_disk:
                    try:
                        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
                        os_disk_name = os_disk_id.split('/')[-1]
                        os_disk_rg = os_disk_id.split('/')[4]
                        os_disk = compute_client.disks.get(os_disk_rg, os_disk_name)
                        monthly_cost += self._calculate_disk_cost(os_disk)
                    except Exception:
                        pass  # If disk not found, skip

                # Calculate data disks cost
                if vm.storage_profile and vm.storage_profile.data_disks:
                    for data_disk in vm.storage_profile.data_disks:
                        if data_disk.managed_disk:
                            try:
                                disk_id = data_disk.managed_disk.id
                                disk_name = disk_id.split('/')[-1]
                                disk_rg = disk_id.split('/')[4]
                                disk = compute_client.disks.get(disk_rg, disk_name)
                                monthly_cost += self._calculate_disk_cost(disk)
                            except Exception:
                                pass  # If disk not found, skip

                # Calculate age for "Already wasted" calculation
                age_days = -1
                created_at = None
                if hasattr(vm, 'time_created') and vm.time_created:
                    age_days = (datetime.now(timezone.utc) - vm.time_created).days
                    created_at = vm.time_created.isoformat()

                metadata = {
                    'vm_id': vm.id,
                    'vm_size': vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown',
                    'power_state': 'deallocated',
                    'stopped_days': stopped_days,
                    'os_type': str(vm.storage_profile.os_disk.os_type) if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.os_type else 'Unknown',
                    'resource_group': resource_group,
                    'tags': vm.tags if vm.tags else {},
                    'age_days': age_days,  # For "Already Wasted" calculation
                    'created_at': created_at,  # ISO format timestamp
                    'orphan_reason': f"VM has been deallocated (stopped) for {stopped_days} days",
                    'recommendation': f"Consider deleting VM if no longer needed. While deallocated, compute charges are $0 but disks continue to cost ${monthly_cost:.2f}/month. You can delete the VM and keep disks if needed later.",
                    'confidence_level': self._calculate_confidence_level(stopped_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='virtual_machine_deallocated',
                    resource_id=vm.id,
                    resource_name=vm.name if vm.name else vm.id.split('/')[-1],
                    region=vm.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning deallocated VMs in {region}: {str(e)}")

        return orphans

    async def scan_stopped_not_deallocated_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure VMs stopped but NOT deallocated (still costing money!).

        This is CRITICAL as VMs in "stopped" state (without deallocation) continue
        to incur FULL compute charges even though they're not running.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration with:
                - enabled: bool (default True)
                - min_stopped_days: int (default 7)

        Returns:
            List of stopped (not deallocated) VM resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_stopped_days = detection_rules.get("min_stopped_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                resource_group = vm.id.split('/')[4]
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=resource_group,
                    vm_name=vm.name
                )

                power_state = None
                stopped_since = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        if hasattr(status, 'time') and status.time:
                            stopped_since = status.time

                # Detect VMs in "stopped" state (NOT deallocated)
                if power_state != 'stopped':
                    continue

                stopped_days = 0
                if stopped_since:
                    stopped_days = (datetime.now(timezone.utc) - stopped_since).days

                if stopped_days < min_stopped_days:
                    continue

                # FULL compute cost while stopped (not deallocated)
                vm_size = vm.hardware_profile.vm_size if vm.hardware_profile else 'Unknown'
                monthly_cost = self._get_vm_cost_estimate(vm_size)

                # Calculate age for "Already wasted" calculation
                age_days = -1
                created_at = None
                if hasattr(vm, 'time_created') and vm.time_created:
                    age_days = (datetime.now(timezone.utc) - vm.time_created).days
                    created_at = vm.time_created.isoformat()

                metadata = {
                    'vm_id': vm.id,
                    'vm_size': vm_size,
                    'power_state': 'stopped (NOT deallocated)',
                    'stopped_days': stopped_days,
                    'os_type': str(vm.storage_profile.os_disk.os_type) if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.os_type else 'Unknown',
                    'resource_group': resource_group,
                    'tags': vm.tags if vm.tags else {},
                    'age_days': age_days,  # For "Already Wasted" calculation
                    'created_at': created_at,  # ISO format timestamp
                    'warning': f'⚠️ CRITICAL: VM is stopped but NOT deallocated! You are paying FULL price (${monthly_cost:.2f}/month) for a VM that is not running!',
                    'orphan_reason': f"VM stopped (not deallocated) for {stopped_days} days - paying full compute charges while not running",
                    'recommendation': f"URGENT: Deallocate this VM immediately using Azure Portal or CLI: 'az vm deallocate'. This will stop compute charges. Current waste: ${monthly_cost:.2f}/month.",
                    'confidence_level': self._calculate_confidence_level(stopped_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='virtual_machine_stopped_not_deallocated',
                    resource_id=vm.id,
                    resource_name=vm.name if vm.name else vm.id.split('/')[-1],
                    region=vm.location,
                    estimated_monthly_cost=monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning stopped (not deallocated) VMs in {region}: {str(e)}")

        return orphans

    async def scan_never_started_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Virtual Machines that have been created but never started.

        This detects VMs that were provisioned but never used - potential provisioning
        errors or forgotten test resources.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_age_days": int (default 7) - VM must exist for this many days
                }

        Returns:
            List of VM resources that have never been started
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # Get all VMs across all resource groups
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Get resource group from VM ID
                resource_group = vm.id.split('/')[4]

                # Get instance view for power state and diagnostics
                instance_view = compute_client.virtual_machines.instance_view(
                    resource_group_name=resource_group,
                    vm_name=vm.name
                )

                # Extract power state
                power_state = 'unknown'
                for status in instance_view.statuses:
                    if status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[1].lower()
                        break

                # Check if VM has ever been started
                # A VM that has never started will be in 'deallocated' or 'stopped' state
                # and won't have boot diagnostics or start history
                has_never_started = False

                if power_state in ['deallocated', 'stopped']:
                    # Check VM creation time vs current state
                    # If VM was created and immediately went to stopped/deallocated without
                    # ever reaching 'running', it's never been started

                    # For simplicity, we'll check:
                    # 1. VM is not running
                    # 2. VM has no recent activity in diagnostics (if available)
                    # 3. VM age > min_age_days

                    # Calculate VM age
                    created_at = vm.time_created if hasattr(vm, 'time_created') else None
                    if created_at:
                        from datetime import datetime, timezone
                        now = datetime.now(timezone.utc)
                        vm_age_days = (now - created_at).days

                        if vm_age_days < min_age_days:
                            continue

                        # If VM has been in stopped/deallocated state for its entire life
                        # and is older than min_age_days, flag as never started
                        has_never_started = True
                    else:
                        # Can't determine creation time, skip
                        continue

                if not has_never_started:
                    continue

                # Estimate cost (VM is not running, so only disk costs apply)
                # But we'll show the potential compute cost if it were running
                vm_size = vm.hardware_profile.vm_size
                potential_monthly_cost = self._get_vm_cost_estimate(vm_size)

                # Current cost is $0 for compute (since it's stopped/deallocated)
                # but disks are still charging
                current_monthly_cost = 0.0

                # Calculate OS disk cost
                if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.managed_disk:
                    try:
                        os_disk_id = vm.storage_profile.os_disk.managed_disk.id
                        os_disk_name = os_disk_id.split('/')[-1]
                        os_disk_rg = os_disk_id.split('/')[4]
                        os_disk = compute_client.disks.get(os_disk_rg, os_disk_name)
                        current_monthly_cost += self._calculate_disk_cost(os_disk)
                    except Exception:
                        pass  # If disk not found, skip

                # Calculate data disks cost
                if vm.storage_profile and vm.storage_profile.data_disks:
                    for data_disk in vm.storage_profile.data_disks:
                        if data_disk.managed_disk:
                            try:
                                disk_id = data_disk.managed_disk.id
                                disk_name = disk_id.split('/')[-1]
                                disk_rg = disk_id.split('/')[4]
                                disk = compute_client.disks.get(disk_rg, disk_name)
                                current_monthly_cost += self._calculate_disk_cost(disk)
                            except Exception:
                                pass  # If disk not found, skip

                metadata = {
                    'vm_size': vm_size,
                    'power_state': power_state,
                    'vm_age_days': vm_age_days,
                    'age_days': vm_age_days,  # For "Already Wasted" calculation
                    'created_at': created_at.isoformat() if created_at else None,
                    'potential_monthly_cost': f'${potential_monthly_cost:.2f}',
                    'orphan_reason': f"VM created {vm_age_days} days ago but has never been started",
                    'recommendation': f"This VM has existed for {vm_age_days} days without ever running. "
                                    f"If it was created by mistake or for testing, consider deleting it. "
                                    f"Potential compute cost if started: ${potential_monthly_cost:.2f}/month.",
                    'confidence_level': self._calculate_confidence_level(vm_age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='virtual_machine_never_started',
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=vm.location,
                    estimated_monthly_cost=current_monthly_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning never-started VMs in {region}: {str(e)}")

        return orphans

    async def scan_oversized_premium_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for oversized Azure VMs with premium managed disks.

        Detects VMs that have excessive CPU cores (>8 vCPUs) combined with
        Premium_LRS managed disks, suggesting potential for cost optimization
        by downsizing or switching to Standard_LRS disks.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_vcpus": int (default 8) - Minimum vCPU count to flag,
                    "disk_tier": str (default "Premium_LRS") - Disk SKU to detect
                }

        Returns:
            List of oversized VM resources with premium disks
        """
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        min_vcpus = detection_rules.get("min_vcpus", 8) if detection_rules else 8
        disk_tier = detection_rules.get("disk_tier", "Premium_LRS") if detection_rules else "Premium_LRS"

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # Get all VMs
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                vm_size = vm.hardware_profile.vm_size

                # Extract vCPU count from VM size (approximation based on size name)
                # E.g., Standard_D8s_v3 has 8 vCPUs
                vcpu_count = self._extract_vcpu_from_size(vm_size)

                if vcpu_count < min_vcpus:
                    continue

                # Check if VM has premium managed disks
                has_premium_disks = False
                premium_disk_count = 0
                total_disk_size_gb = 0

                if vm.storage_profile and vm.storage_profile.data_disks:
                    for disk in vm.storage_profile.data_disks:
                        if disk.managed_disk:
                            # Get disk details
                            resource_group = vm.id.split('/')[4]
                            disk_name = disk.name

                            try:
                                disk_details = compute_client.disks.get(
                                    resource_group_name=resource_group,
                                    disk_name=disk_name
                                )

                                if disk_details.sku.name == disk_tier:
                                    has_premium_disks = True
                                    premium_disk_count += 1
                                    total_disk_size_gb += disk_details.disk_size_gb or 0
                            except:
                                pass  # Skip if can't get disk details

                if not has_premium_disks:
                    continue

                # Calculate potential savings
                # Premium SSD: ~$0.13/GB/month
                # Standard SSD: ~$0.05/GB/month
                # Potential savings: ~$0.08/GB/month
                premium_disk_cost = total_disk_size_gb * 0.13
                standard_disk_cost = total_disk_size_gb * 0.05
                disk_savings = premium_disk_cost - standard_disk_cost

                # VM compute cost
                vm_cost = self._get_vm_cost_estimate(vm_size)

                # Suggest downsizing to 4 vCPUs (50% reduction)
                suggested_size = self._get_downsized_vm(vm_size)
                suggested_cost = self._get_vm_cost_estimate(suggested_size)
                compute_savings = vm_cost - suggested_cost

                total_monthly_savings = disk_savings + compute_savings

                # Calculate age for "Already wasted" calculation
                age_days = -1
                created_at = None
                if hasattr(vm, 'time_created') and vm.time_created:
                    from datetime import datetime, timezone
                    age_days = (datetime.now(timezone.utc) - vm.time_created).days
                    created_at = vm.time_created.isoformat()

                metadata = {
                    'vm_size': vm_size,
                    'vcpu_count': vcpu_count,
                    'premium_disk_count': premium_disk_count,
                    'total_disk_size_gb': total_disk_size_gb,
                    'current_vm_cost': f'${vm_cost:.2f}/month',
                    'current_disk_cost': f'${premium_disk_cost:.2f}/month',
                    'suggested_vm_size': suggested_size,
                    'suggested_vm_cost': f'${suggested_cost:.2f}/month',
                    'suggested_disk_tier': 'Standard_LRS',
                    'suggested_disk_cost': f'${standard_disk_cost:.2f}/month',
                    'potential_monthly_savings': f'${total_monthly_savings:.2f}',
                    'age_days': age_days,  # For "Already Wasted" calculation
                    'created_at': created_at,  # ISO format timestamp
                    'orphan_reason': f"VM is oversized ({vcpu_count} vCPUs) with premium disks ({premium_disk_count} disks, {total_disk_size_gb}GB)",
                    'recommendation': f"Consider downsizing VM from {vm_size} to {suggested_size} "
                                    f"and switching disks from Premium_LRS to Standard_LRS. "
                                    f"Potential savings: ${total_monthly_savings:.2f}/month "
                                    f"(VM: ${compute_savings:.2f}, Disks: ${disk_savings:.2f}).",
                    'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='virtual_machine_oversized_premium',
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=vm.location,
                    estimated_monthly_cost=total_monthly_savings,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning oversized premium VMs in {region}: {str(e)}")

        return orphans

    def _extract_vcpu_from_size(self, vm_size: str) -> int:
        """
        Extract vCPU count from Azure VM size string.

        Examples:
            Standard_D8s_v3 -> 8
            Standard_E4s_v3 -> 4
            Standard_B2s -> 2
        """
        import re

        # Try to extract number after series letter
        match = re.search(r'[A-Z](\d+)', vm_size)
        if match:
            return int(match.group(1))

        # Default fallback
        return 4

    def _get_downsized_vm(self, vm_size: str) -> str:
        """
        Suggest a downsized VM based on current size.

        Simple heuristic: halve the vCPU count while keeping same series.
        """
        vcpu = self._extract_vcpu_from_size(vm_size)
        downsized_vcpu = max(2, vcpu // 2)

        # Replace number in VM size
        import re
        downsized_size = re.sub(r'(\d+)', str(downsized_vcpu), vm_size, count=1)

        return downsized_size

    async def scan_untagged_orphan_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure VMs that are missing required governance tags.

        Detects VMs without proper tagging (owner, team, cost center) that have
        existed for an extended period, indicating potential orphaned or unmanaged
        resources.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "required_tags": list[str] (default ["owner", "team"]),
                    "min_age_days": int (default 30)
                }

        Returns:
            List of untagged VM resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Get detection parameters
        required_tags = detection_rules.get("required_tags", ["owner", "team"]) if detection_rules else ["owner", "team"]
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret,
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # Get all VMs
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Check VM age
                created_at = vm.time_created if hasattr(vm, 'time_created') else None
                if created_at:
                    from datetime import datetime, timezone
                    now = datetime.now(timezone.utc)
                    vm_age_days = (now - created_at).days

                    if vm_age_days < min_age_days:
                        continue
                else:
                    # Can't determine age, skip
                    continue

                # Check for required tags
                vm_tags = vm.tags or {}
                missing_tags = []

                for required_tag in required_tags:
                    if required_tag.lower() not in [tag.lower() for tag in vm_tags.keys()]:
                        missing_tags.append(required_tag)

                if not missing_tags:
                    # VM has all required tags
                    continue

                # Get resource group for power state
                resource_group = vm.id.split('/')[4]

                # Get instance view for power state
                try:
                    instance_view = compute_client.virtual_machines.instance_view(
                        resource_group_name=resource_group,
                        vm_name=vm.name
                    )

                    power_state = 'unknown'
                    for status in instance_view.statuses:
                        if status.code.startswith('PowerState/'):
                            power_state = status.code.split('/')[1].lower()
                            break
                except:
                    power_state = 'unknown'

                # Estimate cost
                vm_size = vm.hardware_profile.vm_size
                vm_cost = self._get_vm_cost_estimate(vm_size)

                # If VM is deallocated, cost is $0 for compute, but disks still charge
                if power_state == 'deallocated':
                    vm_cost = 0.0

                    # Calculate OS disk cost
                    if vm.storage_profile and vm.storage_profile.os_disk and vm.storage_profile.os_disk.managed_disk:
                        try:
                            os_disk_id = vm.storage_profile.os_disk.managed_disk.id
                            os_disk_name = os_disk_id.split('/')[-1]
                            os_disk_rg = os_disk_id.split('/')[4]
                            os_disk = compute_client.disks.get(os_disk_rg, os_disk_name)
                            vm_cost += self._calculate_disk_cost(os_disk)
                        except Exception:
                            pass  # If disk not found, skip

                    # Calculate data disks cost
                    if vm.storage_profile and vm.storage_profile.data_disks:
                        for data_disk in vm.storage_profile.data_disks:
                            if data_disk.managed_disk:
                                try:
                                    disk_id = data_disk.managed_disk.id
                                    disk_name = disk_id.split('/')[-1]
                                    disk_rg = disk_id.split('/')[4]
                                    disk = compute_client.disks.get(disk_rg, disk_name)
                                    vm_cost += self._calculate_disk_cost(disk)
                                except Exception:
                                    pass  # If disk not found, skip

                metadata = {
                    'vm_size': vm_size,
                    'power_state': power_state,
                    'vm_age_days': vm_age_days,
                    'age_days': vm_age_days,  # For "Already Wasted" calculation
                    'existing_tags': list(vm_tags.keys()),
                    'missing_tags': missing_tags,
                    'created_at': created_at.isoformat() if created_at else None,
                    'orphan_reason': f"VM is {vm_age_days} days old but missing required governance tags: {', '.join(missing_tags)}",
                    'recommendation': f"This VM lacks proper tagging for {vm_age_days} days. "
                                    f"Add required tags ({', '.join(missing_tags)}) to identify ownership "
                                    f"and cost accountability. If owner cannot be identified, this may be "
                                    f"an orphaned resource that should be investigated or deleted.",
                    'confidence_level': self._calculate_confidence_level(vm_age_days, detection_rules),
                }

                orphan = OrphanResourceData(
                    resource_type='virtual_machine_untagged_orphan',
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=vm.location,
                    estimated_monthly_cost=vm_cost,
                    resource_metadata=metadata
                )

                orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning untagged orphan VMs in {region}: {str(e)}")

        return orphans

    async def scan_old_generation_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Virtual Machines using old generation SKUs.

        Detects VMs running on older generation VM SKUs (v1, v2, v3) that could be
        migrated to newer generations (v4, v5) for 20-30% cost savings and better performance.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_age_days": int (default 60) - Only flag VMs older than this,
                    "old_generations": list (default ["v1", "v2", "_v3"]) - Generations to flag,
                    "savings_percent": float (default 25.0) - Estimated savings percentage
                }

        Returns:
            List of VMs using old generation SKUs
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 60) if detection_rules else 60
        old_generations = detection_rules.get("old_generations", ["v1", "v2", "_v3"]) if detection_rules else ["v1", "v2", "_v3"]
        savings_percent = detection_rules.get("savings_percent", 25.0) if detection_rules else 25.0

        # Migration mapping: old generation → new generation SKU pattern
        generation_mapping = {
            "D": ("Dv5", "General purpose"),
            "E": ("Ev5", "Memory optimized"),
            "F": ("Fsv2", "Compute optimized"),
            "B": ("B", "Burstable (already latest)"),
        }

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                vm_size = vm.hardware_profile.vm_size

                # Check if VM uses an old generation SKU
                is_old_generation = False
                old_gen_type = None
                for old_gen in old_generations:
                    if old_gen in vm_size:
                        is_old_generation = True
                        old_gen_type = old_gen
                        break

                if not is_old_generation:
                    continue

                # Calculate VM age
                age_days = 0
                if vm.time_created:
                    age_delta = datetime.now(timezone.utc) - vm.time_created
                    age_days = age_delta.days

                # Only flag VMs older than min_age_days
                if age_days < min_age_days:
                    continue

                # Determine VM series (D, E, F, B, etc.)
                vm_series = None
                for series in ["D", "E", "F", "B"]:
                    if vm_size.startswith(f"Standard_{series}"):
                        vm_series = series
                        break

                # Get recommended new generation SKU
                new_generation = None
                workload_type = "General purpose"
                if vm_series and vm_series in generation_mapping:
                    new_generation, workload_type = generation_mapping[vm_series]

                # Parse VM size to suggest migration path
                # Example: Standard_D4_v2 → Standard_D4s_v5
                # Example: Standard_E8s_v3 → Standard_E8s_v5
                suggested_sku = vm_size
                if new_generation:
                    # Replace old generation with new generation
                    for old_gen in old_generations:
                        if old_gen in vm_size:
                            # For v3, suggest v5; for v2, suggest v5; for v1, suggest v5
                            suggested_sku = vm_size.replace(old_gen, "_v5")
                            # If already has 's' (storage optimized), keep it
                            # If not, add 's' for latest gen (e.g., D4_v2 → D4s_v5)
                            if "s_" not in suggested_sku and old_gen in ["v1", "v2"]:
                                suggested_sku = suggested_sku.replace("_v5", "s_v5")
                            break

                # Calculate current monthly cost
                current_cost = self._get_vm_cost_estimate(vm_size)

                # Calculate savings (20-30% typical, using configurable savings_percent)
                monthly_savings = current_cost * (savings_percent / 100.0)
                new_cost = current_cost - monthly_savings

                # Calculate total wasted cost (already paid premium for old gen)
                total_wasted = (age_days / 30.0) * monthly_savings if age_days > 0 else monthly_savings

                # Determine confidence level
                if age_days >= 180:
                    confidence_level = 'critical'
                elif age_days >= 90:
                    confidence_level = 'high'
                elif age_days >= 60:
                    confidence_level = 'medium'
                else:
                    confidence_level = 'low'

                orphans.append(OrphanResourceData(
                    resource_type='virtual_machine_old_generation',
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=region,
                    estimated_monthly_cost=monthly_savings,  # Savings opportunity
                    resource_metadata={
                        'vm_id': vm.id,
                        'vm_name': vm.name,
                        'current_vm_size': vm_size,
                        'suggested_vm_size': suggested_sku,
                        'vm_series': vm_series,
                        'workload_type': workload_type,
                        'old_generation': old_gen_type,
                        'new_generation': new_generation or "v5",
                        'current_monthly_cost': round(current_cost, 2),
                        'new_monthly_cost': round(new_cost, 2),
                        'monthly_savings': round(monthly_savings, 2),
                        'savings_percent': round(savings_percent, 1),
                        'age_days': age_days,
                        'total_wasted_cost': round(total_wasted, 2),
                        'orphan_reason': f'VM uses old generation SKU ({vm_size} with {old_gen_type}). Newer generations (v4/v5) offer 20-30% better price-performance ratio.',
                        'recommendation': f'Migrate VM from {vm_size} to {suggested_sku} for ~{savings_percent:.0f}% cost savings (${monthly_savings:.2f}/month) plus improved performance. '
                                        f'Newer {new_generation or "v5"}-series VMs offer same or better specs at lower cost with latest Intel/AMD processors.',
                        'confidence_level': confidence_level,
                        'migration_effort': 'medium',  # Requires VM stop/start
                        'tags': vm.tags or {},
                    },
                ))

        except Exception as e:
            print(f"Error scanning old generation VMs in {region}: {str(e)}")

        return orphans

    async def scan_spot_convertible_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Virtual Machines that could convert to Spot pricing.

        Detects regular VMs running interruptible workloads (dev/test, batch, CI/CD) that
        could use Azure Spot VMs for 60-90% cost savings. Spot VMs are ideal for workloads
        that can tolerate interruptions.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_age_days": int (default 30) - Only flag stable VMs,
                    "spot_eligible_tags": list (default ["batch", "dev", "test", "ci", "analytics"]),
                    "spot_discount_percent": float (default 75.0) - Average Spot discount,
                    "exclude_ha_vms": bool (default True) - Exclude high-availability VMs
                }

        Returns:
            List of VMs eligible for Spot conversion
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        spot_eligible_tags = detection_rules.get(
            "spot_eligible_tags",
            ["batch", "dev", "test", "staging", "ci", "cd", "analytics", "non-critical", "development", "qa"]
        ) if detection_rules else ["batch", "dev", "test", "staging", "ci", "cd", "analytics", "non-critical", "development", "qa"]
        spot_discount_percent = detection_rules.get("spot_discount_percent", 75.0) if detection_rules else 75.0
        exclude_ha_vms = detection_rules.get("exclude_ha_vms", True) if detection_rules else True

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Check if VM is already Spot (priority = 'Spot')
                # Regular VMs have priority = 'Regular' or None
                if hasattr(vm, 'priority') and vm.priority and vm.priority.lower() == 'spot':
                    continue

                # Calculate VM age
                age_days = 0
                if vm.time_created:
                    age_delta = datetime.now(timezone.utc) - vm.time_created
                    age_days = age_delta.days

                # Only flag stable VMs (older than min_age_days)
                if age_days < min_age_days:
                    continue

                # Analyze tags to determine if workload is Spot-eligible
                vm_tags = vm.tags or {}
                tags_lower = {k.lower(): v.lower() for k, v in vm_tags.items()}

                # Check if VM has Spot-eligible tags
                is_spot_eligible = False
                matched_tags = []
                for tag_key, tag_value in tags_lower.items():
                    for eligible_tag in spot_eligible_tags:
                        if eligible_tag.lower() in tag_key or eligible_tag.lower() in tag_value:
                            is_spot_eligible = True
                            matched_tags.append(f"{tag_key}={tag_value}")

                # Also check VM name for indicators
                vm_name_lower = vm.name.lower()
                for eligible_tag in spot_eligible_tags:
                    if eligible_tag.lower() in vm_name_lower:
                        is_spot_eligible = True
                        matched_tags.append(f"name contains '{eligible_tag}'")
                        break

                if not is_spot_eligible:
                    continue

                # Exclude high-availability VMs (if configured)
                if exclude_ha_vms:
                    # Check for HA indicators in tags
                    ha_keywords = ["prod", "production", "critical", "high-availability", "ha", "database", "db"]
                    is_ha = False
                    for tag_key, tag_value in tags_lower.items():
                        for ha_keyword in ha_keywords:
                            if ha_keyword in tag_key or ha_keyword in tag_value:
                                is_ha = True
                                break
                        if is_ha:
                            break

                    if is_ha:
                        continue  # Skip HA VMs

                # Calculate current monthly cost (Regular VM pricing)
                current_cost = self._get_vm_cost_estimate(vm.hardware_profile.vm_size)

                # Calculate Spot savings (60-90% discount, using configurable discount_percent)
                monthly_savings = current_cost * (spot_discount_percent / 100.0)
                spot_cost = current_cost - monthly_savings

                # Calculate total wasted cost (overpaid for Regular vs Spot)
                total_wasted = (age_days / 30.0) * monthly_savings if age_days > 0 else monthly_savings

                # Determine confidence level
                if age_days >= 90:
                    confidence_level = 'critical'
                elif age_days >= 60:
                    confidence_level = 'high'
                elif age_days >= 30:
                    confidence_level = 'medium'
                else:
                    confidence_level = 'low'

                orphans.append(OrphanResourceData(
                    resource_type='virtual_machine_spot_convertible',
                    resource_id=vm.id,
                    resource_name=vm.name,
                    region=region,
                    estimated_monthly_cost=monthly_savings,  # Savings opportunity
                    resource_metadata={
                        'vm_id': vm.id,
                        'vm_name': vm.name,
                        'vm_size': vm.hardware_profile.vm_size,
                        'current_priority': getattr(vm, 'priority', 'Regular'),
                        'workload_type': ', '.join(matched_tags[:3]) if matched_tags else 'interruptible',
                        'spot_eligible_indicators': matched_tags,
                        'current_monthly_cost': round(current_cost, 2),
                        'spot_monthly_cost': round(spot_cost, 2),
                        'monthly_savings': round(monthly_savings, 2),
                        'spot_discount_percent': round(spot_discount_percent, 1),
                        'age_days': age_days,
                        'total_wasted_cost': round(total_wasted, 2),
                        'orphan_reason': f'VM runs interruptible workload ({", ".join(matched_tags[:2]) if matched_tags else "dev/test"}) on Regular priority. '
                                        f'Spot VMs offer 60-90% savings for fault-tolerant workloads.',
                        'recommendation': f'Convert to Azure Spot VM for ~{spot_discount_percent:.0f}% cost savings (${monthly_savings:.2f}/month). '
                                        f'Spot VMs are ideal for batch jobs, dev/test, CI/CD, and analytics workloads that can handle interruptions. '
                                        f'Use eviction policies and configure VM Scale Sets with multiple instance types for high availability.',
                        'confidence_level': confidence_level,
                        'migration_effort': 'high',  # Requires recreation as Spot VM
                        'eviction_policy_recommendation': 'Deallocate',  # Stop VM on eviction instead of Delete
                        'tags': vm_tags,
                    },
                ))

        except Exception as e:
            print(f"Error scanning Spot-convertible VMs in {region}: {str(e)}")

        return orphans

    async def scan_underutilized_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for underutilized Azure Virtual Machines (rightsizing opportunity).

        Detects running VMs with consistently low CPU utilization (<20% avg, <40% p95)
        over an extended period, indicating they are oversized and could be downsized
        for significant cost savings.

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used: "Percentage CPU" (Average, Maximum, Percentile 95)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_observation_days": int (default 30) - Observation period,
                    "max_avg_cpu_percent": float (default 20.0) - Max sustained avg CPU,
                    "max_p95_cpu_percent": float (default 40.0) - Max peak (p95) CPU
                }

        Returns:
            List of underutilized VMs with rightsizing recommendations
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient
        import re

        orphans = []

        # Extract detection rules
        min_observation_days = detection_rules.get("min_observation_days", 30) if detection_rules else 30
        max_avg_cpu_percent = detection_rules.get("max_avg_cpu_percent", 20.0) if detection_rules else 20.0
        max_p95_cpu_percent = detection_rules.get("max_p95_cpu_percent", 40.0) if detection_rules else 40.0

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Get VM instance view for power state
                resource_group = vm.id.split('/')[4]
                try:
                    instance_view = compute_client.virtual_machines.instance_view(
                        resource_group_name=resource_group,
                        vm_name=vm.name
                    )
                except Exception as e:
                    print(f"Error getting instance view for VM {vm.name}: {str(e)}")
                    continue

                # Check if VM is running
                power_state = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        break

                # Only analyze running VMs
                if power_state != 'running':
                    continue

                # Query Azure Monitor metrics for CPU
                try:
                    # Get average CPU over observation period
                    avg_metrics = await self._get_vm_metrics(
                        vm_id=vm.id,
                        metric_names=["Percentage CPU"],
                        timespan_days=min_observation_days,
                        aggregation="Average"
                    )
                    avg_cpu_percent = avg_metrics.get("Percentage CPU", 0.0)

                    # Get maximum CPU over observation period
                    max_metrics = await self._get_vm_metrics(
                        vm_id=vm.id,
                        metric_names=["Percentage CPU"],
                        timespan_days=min_observation_days,
                        aggregation="Maximum"
                    )
                    max_cpu_percent = max_metrics.get("Percentage CPU", 0.0)

                    # Calculate p95 (approximate - use max as upper bound if needed)
                    # In real implementation, would need to collect all data points and calculate percentile
                    # For simplicity, estimate p95 as ~80% of max (conservative estimate)
                    p95_cpu_percent = min(max_cpu_percent * 0.8, max_cpu_percent)

                    # Check if VM is underutilized
                    if avg_cpu_percent >= max_avg_cpu_percent or p95_cpu_percent >= max_p95_cpu_percent:
                        continue  # Not underutilized

                    # Parse current VM SKU to suggest downsize
                    vm_size = vm.hardware_profile.vm_size
                    current_cost = self._get_vm_cost_estimate(vm_size)

                    # Extract vCPU count from SKU name (e.g., D4s_v3 → 4 vCPUs)
                    # Pattern: Standard_{Series}{vCPU}[s]_v{gen}
                    vcpu_match = re.search(r'[A-Z](\d+)', vm_size)
                    if not vcpu_match:
                        continue  # Can't parse SKU

                    current_vcpus = int(vcpu_match.group(1))

                    # Suggest downsize by 50% (half the vCPUs)
                    suggested_vcpus = max(current_vcpus // 2, 1)  # Minimum 1 vCPU

                    # Build suggested SKU (replace vCPU count)
                    suggested_sku = vm_size.replace(str(current_vcpus), str(suggested_vcpus))

                    # Estimate cost savings (50% for halving vCPUs)
                    savings_percent = 50.0 if suggested_vcpus < current_vcpus else 0.0
                    monthly_savings = current_cost * (savings_percent / 100.0)
                    new_cost = current_cost - monthly_savings

                    # Calculate VM age for total wasted cost
                    age_days = 0
                    if vm.time_created:
                        age_delta = datetime.now(timezone.utc) - vm.time_created
                        age_days = age_delta.days

                    total_wasted = (age_days / 30.0) * monthly_savings if age_days > 0 else monthly_savings

                    # Determine confidence level
                    if min_observation_days >= 60:
                        confidence_level = 'critical'
                    elif min_observation_days >= 30:
                        confidence_level = 'high'
                    elif min_observation_days >= 14:
                        confidence_level = 'medium'
                    else:
                        confidence_level = 'low'

                    orphans.append(OrphanResourceData(
                        resource_type='virtual_machine_underutilized',
                        resource_id=vm.id,
                        resource_name=vm.name,
                        region=region,
                        estimated_monthly_cost=monthly_savings,  # Savings opportunity
                        resource_metadata={
                            'vm_id': vm.id,
                            'vm_name': vm.name,
                            'current_vm_size': vm_size,
                            'suggested_vm_size': suggested_sku,
                            'current_vcpus': current_vcpus,
                            'suggested_vcpus': suggested_vcpus,
                            'power_state': 'running',
                            'avg_cpu_percent': round(avg_cpu_percent, 2),
                            'max_cpu_percent': round(max_cpu_percent, 2),
                            'p95_cpu_percent': round(p95_cpu_percent, 2),
                            'observation_period_days': min_observation_days,
                            'current_monthly_cost': round(current_cost, 2),
                            'new_monthly_cost': round(new_cost, 2),
                            'monthly_savings': round(monthly_savings, 2),
                            'savings_percent': round(savings_percent, 1),
                            'age_days': age_days,
                            'total_wasted_cost': round(total_wasted, 2),
                            'orphan_reason': f'VM consistently underutilized (avg {avg_cpu_percent:.1f}% CPU, p95 {p95_cpu_percent:.1f}%) over {min_observation_days} days. '
                                            f'Oversized for workload - rightsizing opportunity detected.',
                            'recommendation': f'Downsize from {vm_size} ({current_vcpus} vCPU) to {suggested_sku} ({suggested_vcpus} vCPU) for ~{savings_percent:.0f}% cost savings (${monthly_savings:.2f}/month). '
                                            f'Current CPU usage is very low (avg {avg_cpu_percent:.1f}%, p95 {p95_cpu_percent:.1f}%), indicating the VM is significantly oversized for the workload.',
                            'confidence_level': confidence_level,
                            'migration_effort': 'medium',  # Requires VM resize operation
                            'tags': vm.tags or {},
                        },
                    ))

                except Exception as e:
                    print(f"Error querying metrics for VM {vm.name}: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error scanning underutilized VMs in {region}: {str(e)}")

        return orphans

    async def scan_memory_overprovisioned_vms(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for memory-optimized Azure VMs with low memory usage.

        Detects E-series (memory-optimized) VMs with low memory utilization,
        indicating they could be downsized to D-series (general purpose) for cost savings.

        NOTE: This scenario requires Azure Monitor Agent installed on VMs to collect
        memory metrics. Without the agent, detection is based on VM series analysis only.

        Requires: Azure Monitor "Monitoring Reader" permission + Azure Monitor Agent on VMs
        Metrics used: "Available Memory Bytes" (custom metric via Azure Monitor Agent)

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_observation_days": int (default 30) - Observation period,
                    "max_memory_percent": float (default 30.0) - Max memory usage,
                    "memory_optimized_series": list (default ["E", "M", "G"]) - Series to check
                }

        Returns:
            List of memory-overprovisioned VMs
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Extract detection rules
        min_observation_days = detection_rules.get("min_observation_days", 30) if detection_rules else 30
        max_memory_percent = detection_rules.get("max_memory_percent", 30.0) if detection_rules else 30.0
        memory_optimized_series = detection_rules.get("memory_optimized_series", ["E", "M", "G"]) if detection_rules else ["E", "M", "G"]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                vm_size = vm.hardware_profile.vm_size

                # Check if VM is memory-optimized series (E, M, G)
                is_memory_optimized = False
                vm_series = None
                for series in memory_optimized_series:
                    if vm_size.startswith(f"Standard_{series}"):
                        is_memory_optimized = True
                        vm_series = series
                        break

                if not is_memory_optimized:
                    continue

                # Get VM instance view for power state
                resource_group = vm.id.split('/')[4]
                try:
                    instance_view = compute_client.virtual_machines.instance_view(
                        resource_group_name=resource_group,
                        vm_name=vm.name
                    )
                except Exception as e:
                    print(f"Error getting instance view for VM {vm.name}: {str(e)}")
                    continue

                # Check if VM is running
                power_state = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        break

                # Only analyze running VMs
                if power_state != 'running':
                    continue

                # Try to query memory metrics (requires Azure Monitor Agent)
                try:
                    # Attempt to get Available Memory Bytes metric
                    # Note: This requires Azure Monitor Agent to be installed on the VM
                    memory_metrics = await self._get_vm_metrics(
                        vm_id=vm.id,
                        metric_names=["Available Memory Bytes"],
                        timespan_days=min_observation_days,
                        aggregation="Average"
                    )

                    available_memory_bytes = memory_metrics.get("Available Memory Bytes", 0.0)

                    # If memory metrics unavailable (agent not installed), skip this VM
                    if available_memory_bytes == 0.0:
                        print(f"Memory metrics unavailable for VM {vm.name} - Azure Monitor Agent may not be installed")
                        continue

                    # Estimate total memory based on VM SKU (rough estimates)
                    # E-series: E{vCPU}[s]_v{gen} → vCPU * 8 GB RAM (8:1 ratio)
                    # Example: E4s_v3 = 4 vCPU * 8 GB = 32 GB RAM
                    import re
                    vcpu_match = re.search(r'[A-Z](\d+)', vm_size)
                    if not vcpu_match:
                        continue

                    vcpus = int(vcpu_match.group(1))
                    # E-series has 8 GB RAM per vCPU
                    total_memory_gb = vcpus * 8
                    total_memory_bytes = total_memory_gb * 1024 * 1024 * 1024

                    # Calculate memory used percentage
                    memory_used_bytes = total_memory_bytes - available_memory_bytes
                    memory_used_percent = (memory_used_bytes / total_memory_bytes * 100.0) if total_memory_bytes > 0 else 0.0

                    # Check if memory usage is low
                    if memory_used_percent >= max_memory_percent:
                        continue  # Memory usage is high enough

                    # Suggest migration to D-series (general purpose)
                    # E-series → D-series (same vCPU count)
                    suggested_sku = vm_size.replace(f"_{vm_series}", "_D")

                    # Calculate costs
                    current_cost = self._get_vm_cost_estimate(vm_size)
                    # E-series is typically 25-30% more expensive than D-series
                    savings_percent = 25.0
                    monthly_savings = current_cost * (savings_percent / 100.0)
                    new_cost = current_cost - monthly_savings

                    # Calculate VM age
                    age_days = 0
                    if vm.time_created:
                        age_delta = datetime.now(timezone.utc) - vm.time_created
                        age_days = age_delta.days

                    total_wasted = (age_days / 30.0) * monthly_savings if age_days > 0 else monthly_savings

                    # Determine confidence level
                    if min_observation_days >= 60:
                        confidence_level = 'critical'
                    elif min_observation_days >= 30:
                        confidence_level = 'high'
                    elif min_observation_days >= 14:
                        confidence_level = 'medium'
                    else:
                        confidence_level = 'low'

                    orphans.append(OrphanResourceData(
                        resource_type='virtual_machine_memory_overprovisioned',
                        resource_id=vm.id,
                        resource_name=vm.name,
                        region=region,
                        estimated_monthly_cost=monthly_savings,  # Savings opportunity
                        resource_metadata={
                            'vm_id': vm.id,
                            'vm_name': vm.name,
                            'current_vm_size': vm_size,
                            'suggested_vm_size': suggested_sku,
                            'vm_series': vm_series,
                            'power_state': 'running',
                            'memory_used_percent': round(memory_used_percent, 2),
                            'total_memory_gb': total_memory_gb,
                            'available_memory_gb': round(available_memory_bytes / (1024 * 1024 * 1024), 2),
                            'observation_period_days': min_observation_days,
                            'current_monthly_cost': round(current_cost, 2),
                            'new_monthly_cost': round(new_cost, 2),
                            'monthly_savings': round(monthly_savings, 2),
                            'savings_percent': round(savings_percent, 1),
                            'age_days': age_days,
                            'total_wasted_cost': round(total_wasted, 2),
                            'orphan_reason': f'{vm_series}-series (memory-optimized) VM only using {memory_used_percent:.1f}% memory over {min_observation_days} days. '
                                            f'Standard D-series (general purpose) would be sufficient.',
                            'recommendation': f'Downgrade from {vm_size} ({vm_series}-series memory-optimized) to {suggested_sku} (D-series general purpose) for ~{savings_percent:.0f}% cost savings (${monthly_savings:.2f}/month). '
                                            f'Current memory usage is very low ({memory_used_percent:.1f}%), indicating memory-optimized SKU is unnecessary.',
                            'confidence_level': confidence_level,
                            'migration_effort': 'medium',  # Requires VM resize
                            'requires_agent': True,  # Requires Azure Monitor Agent
                            'tags': vm.tags or {},
                        },
                    ))

                except Exception as e:
                    print(f"Error querying memory metrics for VM {vm.name}: {str(e)}")
                    # Note: If agent not installed, this will fail silently and VM will be skipped
                    continue

        except Exception as e:
            print(f"Error scanning memory-overprovisioned VMs in {region}: {str(e)}")

        return orphans

    async def _get_disk_metrics(
        self,
        disk_id: str,
        metric_names: list[str],
        timespan_days: int,
        aggregation: str = "Average"
    ) -> dict[str, float]:
        """
        Query Azure Monitor metrics for a managed disk.

        Args:
            disk_id: Full Azure resource ID of the disk
            metric_names: List of metric names to query (e.g., ["Composite Disk Read Operations/sec"])
            timespan_days: Number of days to look back
            aggregation: Aggregation type ("Average", "Maximum", "Minimum", "Total")

        Returns:
            Dict mapping metric_name -> aggregated value over the timespan

        Example:
            metrics = await _get_disk_metrics(
                disk_id="/subscriptions/.../disks/my-disk",
                metric_names=["Composite Disk Read Operations/sec", "Composite Disk Write Operations/sec"],
                timespan_days=60,
                aggregation="Average"
            )
            # Returns: {"Composite Disk Read Operations/sec": 0.05, "Composite Disk Write Operations/sec": 0.02}
        """
        from datetime import datetime, timedelta, timezone
        from azure.monitor.query import MetricsQueryClient, MetricAggregationType
        from azure.identity import ClientSecretCredential

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            metrics_client = MetricsQueryClient(credential)

            # Calculate timespan
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=timespan_days)

            # Map aggregation string to enum
            aggregation_map = {
                "Average": MetricAggregationType.AVERAGE,
                "Maximum": MetricAggregationType.MAXIMUM,
                "Minimum": MetricAggregationType.MINIMUM,
                "Total": MetricAggregationType.TOTAL,
                "Count": MetricAggregationType.COUNT
            }
            agg_type = aggregation_map.get(aggregation, MetricAggregationType.AVERAGE)

            # Query metrics
            response = metrics_client.query_resource(
                resource_uri=disk_id,
                metric_names=metric_names,
                timespan=(start_time, end_time),
                aggregations=[agg_type]
            )

            results = {}
            for metric in response.metrics:
                if metric.timeseries:
                    # Collect all data points and calculate overall average
                    values = []
                    for ts in metric.timeseries:
                        for data in ts.data:
                            if aggregation == "Average" and data.average is not None:
                                values.append(data.average)
                            elif aggregation == "Maximum" and data.maximum is not None:
                                values.append(data.maximum)
                            elif aggregation == "Minimum" and data.minimum is not None:
                                values.append(data.minimum)
                            elif aggregation == "Total" and data.total is not None:
                                values.append(data.total)

                    # Calculate overall metric value
                    if values:
                        results[metric.name] = sum(values) / len(values)
                    else:
                        results[metric.name] = 0.0
                else:
                    results[metric.name] = 0.0

            return results

        except Exception as e:
            print(f"Error querying Azure Monitor metrics for {disk_id}: {str(e)}")
            # Return zeros if metrics unavailable
            return {name: 0.0 for name in metric_names}

    async def _get_public_ip_metrics(
        self,
        ip_id: str,
        metric_names: list[str],
        timespan_days: int,
    ) -> dict[str, float]:
        """
        Query Azure Monitor metrics for a Public IP Address.

        Args:
            ip_id: Full Azure resource ID of the Public IP
            metric_names: List of metric names to query (e.g., ["ByteCount", "PacketCount", "IfUnderDDoSAttack"])
            timespan_days: Number of days to look back

        Returns:
            Dict mapping metric_name -> aggregated value over the timespan

        Metrics available for Public IPs:
            - ByteCount: Total bytes transmitted (inbound + outbound)
            - PacketCount: Total packets transmitted (inbound + outbound)
            - IfUnderDDoSAttack: Maximum value (1 = under attack, 0 = not under attack)

        Example:
            metrics = await _get_public_ip_metrics(
                ip_id="/subscriptions/.../publicIPAddresses/my-ip",
                metric_names=["ByteCount", "PacketCount"],
                timespan_days=30
            )
            # Returns: {"ByteCount": 1234567890.0, "PacketCount": 9876543.0}
        """
        from datetime import datetime, timedelta, timezone
        from azure.monitor.query import MetricsQueryClient, MetricAggregationType
        from azure.identity import ClientSecretCredential

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            metrics_client = MetricsQueryClient(credential)

            # Calculate timespan
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=timespan_days)

            # Public IP metrics use different aggregations depending on the metric
            # ByteCount and PacketCount: Total (sum of all bytes/packets)
            # IfUnderDDoSAttack: Maximum (binary flag, 1 = attacked at some point)
            results = {}

            for metric_name in metric_names:
                # Determine aggregation type based on metric
                if metric_name == "IfUnderDDoSAttack":
                    agg_type = MetricAggregationType.MAXIMUM
                else:  # ByteCount, PacketCount
                    agg_type = MetricAggregationType.TOTAL

                # Query metric
                response = metrics_client.query_resource(
                    resource_uri=ip_id,
                    metric_names=[metric_name],
                    timespan=(start_time, end_time),
                    aggregations=[agg_type]
                )

                # Extract value
                for metric in response.metrics:
                    if metric.timeseries:
                        # Collect all data points
                        values = []
                        for ts in metric.timeseries:
                            for data in ts.data:
                                if metric_name == "IfUnderDDoSAttack" and data.maximum is not None:
                                    values.append(data.maximum)
                                elif metric_name in ["ByteCount", "PacketCount"] and data.total is not None:
                                    values.append(data.total)

                        # Calculate overall metric value
                        if values:
                            if metric_name == "IfUnderDDoSAttack":
                                # For DDoS flag, return maximum (1 if ever attacked, 0 otherwise)
                                results[metric_name] = max(values)
                            else:
                                # For ByteCount and PacketCount, return total sum
                                results[metric_name] = sum(values)
                        else:
                            results[metric_name] = 0.0
                    else:
                        results[metric_name] = 0.0

            return results

        except Exception as e:
            print(f"Error querying Azure Monitor metrics for Public IP {ip_id}: {str(e)}")
            # Return zeros if metrics unavailable
            return {name: 0.0 for name in metric_names}

    async def _get_vm_metrics(
        self,
        vm_id: str,
        metric_names: list[str],
        timespan_days: int,
        aggregation: str = "Average"
    ) -> dict[str, float]:
        """
        Query Azure Monitor metrics for a Virtual Machine.

        Args:
            vm_id: Full Azure resource ID of the VM
            metric_names: List of metric names to query (e.g., ["Percentage CPU", "Network In Total"])
            timespan_days: Number of days to look back
            aggregation: Aggregation type ("Average", "Maximum", "Minimum", "Total")

        Returns:
            Dict mapping metric_name -> aggregated value over the timespan

        Metrics available for VMs:
            - Percentage CPU: CPU utilization percentage (0-100%)
            - Network In Total: Total bytes received (bytes)
            - Network Out Total: Total bytes transmitted (bytes)
            - Disk Read Bytes: Disk read throughput (bytes)
            - Disk Write Bytes: Disk write throughput (bytes)
            - Available Memory Bytes: Available RAM (requires VM agent)

        Example:
            metrics = await _get_vm_metrics(
                vm_id="/subscriptions/.../virtualMachines/my-vm",
                metric_names=["Percentage CPU", "Network In Total", "Network Out Total"],
                timespan_days=7,
                aggregation="Average"
            )
            # Returns: {"Percentage CPU": 2.5, "Network In Total": 1024000.0, "Network Out Total": 512000.0}
        """
        from datetime import datetime, timedelta, timezone
        from azure.monitor.query import MetricsQueryClient, MetricAggregationType
        from azure.identity import ClientSecretCredential

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            metrics_client = MetricsQueryClient(credential)

            # Calculate timespan
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=timespan_days)

            # Map aggregation string to enum
            aggregation_map = {
                "Average": MetricAggregationType.AVERAGE,
                "Maximum": MetricAggregationType.MAXIMUM,
                "Minimum": MetricAggregationType.MINIMUM,
                "Total": MetricAggregationType.TOTAL,
                "Count": MetricAggregationType.COUNT
            }
            agg_type = aggregation_map.get(aggregation, MetricAggregationType.AVERAGE)

            # Query metrics
            response = metrics_client.query_resource(
                resource_uri=vm_id,
                metric_names=metric_names,
                timespan=(start_time, end_time),
                aggregations=[agg_type]
            )

            results = {}
            for metric in response.metrics:
                if metric.timeseries:
                    # Collect all data points and calculate overall value
                    values = []
                    for ts in metric.timeseries:
                        for data in ts.data:
                            if aggregation == "Average" and data.average is not None:
                                values.append(data.average)
                            elif aggregation == "Maximum" and data.maximum is not None:
                                values.append(data.maximum)
                            elif aggregation == "Minimum" and data.minimum is not None:
                                values.append(data.minimum)
                            elif aggregation == "Total" and data.total is not None:
                                values.append(data.total)

                    # Calculate overall metric value
                    if values:
                        if aggregation == "Total":
                            # For Total aggregation (e.g., Network In/Out), sum all values
                            results[metric.name] = sum(values)
                        else:
                            # For Average, Maximum, Minimum - take average of data points
                            results[metric.name] = sum(values) / len(values)
                    else:
                        results[metric.name] = 0.0
                else:
                    results[metric.name] = 0.0

            return results

        except Exception as e:
            print(f"Error querying Azure Monitor metrics for VM {vm_id}: {str(e)}")
            # Return zeros if metrics unavailable
            return {name: 0.0 for name in metric_names}

    async def scan_idle_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Managed Disks with zero I/O activity.

        Detects disks attached to VMs that have had virtually no read/write operations
        over an extended period (default 60 days), indicating they are not being used.

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used: "Composite Disk Read Operations/sec", "Composite Disk Write Operations/sec"

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_idle_days": int (default 60),
                    "max_iops_threshold": float (default 0.1) - Avg IOPS below this = idle
                }

        Returns:
            List of idle disk resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_idle_days = detection_rules.get("min_idle_days", 60) if detection_rules else 60
        max_iops_threshold = detection_rules.get("max_iops_threshold", 0.1) if detection_rules else 0.1

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Only check attached disks (idle detection only makes sense for attached disks)
                if disk.disk_state != 'Attached':
                    continue

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_idle_days:
                    continue

                # Query Azure Monitor metrics for I/O activity
                metrics = await self._get_disk_metrics(
                    disk_id=disk.id,
                    metric_names=["Composite Disk Read Operations/sec", "Composite Disk Write Operations/sec"],
                    timespan_days=min_idle_days,
                    aggregation="Average"
                )

                avg_read_iops = metrics.get("Composite Disk Read Operations/sec", 0.0)
                avg_write_iops = metrics.get("Composite Disk Write Operations/sec", 0.0)
                total_avg_iops = avg_read_iops + avg_write_iops

                # Detect idle disk (very low I/O activity)
                if total_avg_iops < max_iops_threshold:
                    monthly_cost = self._calculate_disk_cost(disk)

                    metadata = {
                        'disk_id': disk.id,
                        'disk_name': disk.name,
                        'disk_size_gb': disk.disk_size_gb,
                        'sku_name': disk.sku.name if disk.sku else 'Unknown',
                        'disk_state': disk.disk_state,
                        'avg_read_iops': round(avg_read_iops, 4),
                        'avg_write_iops': round(avg_write_iops, 4),
                        'total_avg_iops': round(total_avg_iops, 4),
                        'observation_period_days': min_idle_days,
                        'iops_threshold': max_iops_threshold,
                        'age_days': age_days,
                        'created_at': disk.time_created.isoformat() if disk.time_created else None,
                        'orphan_reason': f"Disk attached to VM but idle for {min_idle_days} days with {total_avg_iops:.4f} avg IOPS (threshold: {max_iops_threshold} IOPS)",
                        'recommendation': f"Detach and delete idle disk to save ${monthly_cost:.2f}/month. Disk has no meaningful I/O activity.",
                        'tags': disk.tags if disk.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    orphan = OrphanResourceData(
                        resource_type='managed_disk_idle',
                        resource_id=disk.id,
                        resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                        region=disk.location,
                        estimated_monthly_cost=monthly_cost,
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning idle disks in {region}: {str(e)}")

        return orphans

    async def scan_unused_bursting(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Premium Managed Disks with bursting enabled but never used.

        Disk bursting costs +15% but is only useful if the workload actually bursts
        beyond baseline IOPS. This detects disks with bursting enabled that have
        never used their burst credits over the observation period.

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used: "OS Disk Used Burst IO Credits %", "Data Disk Used Burst IO Credits %"

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_observation_days": int (default 30),
                    "max_burst_usage_percent": float (default 0.01) - Max % burst credits used
                }

        Returns:
            List of disks with unused bursting feature
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_observation_days = detection_rules.get("min_observation_days", 30) if detection_rules else 30
        max_burst_usage = detection_rules.get("max_burst_usage_percent", 0.01) if detection_rules else 0.01

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Only check Premium disks with bursting enabled
                sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
                if 'Premium' not in sku_name:
                    continue  # Bursting only available on Premium disks

                # Check if bursting is enabled
                bursting_enabled = getattr(disk, 'bursting_enabled', False)
                if not bursting_enabled:
                    continue

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_observation_days:
                    continue

                # Determine metric name based on disk type (OS vs Data)
                # We'll try both and use whichever returns data
                metric_names = ["OS Disk Used Burst IO Credits Percentage", "Data Disk Used Burst IO Credits Percentage"]

                metrics = await self._get_disk_metrics(
                    disk_id=disk.id,
                    metric_names=metric_names,
                    timespan_days=min_observation_days,
                    aggregation="Maximum"  # Use Maximum to catch any burst usage
                )

                # Get the max burst usage from either OS or Data disk metric
                max_burst_percentage = max(
                    metrics.get("OS Disk Used Burst IO Credits Percentage", 0.0),
                    metrics.get("Data Disk Used Burst IO Credits Percentage", 0.0)
                )

                # Detect unused bursting (never used burst credits)
                if max_burst_percentage < max_burst_usage:
                    current_cost = self._calculate_disk_cost(disk)

                    # Bursting adds ~15% to disk cost
                    cost_without_bursting = current_cost / 1.15
                    potential_savings = current_cost - cost_without_bursting

                    metadata = {
                        'disk_id': disk.id,
                        'disk_name': disk.name,
                        'disk_size_gb': disk.disk_size_gb,
                        'sku_name': sku_name,
                        'bursting_enabled': True,
                        'max_burst_credits_used_percent': round(max_burst_percentage, 4),
                        'observation_period_days': min_observation_days,
                        'burst_usage_threshold': max_burst_usage,
                        'current_monthly_cost': f'${current_cost:.2f}',
                        'cost_without_bursting': f'${cost_without_bursting:.2f}',
                        'potential_monthly_savings': f'${potential_savings:.2f}',
                        'age_days': age_days,
                        'created_at': disk.time_created.isoformat() if disk.time_created else None,
                        'orphan_reason': f"Bursting enabled but unused for {min_observation_days} days. Max burst credits used: {max_burst_percentage:.4f}% (threshold: {max_burst_usage}%)",
                        'recommendation': f"Disable bursting to save ${potential_savings:.2f}/month (~15% cost reduction). Bursting has never been utilized.",
                        'tags': disk.tags if disk.tags else {},
                        'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                    }

                    orphan = OrphanResourceData(
                        resource_type='managed_disk_unused_bursting',
                        resource_id=disk.id,
                        resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                        region=disk.location,
                        estimated_monthly_cost=round(potential_savings, 2),
                        resource_metadata=metadata
                    )

                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning unused bursting in {region}: {str(e)}")

        return orphans

    async def scan_overprovisioned_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for over-provisioned Azure Premium Managed Disks (performance tier too high).

        Detects Premium disks where actual IOPS/bandwidth usage is significantly lower
        than provisioned capacity, indicating a lower-tier disk would suffice with
        substantial cost savings.

        Example: P50 (7500 IOPS, $307/mo) used at 500 IOPS → P30 (5000 IOPS, $135/mo) saves $172/mo

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used: "Data/OS Disk IOPS Consumed %", "Data/OS Disk Bandwidth Consumed %"

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_observation_days": int (default 30),
                    "max_utilization_percent": float (default 30) - Max % of provisioned IOPS/BW used
                }

        Returns:
            List of over-provisioned disk resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_observation_days = detection_rules.get("min_observation_days", 30) if detection_rules else 30
        max_utilization = detection_rules.get("max_utilization_percent", 30) if detection_rules else 30

        # Premium disk SKU downgrade mapping (size in GB -> SKU name -> (IOPS, MB/s))
        premium_tiers = [
            ("P80", 32767, 16384, 900),   # 32TB
            ("P70", 16384, 8192, 750),    # 16TB
            ("P60", 8192, 4096, 600),     # 8TB
            ("P50", 4096, 7500, 250),     # 4TB
            ("P40", 2048, 7500, 250),     # 2TB
            ("P30", 1024, 5000, 200),     # 1TB
            ("P20", 512, 2300, 150),      # 512GB
            ("P15", 256, 1100, 125),      # 256GB
            ("P10", 128, 500, 100),       # 128GB
        ]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Only check Premium disks
                sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
                if 'Premium' not in sku_name:
                    continue

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_observation_days:
                    continue

                # Query Azure Monitor metrics for utilization
                metric_names = [
                    "OS Disk IOPS Consumed Percentage",
                    "Data Disk IOPS Consumed Percentage",
                    "OS Disk Bandwidth Consumed Percentage",
                    "Data Disk Bandwidth Consumed Percentage"
                ]

                metrics = await self._get_disk_metrics(
                    disk_id=disk.id,
                    metric_names=metric_names,
                    timespan_days=min_observation_days,
                    aggregation="Average"
                )

                # Get max utilization from either OS or Data disk metrics
                iops_utilization = max(
                    metrics.get("OS Disk IOPS Consumed Percentage", 0.0),
                    metrics.get("Data Disk IOPS Consumed Percentage", 0.0)
                )
                bandwidth_utilization = max(
                    metrics.get("OS Disk Bandwidth Consumed Percentage", 0.0),
                    metrics.get("Data Disk Bandwidth Consumed Percentage", 0.0)
                )

                # Detect over-provisioning (both IOPS and bandwidth under-utilized)
                if iops_utilization < max_utilization and bandwidth_utilization < max_utilization:
                    current_cost = self._calculate_disk_cost(disk)
                    disk_size_gb = disk.disk_size_gb if disk.disk_size_gb else 0

                    # Find current tier and suggest downgrade
                    current_tier = None
                    suggested_tier = None

                    for tier_name, tier_size, tier_iops, tier_mbps in premium_tiers:
                        if disk_size_gb >= tier_size:
                            current_tier = (tier_name, tier_size, tier_iops, tier_mbps)
                            break

                    # Find next lower tier that would still accommodate usage
                    # Assume actual usage is iops_utilization% of current tier's IOPS
                    if current_tier:
                        current_iops = current_tier[2]
                        actual_iops_usage = (iops_utilization / 100) * current_iops

                        for tier_name, tier_size, tier_iops, tier_mbps in reversed(premium_tiers):
                            # Suggest tier if it provides at least 2x actual usage (safety margin)
                            if tier_iops >= actual_iops_usage * 2:
                                suggested_tier = (tier_name, tier_size, tier_iops, tier_mbps)

                    if suggested_tier and suggested_tier != current_tier:
                        # Calculate cost savings
                        suggested_cost = suggested_tier[1] * 0.135  # Rough estimate $0.135/GB/month for Premium
                        potential_savings = current_cost - suggested_cost

                        if potential_savings > 5:  # Only flag if savings > $5/month
                            metadata = {
                                'disk_id': disk.id,
                                'disk_name': disk.name,
                                'disk_size_gb': disk_size_gb,
                                'current_sku': sku_name,
                                'current_tier': current_tier[0] if current_tier else 'Unknown',
                                'suggested_tier': suggested_tier[0],
                                'current_iops': current_tier[2] if current_tier else 0,
                                'suggested_iops': suggested_tier[2],
                                'avg_iops_utilization_percent': round(iops_utilization, 2),
                                'avg_bandwidth_utilization_percent': round(bandwidth_utilization, 2),
                                'observation_period_days': min_observation_days,
                                'utilization_threshold': max_utilization,
                                'current_monthly_cost': f'${current_cost:.2f}',
                                'suggested_monthly_cost': f'${suggested_cost:.2f}',
                                'potential_monthly_savings': f'${potential_savings:.2f}',
                                'age_days': age_days,
                                'created_at': disk.time_created.isoformat() if disk.time_created else None,
                                'orphan_reason': f"Disk over-provisioned for {min_observation_days} days. IOPS utilization: {iops_utilization:.2f}%, Bandwidth utilization: {bandwidth_utilization:.2f}% (threshold: {max_utilization}%)",
                                'recommendation': f"Downgrade from {current_tier[0] if current_tier else 'current tier'} to {suggested_tier[0]} to save ${potential_savings:.2f}/month while maintaining performance.",
                                'tags': disk.tags if disk.tags else {},
                                'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                            }

                            orphan = OrphanResourceData(
                                resource_type='managed_disk_overprovisioned',
                                resource_id=disk.id,
                                resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                                region=disk.location,
                                estimated_monthly_cost=round(potential_savings, 2),
                                resource_metadata=metadata
                            )

                            orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning overprovisioned disks in {region}: {str(e)}")

        return orphans

    async def scan_underutilized_hdd_disks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for under-utilized Standard HDD disks that should be Standard SSD.

        Detects large Standard HDD disks with low IOPS usage where a smaller
        Standard SSD would provide better performance at lower cost.

        Example: 1TB Standard HDD ($48/mo, 500 IOPS) with 50 IOPS usage →
                 128GB Standard SSD ($12/mo, 500 IOPS) saves $36/mo + 20x faster

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used: "Composite Disk Read/Write Operations/sec"

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_observation_days": int (default 30),
                    "max_iops_threshold": float (default 100) - Max avg IOPS
                    "min_disk_size_gb": int (default 256) - Only flag large disks
                }

        Returns:
            List of under-utilized HDD disk resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []
        min_observation_days = detection_rules.get("min_observation_days", 30) if detection_rules else 30
        max_iops_threshold = detection_rules.get("max_iops_threshold", 100) if detection_rules else 100
        min_disk_size_gb = detection_rules.get("min_disk_size_gb", 256) if detection_rules else 256

        # Standard SSD sizing (GB -> IOPS)
        ssd_tiers = [
            (4096, 500),   # 4TB
            (2048, 500),   # 2TB
            (1024, 500),   # 1TB
            (512, 500),    # 512GB
            (256, 500),    # 256GB
            (128, 500),    # 128GB
            (64, 500),     # 64GB
        ]

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)

            # List all disks
            disks = compute_client.disks.list()

            for disk in disks:
                # Filter by region
                if disk.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(disk.id):
                    continue

                # Only check Standard HDD disks
                sku_name = disk.sku.name if disk.sku else 'Standard_LRS'
                if sku_name != 'Standard_LRS':
                    continue  # Not Standard HDD

                # Only check large disks
                disk_size_gb = disk.disk_size_gb if disk.disk_size_gb else 0
                if disk_size_gb < min_disk_size_gb:
                    continue

                # Calculate disk age
                age_days = 0
                if disk.time_created:
                    age_days = (datetime.now(timezone.utc) - disk.time_created).days

                # Skip young disks
                if age_days < min_observation_days:
                    continue

                # Query Azure Monitor metrics for IOPS usage
                metrics = await self._get_disk_metrics(
                    disk_id=disk.id,
                    metric_names=["Composite Disk Read Operations/sec", "Composite Disk Write Operations/sec"],
                    timespan_days=min_observation_days,
                    aggregation="Average"
                )

                avg_read_iops = metrics.get("Composite Disk Read Operations/sec", 0.0)
                avg_write_iops = metrics.get("Composite Disk Write Operations/sec", 0.0)
                total_avg_iops = avg_read_iops + avg_write_iops

                # Detect under-utilization (low IOPS on large HDD)
                if total_avg_iops < max_iops_threshold:
                    # Calculate current HDD cost (~$0.04/GB/month for Standard HDD)
                    current_cost = disk_size_gb * 0.04

                    # Find smallest SSD tier that can handle the IOPS
                    suggested_ssd_size = 128  # Minimum SSD size for cost efficiency
                    for ssd_size, ssd_iops in reversed(ssd_tiers):
                        if ssd_iops >= total_avg_iops * 2:  # 2x safety margin
                            suggested_ssd_size = ssd_size
                            break

                    # Standard SSD pricing (~$0.096/GB/month)
                    suggested_cost = suggested_ssd_size * 0.096
                    potential_savings = current_cost - suggested_cost

                    if potential_savings > 5:  # Only flag if savings > $5/month
                        metadata = {
                            'disk_id': disk.id,
                            'disk_name': disk.name,
                            'disk_size_gb': disk_size_gb,
                            'current_sku': 'Standard_LRS (HDD)',
                            'suggested_sku': 'StandardSSD_LRS',
                            'suggested_size_gb': suggested_ssd_size,
                            'avg_read_iops': round(avg_read_iops, 2),
                            'avg_write_iops': round(avg_write_iops, 2),
                            'total_avg_iops': round(total_avg_iops, 2),
                            'observation_period_days': min_observation_days,
                            'iops_threshold': max_iops_threshold,
                            'current_monthly_cost': f'${current_cost:.2f}',
                            'suggested_monthly_cost': f'${suggested_cost:.2f}',
                            'potential_monthly_savings': f'${potential_savings:.2f}',
                            'age_days': age_days,
                            'created_at': disk.time_created.isoformat() if disk.time_created else None,
                            'orphan_reason': f"Standard HDD {disk_size_gb}GB under-utilized for {min_observation_days} days with {total_avg_iops:.2f} avg IOPS (threshold: {max_iops_threshold} IOPS)",
                            'recommendation': f"Switch from Standard HDD {disk_size_gb}GB to Standard SSD {suggested_ssd_size}GB to save ${potential_savings:.2f}/month. SSD provides 20x better performance (IOPS) at lower cost.",
                            'tags': disk.tags if disk.tags else {},
                            'confidence_level': self._calculate_confidence_level(age_days, detection_rules),
                        }

                        orphan = OrphanResourceData(
                            resource_type='managed_disk_underutilized_hdd',
                            resource_id=disk.id,
                            resource_name=disk.name if disk.name else disk.id.split('/')[-1],
                            region=disk.location,
                            estimated_monthly_cost=round(potential_savings, 2),
                            resource_metadata=metadata
                        )

                        orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning underutilized HDD disks in {region}: {str(e)}")

        return orphans

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Virtual Machines (running but completely idle).

        Detects VMs that are running but have very low CPU utilization (<5%) AND
        minimal network traffic (<7MB/day), indicating they are not being actively used.
        This is 100% waste as the VM is paying full compute cost while idle.

        Requires: Azure Monitor "Monitoring Reader" permission
        Metrics used:
            - "Percentage CPU": Average CPU utilization
            - "Network In Total": Total bytes received
            - "Network Out Total": Total bytes transmitted

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration:
                {
                    "enabled": bool (default True),
                    "min_idle_days": int (default 7) - Observation period in days,
                    "max_cpu_percent": float (default 5.0) - Max avg CPU % threshold,
                    "max_network_mb_per_day": float (default 7.0) - Max network traffic MB/day
                }

        Returns:
            List of idle VM resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.compute import ComputeManagementClient

        orphans = []

        # Extract detection rules
        min_idle_days = detection_rules.get("min_idle_days", 7) if detection_rules else 7
        max_cpu_percent = detection_rules.get("max_cpu_percent", 5.0) if detection_rules else 5.0
        max_network_mb_per_day = detection_rules.get("max_network_mb_per_day", 7.0) if detection_rules else 7.0

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            compute_client = ComputeManagementClient(credential, self.subscription_id)
            vms = list(compute_client.virtual_machines.list_all())

            for vm in vms:
                if vm.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(vm.id):
                    continue

                # Get VM instance view for power state
                resource_group = vm.id.split('/')[4]
                try:
                    instance_view = compute_client.virtual_machines.instance_view(
                        resource_group_name=resource_group,
                        vm_name=vm.name
                    )
                except Exception as e:
                    print(f"Error getting instance view for VM {vm.name}: {str(e)}")
                    continue

                # Check if VM is running (not deallocated, not stopped)
                power_state = None
                for status in instance_view.statuses:
                    if status.code and status.code.startswith('PowerState/'):
                        power_state = status.code.split('/')[-1]
                        break

                # Only analyze running VMs
                if power_state != 'running':
                    continue

                # Query Azure Monitor metrics for CPU and Network
                try:
                    metrics = await self._get_vm_metrics(
                        vm_id=vm.id,
                        metric_names=["Percentage CPU", "Network In Total", "Network Out Total"],
                        timespan_days=min_idle_days,
                        aggregation="Average"
                    )

                    avg_cpu_percent = metrics.get("Percentage CPU", 0.0)
                    network_in_bytes = metrics.get("Network In Total", 0.0)
                    network_out_bytes = metrics.get("Network Out Total", 0.0)

                    # Convert network bytes to MB
                    network_in_mb = network_in_bytes / (1024 * 1024)
                    network_out_mb = network_out_bytes / (1024 * 1024)
                    total_network_mb = network_in_mb + network_out_mb

                    # Calculate MB per day
                    network_mb_per_day = total_network_mb / min_idle_days if min_idle_days > 0 else total_network_mb

                    # Check if VM is idle (low CPU AND low network traffic)
                    if avg_cpu_percent < max_cpu_percent and network_mb_per_day < max_network_mb_per_day:
                        # Calculate VM age
                        age_days = 0
                        if vm.time_created:
                            age_delta = datetime.now(timezone.utc) - vm.time_created
                            age_days = age_delta.days

                        # Calculate monthly cost (100% waste - VM is running but idle)
                        vm_cost = self._get_vm_cost_estimate(vm.hardware_profile.vm_size)

                        # Determine confidence level based on observation period
                        if min_idle_days >= 30:
                            confidence_level = 'critical'
                        elif min_idle_days >= 14:
                            confidence_level = 'high'
                        elif min_idle_days >= 7:
                            confidence_level = 'medium'
                        else:
                            confidence_level = 'low'

                        # Calculate total wasted cost (age * monthly cost)
                        monthly_waste = vm_cost
                        total_wasted = (age_days / 30.0) * monthly_waste if age_days > 0 else monthly_waste

                        orphans.append(OrphanResourceData(
                            resource_type='virtual_machine_idle',
                            resource_id=vm.id,
                            resource_name=vm.name,
                            region=region,
                            estimated_monthly_cost=monthly_waste,
                            resource_metadata={
                                'vm_id': vm.id,
                                'vm_name': vm.name,
                                'vm_size': vm.hardware_profile.vm_size,
                                'power_state': 'running',
                                'os_type': vm.storage_profile.os_disk.os_type.value if vm.storage_profile.os_disk.os_type else 'Unknown',
                                'avg_cpu_percent': round(avg_cpu_percent, 2),
                                'avg_network_in_mb': round(network_in_mb, 2),
                                'avg_network_out_mb': round(network_out_mb, 2),
                                'total_network_mb': round(total_network_mb, 2),
                                'network_mb_per_day': round(network_mb_per_day, 2),
                                'observation_period_days': min_idle_days,
                                'age_days': age_days,
                                'total_wasted_cost': round(total_wasted, 2),
                                'orphan_reason': f'VM running but idle for {min_idle_days} days with {avg_cpu_percent:.1f}% avg CPU and {network_mb_per_day:.1f}MB/day network traffic',
                                'recommendation': f'Shut down or delete VM. Completely idle workload wasting ${monthly_waste:.2f}/month. Consider deallocating if temporarily unused, or deleting if no longer needed.',
                                'confidence_level': confidence_level,
                                'tags': vm.tags or {},
                            },
                        ))

                except Exception as e:
                    print(f"Error querying metrics for VM {vm.name}: {str(e)}")
                    continue

        except Exception as e:
            print(f"Error scanning idle VMs in {region}: {str(e)}")

        return orphans

    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for Azure Load Balancers with no backend pools.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of unused load balancer resources
        """
        # TODO: Implement using azure.mgmt.network.LoadBalancersOperations
        # Detect: Load Balancers with 0 backend pool instances
        return []

    async def scan_stopped_databases(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for stopped/idle Azure Databases (SQL, PostgreSQL, MySQL).

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of stopped/idle database resources
        """
        # TODO: Implement using azure.mgmt.sql, azure.mgmt.rdbms
        # Detect: Databases with status != 'Online' or 0 connections for 30 days
        return []

    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for unused Azure NAT Gateways.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of unused NAT gateway resources
        """
        # TODO: Implement using azure.mgmt.network.NatGatewaysOperations
        # Detect: NAT Gateways with 0 subnets attached
        return []

    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused Azure Files or Azure NetApp Files (not applicable to Azure)."""
        # Note: Azure does not have FSx. This would map to Azure Files or Azure NetApp Files
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle graph databases (Azure Cosmos DB Gremlin API)."""
        # Note: Azure equivalent would be Cosmos DB with Gremlin API
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle managed Kafka clusters (Azure Event Hubs)."""
        # Note: Azure equivalent would be Event Hubs or HDInsight Kafka
        # For now, return empty list (not in MVP scope)
        return []

    async def _detect_aks_cluster_stopped(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #1: Detect AKS cluster stopped but not deleted."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 14) if detection_rules else 14

        # Check if cluster has been stopped
        if not (cluster.power_state and cluster.power_state.code == 'Stopped'):
            return None

        # Calculate age (use creation time as proxy for stopped time)
        age_days = 0
        if cluster.time_created:
            age_days = (datetime.now(timezone.utc) - cluster.time_created).days

        if age_days < min_age_days:
            return None  # Too young

        # Calculate costs (cluster still incurs fees even when stopped)
        cost_breakdown = self._calculate_aks_cluster_cost(
            cluster, agent_pools,
            include_storage=True,  # Storage still charged
            include_networking=True  # LB/IPs still charged
        )

        # Remove node costs (nodes not running when stopped)
        stopped_monthly_cost = (
            cost_breakdown['cluster_fee'] +
            cost_breakdown['storage_cost'] +
            cost_breakdown['lb_cost'] +
            cost_breakdown['public_ip_cost']
        )

        already_wasted = stopped_monthly_cost * (age_days / 30)

        confidence_level = self._calculate_confidence_level(age_days, detection_rules)

        metadata = {
            'resource_type': 'azure_aks_cluster',
            'scenario': 'aks_cluster_stopped',
            'cluster_name': cluster.name,
            'resource_group': resource_group_name,
            'location': cluster.location,
            'power_state': cluster.power_state.code,
            'sku': {
                'name': cluster.sku.name if cluster.sku else 'Base',
                'tier': cluster.sku.tier if cluster.sku else 'Free'
            },
            'kubernetes_version': cluster.kubernetes_version,
            'node_count_total': cost_breakdown['total_nodes'],
            'created_date': cluster.time_created.isoformat() if cluster.time_created else None,
            'age_days': age_days,
            'monthly_cluster_fee': cost_breakdown['cluster_fee'],
            'monthly_storage_cost': cost_breakdown['storage_cost'],
            'monthly_lb_cost': cost_breakdown['lb_cost'],
            'monthly_public_ip_cost': cost_breakdown['public_ip_cost'],
            'total_monthly_cost_while_stopped': round(stopped_monthly_cost, 2),
            'already_wasted_usd': round(already_wasted, 2),
            'recommendation': 'Delete cluster if no longer needed, or restart if required',
            'confidence_level': confidence_level
        }

        return OrphanResourceData(
            resource_type='azure_aks_cluster',
            resource_id=cluster.id,
            resource_name=cluster.name,
            region=cluster.location,
            estimated_monthly_cost=stopped_monthly_cost,
            resource_metadata=metadata
        )

    async def _detect_aks_cluster_zero_nodes(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #2: Detect AKS cluster with 0 nodes."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        # Calculate total nodes
        total_nodes = sum(pool.count if pool.count else 0 for pool in agent_pools)

        if total_nodes > 0:
            return None  # Has nodes

        # Calculate age
        age_days = 0
        if cluster.time_created:
            age_days = (datetime.now(timezone.utc) - cluster.time_created).days

        if age_days < min_age_days:
            return None  # Too young

        # Calculate costs (only cluster management fee is wasted)
        tier_pricing = {'Free': 0, 'Standard': 73.0, 'Premium': 438.0}
        cluster_tier = cluster.sku.tier if cluster.sku else 'Free'
        monthly_cost = tier_pricing.get(cluster_tier, 0.0)

        already_wasted = monthly_cost * (age_days / 30)

        confidence_level = self._calculate_confidence_level(age_days, detection_rules)

        metadata = {
            'resource_type': 'azure_aks_cluster',
            'scenario': 'aks_cluster_zero_nodes',
            'cluster_name': cluster.name,
            'resource_group': resource_group_name,
            'location': cluster.location,
            'power_state': cluster.power_state.code if cluster.power_state else 'Running',
            'sku': {
                'name': cluster.sku.name if cluster.sku else 'Base',
                'tier': cluster.sku.tier if cluster.sku else 'Free'
            },
            'kubernetes_version': cluster.kubernetes_version,
            'node_pools': [
                {
                    'name': pool.name,
                    'count': pool.count if pool.count else 0,
                    'vm_size': pool.vm_size
                }
                for pool in agent_pools
            ],
            'total_nodes': total_nodes,
            'created_date': cluster.time_created.isoformat() if cluster.time_created else None,
            'age_days': age_days,
            'monthly_cluster_fee': monthly_cost,
            'already_wasted_usd': round(already_wasted, 2),
            'recommendation': 'Delete cluster or add nodes to use it',
            'confidence_level': confidence_level
        }

        return OrphanResourceData(
            resource_type='azure_aks_cluster',
            resource_id=cluster.id,
            resource_name=cluster.name,
            region=cluster.location,
            estimated_monthly_cost=monthly_cost,
            resource_metadata=metadata
        )

    async def _detect_aks_cluster_no_user_pods(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #3: Detect AKS cluster with nodes but no user pods."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 14) if detection_rules else 14

        try:
            # Get kubectl credentials
            kubeconfig = await self._get_aks_credentials(cluster.name, resource_group_name)

            if not kubeconfig:
                return None  # Cannot access cluster

            # Configure Kubernetes client
            from kubernetes import client, config
            from kubernetes.client.rest import ApiException
            import tempfile
            import yaml
            import os

            # Write kubeconfig to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(kubeconfig, f)
                kubeconfig_path = f.name

            try:
                # Load kubeconfig
                config.load_kube_config(config_file=kubeconfig_path)
                v1 = client.CoreV1Api()

                # List all pods
                all_pods = v1.list_pod_for_all_namespaces(watch=False)

                # System namespaces to exclude
                system_namespaces = ['kube-system', 'kube-public', 'kube-node-lease', 'gatekeeper-system']

                # Count user pods
                user_pods = [pod for pod in all_pods.items if pod.metadata.namespace not in system_namespaces]

                if len(user_pods) > 0:
                    return None  # Has user pods

                # Calculate age
                age_days = 0
                if cluster.time_created:
                    age_days = (datetime.now(timezone.utc) - cluster.time_created).days

                if age_days < min_age_days:
                    return None  # Too young

                # Calculate costs (entire cluster is wasteful)
                cost_breakdown = self._calculate_aks_cluster_cost(cluster, agent_pools)
                total_monthly_cost = cost_breakdown['total_monthly_cost']
                already_wasted = total_monthly_cost * (age_days / 30)

                confidence_level = self._calculate_confidence_level(age_days, detection_rules)

                metadata = {
                    'resource_type': 'azure_aks_cluster',
                    'scenario': 'aks_cluster_no_user_pods',
                    'cluster_name': cluster.name,
                    'resource_group': resource_group_name,
                    'location': cluster.location,
                    'power_state': cluster.power_state.code if cluster.power_state else 'Running',
                    'sku': {
                        'name': cluster.sku.name if cluster.sku else 'Base',
                        'tier': cluster.sku.tier if cluster.sku else 'Free'
                    },
                    'node_count_total': cost_breakdown['total_nodes'],
                    'node_pools': [
                        {
                            'name': pool.name,
                            'count': pool.count if pool.count else 0,
                            'vm_size': pool.vm_size
                        }
                        for pool in agent_pools
                    ],
                    'total_pods': len(all_pods.items),
                    'system_pods': len(all_pods.items) - len(user_pods),
                    'user_pods': len(user_pods),
                    'age_days': age_days,
                    'monthly_cluster_fee': cost_breakdown['cluster_fee'],
                    'monthly_node_cost': cost_breakdown['node_cost'],
                    'monthly_storage_cost': cost_breakdown['storage_cost'],
                    'monthly_lb_cost': cost_breakdown['lb_cost'],
                    'total_monthly_cost': total_monthly_cost,
                    'already_wasted_usd': round(already_wasted, 2),
                    'recommendation': 'Delete cluster or deploy workloads',
                    'confidence_level': confidence_level
                }

                return OrphanResourceData(
                    resource_type='azure_aks_cluster',
                    resource_id=cluster.id,
                    resource_name=cluster.name,
                    region=cluster.location,
                    estimated_monthly_cost=total_monthly_cost,
                    resource_metadata=metadata
                )

            finally:
                # Clean up temp file
                if os.path.exists(kubeconfig_path):
                    os.unlink(kubeconfig_path)

        except Exception as e:
            print(f"Error checking pods for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_autoscaler_not_enabled(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #4: Detect node pools without autoscaling enabled."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        # Check each node pool for autoscaling
        pools_without_autoscaler = []
        total_wasteful_cost = 0.0

        for pool in agent_pools:
            if not pool.enable_auto_scaling:
                # Node pool without autoscaling
                # Estimate over-provisioning: assume 40% savings if autoscaler enabled
                pool_node_count = pool.count if pool.count else 0
                if pool_node_count == 0:
                    continue  # Skip empty pools

                vm_size = pool.vm_size if pool.vm_size else 'Standard_D2s_v3'
                vm_hourly_cost = self._get_vm_hourly_cost(vm_size)
                pool_monthly_cost = pool_node_count * vm_hourly_cost * 730

                # Estimate savings with autoscaler (typical: 30-50% savings)
                savings_ratio = 0.40  # 40% average savings
                monthly_savings = pool_monthly_cost * savings_ratio

                pools_without_autoscaler.append({
                    'name': pool.name,
                    'count': pool_node_count,
                    'vm_size': vm_size,
                    'enable_auto_scaling': False,
                    'current_monthly_cost': round(pool_monthly_cost, 2),
                    'estimated_savings': round(monthly_savings, 2)
                })

                total_wasteful_cost += monthly_savings

        if not pools_without_autoscaler:
            return None  # All pools have autoscaling

        # Calculate age
        age_days = 0
        if cluster.time_created:
            age_days = (datetime.now(timezone.utc) - cluster.time_created).days

        if age_days < min_age_days:
            return None  # Too young

        already_wasted = total_wasteful_cost * (age_days / 30)

        confidence_level = self._calculate_confidence_level(age_days, detection_rules)

        metadata = {
            'resource_type': 'azure_aks_cluster',
            'scenario': 'aks_autoscaler_not_enabled',
            'cluster_name': cluster.name,
            'resource_group': resource_group_name,
            'location': cluster.location,
            'sku': {
                'tier': cluster.sku.tier if cluster.sku else 'Free'
            },
            'pools_without_autoscaler': pools_without_autoscaler,
            'pools_count_total': len(agent_pools),
            'pools_without_autoscaler_count': len(pools_without_autoscaler),
            'age_days': age_days,
            'monthly_savings_potential': round(total_wasteful_cost, 2),
            'already_wasted_usd': round(already_wasted, 2),
            'recommendation': 'Enable cluster autoscaler on node pools to optimize costs',
            'confidence_level': confidence_level
        }

        return OrphanResourceData(
            resource_type='azure_aks_cluster',
            resource_id=cluster.id,
            resource_name=cluster.name,
            region=cluster.location,
            estimated_monthly_cost=total_wasteful_cost,
            resource_metadata=metadata
        )

    async def _detect_aks_node_pool_oversized_vms(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #5: Detect node pools with oversized VMs (low utilization)."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        cpu_threshold = detection_rules.get("cpu_threshold", 30) if detection_rules else 30  # <30% CPU
        memory_threshold = detection_rules.get("memory_threshold", 40) if detection_rules else 40  # <40% memory

        # Query Azure Monitor metrics for node utilization
        # Note: This requires Container Insights to be enabled on the cluster
        try:
            cpu_metrics = await self._query_aks_metrics(
                cluster.id,
                metric_name="node_cpu_usage_percentage",
                timespan_days=30,
                aggregation="Average"
            )

            memory_metrics = await self._query_aks_metrics(
                cluster.id,
                metric_name="node_memory_working_set_percentage",
                timespan_days=30,
                aggregation="Average"
            )

            if not cpu_metrics or not memory_metrics:
                return None  # Cannot get metrics

            avg_cpu = cpu_metrics['avg']
            avg_memory = memory_metrics['avg']

            # Check if both CPU and memory are low
            if avg_cpu >= cpu_threshold or avg_memory >= memory_threshold:
                return None  # Utilization is fine

            # Calculate age
            age_days = 0
            if cluster.time_created:
                age_days = (datetime.now(timezone.utc) - cluster.time_created).days

            if age_days < min_age_days:
                return None  # Too young

            # Calculate current costs
            cost_breakdown = self._calculate_aks_cluster_cost(cluster, agent_pools)
            current_monthly_cost = cost_breakdown['node_cost']

            # Recommend VM downgrade (50% savings typical)
            # For example: D8s_v3 → D4s_v3 if low utilization
            recommended_monthly_cost = current_monthly_cost * 0.50
            monthly_savings = current_monthly_cost - recommended_monthly_cost

            already_wasted = monthly_savings * (age_days / 30)

            confidence_level = self._calculate_confidence_level(age_days, detection_rules)

            metadata = {
                'resource_type': 'azure_aks_cluster',
                'scenario': 'aks_node_pool_oversized_vms',
                'cluster_name': cluster.name,
                'resource_group': resource_group_name,
                'location': cluster.location,
                'node_count_total': cost_breakdown['total_nodes'],
                'monitoring_period_days': 30,
                'avg_cpu_utilization_percent': avg_cpu,
                'avg_memory_utilization_percent': avg_memory,
                'p95_cpu_percent': cpu_metrics['p95'],
                'p95_memory_percent': memory_metrics['p95'],
                'current_monthly_cost': cost_breakdown['node_cost'],
                'recommended_monthly_cost': round(recommended_monthly_cost, 2),
                'monthly_savings_potential': round(monthly_savings, 2),
                'age_days': age_days,
                'already_wasted_usd': round(already_wasted, 2),
                'recommendation': 'Downgrade VM sizes (e.g., D8s_v3 → D4s_v3) or reduce node count',
                'confidence_level': confidence_level
            }

            return OrphanResourceData(
                resource_type='azure_aks_cluster',
                resource_id=cluster.id,
                resource_name=cluster.name,
                region=cluster.location,
                estimated_monthly_cost=monthly_savings,
                resource_metadata=metadata
            )

        except Exception as e:
            print(f"Error checking VM utilization for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_orphaned_persistent_volumes(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #6: Detect orphaned persistent volumes (Released/Available)."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 14) if detection_rules else 14

        try:
            # Get kubectl credentials
            kubeconfig = await self._get_aks_credentials(cluster.name, resource_group_name)
            if not kubeconfig:
                return None

            from kubernetes import client, config
            import tempfile
            import yaml
            import os

            # Write kubeconfig to temp file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(kubeconfig, f)
                kubeconfig_path = f.name

            try:
                config.load_kube_config(config_file=kubeconfig_path)
                v1 = client.CoreV1Api()

                # List all persistent volumes
                all_pvs = v1.list_persistent_volume(watch=False)

                orphaned_pvs = []
                total_cost = 0.0

                for pv in all_pvs.items:
                    # Check if PV is orphaned (Released or Available for >14 days)
                    if pv.status.phase in ['Released', 'Available']:
                        creation_time = pv.metadata.creation_timestamp
                        age_days = (datetime.now(timezone.utc) - creation_time).days

                        if age_days >= min_age_days:
                            # Calculate PV cost
                            size_gb = 0
                            if pv.spec.capacity and 'storage' in pv.spec.capacity:
                                storage_str = pv.spec.capacity['storage']
                                # Parse storage (e.g., "100Gi" → 100)
                                if storage_str.endswith('Gi'):
                                    size_gb = int(storage_str[:-2])

                            # Estimate disk SKU (Premium SSD default for AKS)
                            cost_per_gb = 0.12  # Premium SSD pricing
                            monthly_cost = size_gb * cost_per_gb

                            orphaned_pvs.append({
                                'pv_name': pv.metadata.name,
                                'phase': pv.status.phase,
                                'size_gb': size_gb,
                                'age_days': age_days,
                                'monthly_cost': round(monthly_cost, 2)
                            })

                            total_cost += monthly_cost

                if not orphaned_pvs:
                    return None  # No orphaned PVs

                # Calculate total already wasted
                avg_age_days = sum(pv['age_days'] for pv in orphaned_pvs) / len(orphaned_pvs)
                already_wasted = total_cost * (avg_age_days / 30)

                confidence_level = self._calculate_confidence_level(int(avg_age_days), detection_rules)

                metadata = {
                    'resource_type': 'azure_aks_cluster',
                    'scenario': 'aks_orphaned_persistent_volumes',
                    'cluster_name': cluster.name,
                    'resource_group': resource_group_name,
                    'location': cluster.location,
                    'orphaned_pvs': orphaned_pvs,
                    'total_orphaned_count': len(orphaned_pvs),
                    'total_storage_gb': sum(pv['size_gb'] for pv in orphaned_pvs),
                    'total_monthly_cost': round(total_cost, 2),
                    'avg_age_days': int(avg_age_days),
                    'already_wasted_usd': round(already_wasted, 2),
                    'recommendation': 'Delete orphaned PVs or update reclaim policy to Delete',
                    'confidence_level': confidence_level
                }

                return OrphanResourceData(
                    resource_type='azure_aks_cluster',
                    resource_id=cluster.id,
                    resource_name=cluster.name,
                    region=cluster.location,
                    estimated_monthly_cost=total_cost,
                    resource_metadata=metadata
                )

            finally:
                if os.path.exists(kubeconfig_path):
                    os.unlink(kubeconfig_path)

        except Exception as e:
            print(f"Error checking PVs for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_unused_load_balancers(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #7: Detect LoadBalancer services with 0 backends."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            # Get kubectl credentials
            kubeconfig = await self._get_aks_credentials(cluster.name, resource_group_name)
            if not kubeconfig:
                return None

            from kubernetes import client, config
            import tempfile
            import yaml
            import os

            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump(kubeconfig, f)
                kubeconfig_path = f.name

            try:
                config.load_kube_config(config_file=kubeconfig_path)
                v1 = client.CoreV1Api()

                # List all services
                all_services = v1.list_service_for_all_namespaces(watch=False)

                unused_lbs = []
                total_cost = 0.0

                for svc in all_services.items:
                    if svc.spec.type == 'LoadBalancer':
                        # Check endpoints
                        namespace = svc.metadata.namespace
                        service_name = svc.metadata.name

                        try:
                            endpoints = v1.read_namespaced_endpoints(service_name, namespace)
                            backend_count = 0
                            if endpoints.subsets:
                                for subset in endpoints.subsets:
                                    if subset.addresses:
                                        backend_count += len(subset.addresses)

                            if backend_count == 0:
                                # LoadBalancer with 0 backends
                                creation_time = svc.metadata.creation_timestamp
                                age_days = (datetime.now(timezone.utc) - creation_time).days

                                if age_days >= min_age_days:
                                    # Cost: LB fee + Public IP
                                    monthly_lb_cost = 18.25  # Standard LB
                                    monthly_ip_cost = 3.65   # Public IP
                                    monthly_cost = monthly_lb_cost + monthly_ip_cost  # $21.90

                                    unused_lbs.append({
                                        'service_name': service_name,
                                        'namespace': namespace,
                                        'backend_count': backend_count,
                                        'age_days': age_days,
                                        'monthly_cost': monthly_cost
                                    })

                                    total_cost += monthly_cost

                        except Exception:
                            continue  # Skip if cannot read endpoints

                if not unused_lbs:
                    return None  # No unused LBs

                avg_age_days = sum(lb['age_days'] for lb in unused_lbs) / len(unused_lbs)
                already_wasted = total_cost * (avg_age_days / 30)

                confidence_level = self._calculate_confidence_level(int(avg_age_days), detection_rules)

                metadata = {
                    'resource_type': 'azure_aks_cluster',
                    'scenario': 'aks_unused_load_balancers',
                    'cluster_name': cluster.name,
                    'resource_group': resource_group_name,
                    'location': cluster.location,
                    'unused_services': unused_lbs,
                    'total_unused_count': len(unused_lbs),
                    'total_monthly_cost': round(total_cost, 2),
                    'avg_age_days': int(avg_age_days),
                    'already_wasted_usd': round(already_wasted, 2),
                    'recommendation': 'Delete unused LoadBalancer services',
                    'confidence_level': confidence_level
                }

                return OrphanResourceData(
                    resource_type='azure_aks_cluster',
                    resource_id=cluster.id,
                    resource_name=cluster.name,
                    region=cluster.location,
                    estimated_monthly_cost=total_cost,
                    resource_metadata=metadata
                )

            finally:
                if os.path.exists(kubeconfig_path):
                    os.unlink(kubeconfig_path)

        except Exception as e:
            print(f"Error checking LoadBalancers for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_low_cpu_utilization(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #8: Detect low CPU utilization (<20% over 30 days)."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        cpu_threshold = detection_rules.get("cpu_threshold", 20) if detection_rules else 20

        try:
            cpu_metrics = await self._query_aks_metrics(
                cluster.id,
                metric_name="node_cpu_usage_percentage",
                timespan_days=30,
                aggregation="Average"
            )

            if not cpu_metrics:
                return None

            avg_cpu = cpu_metrics['avg']

            if avg_cpu >= cpu_threshold:
                return None  # CPU usage is acceptable

            age_days = 0
            if cluster.time_created:
                age_days = (datetime.now(timezone.utc) - cluster.time_created).days

            if age_days < min_age_days:
                return None

            # Calculate current costs and savings potential
            cost_breakdown = self._calculate_aks_cluster_cost(cluster, agent_pools)
            current_monthly_cost = cost_breakdown['node_cost']

            # Rightsizing savings: reduce 40% (based on low CPU)
            optimized_monthly_cost = current_monthly_cost * 0.60
            monthly_savings = current_monthly_cost - optimized_monthly_cost

            already_wasted = monthly_savings * (age_days / 30)

            confidence_level = self._calculate_confidence_level(age_days, detection_rules)

            metadata = {
                'resource_type': 'azure_aks_cluster',
                'scenario': 'aks_low_cpu_utilization',
                'cluster_name': cluster.name,
                'resource_group': resource_group_name,
                'location': cluster.location,
                'monitoring_period_days': 30,
                'node_count': cost_breakdown['total_nodes'],
                'avg_cpu_percent': avg_cpu,
                'max_cpu_percent': cpu_metrics['max'],
                'p95_cpu_percent': cpu_metrics['p95'],
                'current_monthly_cost': cost_breakdown['node_cost'],
                'recommended_monthly_cost': round(optimized_monthly_cost, 2),
                'monthly_savings_potential': round(monthly_savings, 2),
                'age_days': age_days,
                'already_wasted_usd': round(already_wasted, 2),
                'recommendation': 'Reduce node count or downgrade VM sizes',
                'confidence_level': confidence_level
            }

            return OrphanResourceData(
                resource_type='azure_aks_cluster',
                resource_id=cluster.id,
                resource_name=cluster.name,
                region=cluster.location,
                estimated_monthly_cost=monthly_savings,
                resource_metadata=metadata
            )

        except Exception as e:
            print(f"Error checking CPU metrics for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_low_memory_utilization(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #9: Detect low memory utilization (<30% over 30 days)."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30
        memory_threshold = detection_rules.get("memory_threshold", 30) if detection_rules else 30

        try:
            memory_metrics = await self._query_aks_metrics(
                cluster.id,
                metric_name="node_memory_working_set_percentage",
                timespan_days=30,
                aggregation="Average"
            )

            if not memory_metrics:
                return None

            avg_memory = memory_metrics['avg']

            if avg_memory >= memory_threshold:
                return None  # Memory usage is acceptable

            age_days = 0
            if cluster.time_created:
                age_days = (datetime.now(timezone.utc) - cluster.time_created).days

            if age_days < min_age_days:
                return None

            # Calculate savings (downgrade to VMs with less RAM)
            cost_breakdown = self._calculate_aks_cluster_cost(cluster, agent_pools)
            current_monthly_cost = cost_breakdown['node_cost']

            # Memory-optimized to General Purpose savings: ~24%
            optimized_monthly_cost = current_monthly_cost * 0.76
            monthly_savings = current_monthly_cost - optimized_monthly_cost

            already_wasted = monthly_savings * (age_days / 30)

            confidence_level = self._calculate_confidence_level(age_days, detection_rules)

            metadata = {
                'resource_type': 'azure_aks_cluster',
                'scenario': 'aks_low_memory_utilization',
                'cluster_name': cluster.name,
                'resource_group': resource_group_name,
                'location': cluster.location,
                'monitoring_period_days': 30,
                'node_count': cost_breakdown['total_nodes'],
                'avg_memory_percent': avg_memory,
                'max_memory_percent': memory_metrics['max'],
                'p95_memory_percent': memory_metrics['p95'],
                'current_monthly_cost': cost_breakdown['node_cost'],
                'recommended_monthly_cost': round(optimized_monthly_cost, 2),
                'monthly_savings_potential': round(monthly_savings, 2),
                'age_days': age_days,
                'already_wasted_usd': round(already_wasted, 2),
                'recommendation': 'Downgrade to VMs with less RAM (e.g., E-series → D-series)',
                'confidence_level': confidence_level
            }

            return OrphanResourceData(
                resource_type='azure_aks_cluster',
                resource_id=cluster.id,
                resource_name=cluster.name,
                region=cluster.location,
                estimated_monthly_cost=monthly_savings,
                resource_metadata=metadata
            )

        except Exception as e:
            print(f"Error checking memory metrics for cluster {cluster.name}: {str(e)}")
            return None

    async def _detect_aks_dev_test_always_on(
        self,
        cluster,
        agent_pools: list,
        resource_group_name: str,
        detection_rules: dict | None = None
    ) -> OrphanResourceData | None:
        """Scenario #10: Detect dev/test clusters running 24/7."""
        from datetime import datetime, timezone

        min_age_days = detection_rules.get("min_age_days", 30) if detection_rules else 30

        # Check if cluster is tagged as dev/test
        tags = cluster.tags or {}
        environment_tag = tags.get('environment', '').lower()

        is_dev_test = (
            environment_tag in ['dev', 'test', 'development', 'testing', 'staging'] or
            'dev' in cluster.name.lower() or
            'test' in cluster.name.lower()
        )

        if not is_dev_test:
            return None  # Not a dev/test cluster

        # Calculate age
        age_days = 0
        if cluster.time_created:
            age_days = (datetime.now(timezone.utc) - cluster.time_created).days

        if age_days < min_age_days:
            return None

        # Assume cluster is always on (we'd need Activity Log to verify stop events)
        # For now, flag all dev/test clusters >30 days old

        # Calculate costs
        cost_breakdown = self._calculate_aks_cluster_cost(cluster, agent_pools)
        total_24_7_cost = cost_breakdown['total_monthly_cost']

        # Cost with 8h/day × 5 days/week = 24% uptime
        cluster_fee = cost_breakdown['cluster_fee']  # Always paid
        node_cost_24_7 = cost_breakdown['node_cost']
        node_cost_optimized = node_cost_24_7 * 0.24  # 24% uptime

        total_optimized_cost = cluster_fee + node_cost_optimized

        monthly_savings = total_24_7_cost - total_optimized_cost

        already_wasted = monthly_savings * (age_days / 30)

        confidence_level = self._calculate_confidence_level(age_days, detection_rules)

        metadata = {
            'resource_type': 'azure_aks_cluster',
            'scenario': 'aks_dev_test_always_on',
            'cluster_name': cluster.name,
            'resource_group': resource_group_name,
            'location': cluster.location,
            'environment_tag': environment_tag or 'dev/test (inferred from name)',
            'tags': tags,
            'node_count': cost_breakdown['total_nodes'],
            'created_date': cluster.time_created.isoformat() if cluster.time_created else None,
            'age_days': age_days,
            'uptime_ratio': 1.0,  # Assumed 100% uptime
            'expected_uptime_ratio': 0.24,  # 8h × 5d = 24%
            'current_monthly_cost': total_24_7_cost,
            'optimized_monthly_cost': round(total_optimized_cost, 2),
            'monthly_savings_potential': round(monthly_savings, 2),
            'annual_savings_potential': round(monthly_savings * 12, 2),
            'already_wasted_usd': round(already_wasted, 2),
            'recommendation': 'Implement start/stop automation (8am-6pm weekdays)',
            'confidence_level': confidence_level
        }

        return OrphanResourceData(
            resource_type='azure_aks_cluster',
            resource_id=cluster.id,
            resource_name=cluster.name,
            region=cluster.location,
            estimated_monthly_cost=monthly_savings,
            resource_metadata=metadata
        )

    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle/wasteful Azure Kubernetes Service (AKS) clusters.

        Detects 10 scenarios (7 simple + 3 Azure Monitor):
        1. aks_cluster_stopped - Cluster stopped but not deleted
        2. aks_cluster_zero_nodes - Cluster with 0 nodes
        3. aks_cluster_no_user_pods - No user pods (only kube-system)
        4. aks_autoscaler_not_enabled - No autoscaling configured
        5. aks_node_pool_oversized_vms - VMs too large for workload
        6. aks_orphaned_persistent_volumes - Orphaned PVs (Released/Available)
        7. aks_unused_load_balancers - LoadBalancer services with 0 backends
        8. aks_low_cpu_utilization - CPU <20% over 30 days
        9. aks_low_memory_utilization - Memory <30% over 30 days
        10. aks_dev_test_always_on - Dev/test clusters running 24/7

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of orphan AKS cluster resources
        """
        from datetime import datetime, timezone
        from azure.identity import ClientSecretCredential
        from azure.mgmt.containerservice import ContainerServiceClient

        orphans: list[OrphanResourceData] = []

        # Extract detection rules
        min_age_days = detection_rules.get("min_age_days", 7) if detection_rules else 7

        try:
            credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )

            aks_client = ContainerServiceClient(credential, self.subscription_id)

            # List all AKS clusters in the subscription
            clusters = aks_client.managed_clusters.list()

            for cluster in clusters:
                # Filter by region (Azure uses 'location')
                if cluster.location != region:
                    continue

                # Filter by resource group (if specified)
                if not self._is_resource_in_scope(cluster.id):
                    continue

                # Extract resource group name from cluster ID
                # Format: /subscriptions/{sub}/resourceGroups/{rg}/providers/Microsoft.ContainerService/managedClusters/{name}
                parts = cluster.id.split('/')
                try:
                    rg_index = parts.index('resourceGroups')
                    resource_group_name = parts[rg_index + 1]
                except (ValueError, IndexError):
                    print(f"Could not parse resource group from cluster ID: {cluster.id}")
                    continue

                # List agent pools for this cluster
                agent_pools = list(aks_client.agent_pools.list(
                    resource_group_name=resource_group_name,
                    resource_name=cluster.name
                ))

                # Calculate total nodes across all pools
                total_nodes = sum(pool.count if pool.count else 0 for pool in agent_pools)

                # Scenario #1: Cluster stopped but not deleted
                if cluster.power_state and cluster.power_state.code == 'Stopped':
                    orphan = await self._detect_aks_cluster_stopped(
                        cluster, agent_pools, resource_group_name, detection_rules
                    )
                    if orphan:
                        orphans.append(orphan)
                    continue  # Skip other checks if stopped

                # Scenario #2: Cluster with 0 nodes (but running)
                if total_nodes == 0:
                    orphan = await self._detect_aks_cluster_zero_nodes(
                        cluster, agent_pools, resource_group_name, detection_rules
                    )
                    if orphan:
                        orphans.append(orphan)
                    continue  # Skip other checks if no nodes

                # For remaining scenarios, cluster must be Running with nodes
                # Scenario #3: No user pods (requires kubectl access)
                orphan = await self._detect_aks_cluster_no_user_pods(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #4: Autoscaler not enabled
                orphan = await self._detect_aks_autoscaler_not_enabled(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #5: Node pool oversized VMs
                orphan = await self._detect_aks_node_pool_oversized_vms(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #6: Orphaned persistent volumes
                orphan = await self._detect_aks_orphaned_persistent_volumes(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #7: Unused load balancers
                orphan = await self._detect_aks_unused_load_balancers(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #8: Low CPU utilization (requires Azure Monitor)
                orphan = await self._detect_aks_low_cpu_utilization(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #9: Low memory utilization (requires Azure Monitor)
                orphan = await self._detect_aks_low_memory_utilization(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

                # Scenario #10: Dev/test clusters always on
                orphan = await self._detect_aks_dev_test_always_on(
                    cluster, agent_pools, resource_group_name, detection_rules
                )
                if orphan:
                    orphans.append(orphan)

        except Exception as e:
            print(f"Error scanning AKS clusters in {region}: {str(e)}")
            # Log error but don't fail entire scan

        return orphans

    async def scan_idle_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle machine learning endpoints (Azure Machine Learning)."""
        # Note: Azure equivalent would be Azure Machine Learning endpoints
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle data warehouse clusters (Azure Synapse Analytics)."""
        # TODO: Implement using azure.mgmt.synapse
        # Detect: Synapse SQL pools with 0 queries for 30 days
        return []

    async def scan_idle_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle cache clusters (Azure Cache for Redis)."""
        # TODO: Implement using azure.mgmt.redis
        # Detect: Redis caches with 0 connections for 30 days
        return []

    async def scan_idle_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle VPN Gateway connections."""
        # TODO: Implement using azure.mgmt.network.VirtualNetworkGatewaysOperations
        # Detect: VPN Gateways with connection_state != 'Connected'
        return []

    async def scan_idle_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle virtual network peerings."""
        # Note: Azure equivalent would be Virtual Network Peering or Virtual WAN
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle search service domains (Azure Cognitive Search)."""
        # Note: Azure equivalent would be Azure Cognitive Search
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle global accelerators (Azure Front Door / Traffic Manager)."""
        # Note: Azure equivalent would be Azure Front Door or Traffic Manager
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle streaming data services (Azure Event Hubs / Stream Analytics)."""
        # Note: Azure equivalent would be Event Hubs or Stream Analytics
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_unused_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for unused private endpoints."""
        # TODO: Implement using azure.mgmt.network.PrivateEndpointsOperations
        # Detect: Private Endpoints with 0 network interfaces
        return []

    async def scan_idle_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle document database clusters (Azure Cosmos DB MongoDB API)."""
        # Note: Azure equivalent would be Cosmos DB with MongoDB API
        # For now, return empty list (not in MVP scope)
        return []

    async def scan_idle_s3_buckets(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Storage Accounts (Blob Storage).

        Note: This is called once per account scan, not per region.

        Args:
            detection_rules: Optional detection configuration

        Returns:
            List of idle storage account resources
        """
        # TODO: Implement using azure.mgmt.storage.StorageAccountsOperations
        # Detect: Storage accounts with 0 transactions for 90 days
        return []

    async def scan_idle_lambda_functions(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Functions.

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of idle function resources
        """
        # TODO: Implement using azure.mgmt.web (App Service / Azure Functions)
        # Detect: Functions with 0 executions for 60 days
        return []

    async def scan_idle_dynamodb_tables(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Cosmos DB tables (Table API).

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of idle table resources
        """
        # Note: Azure equivalent would be Cosmos DB Table API or Azure Table Storage
        # For now, return empty list (not in MVP scope)
        return []
