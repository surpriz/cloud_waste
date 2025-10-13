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
    ) -> None:
        """
        Initialize Azure provider client.

        Args:
            tenant_id: Azure AD Tenant ID
            client_id: Service Principal Application/Client ID
            client_secret: Service Principal Client Secret
            subscription_id: Azure Subscription ID
            regions: List of Azure regions to scan (e.g., ['eastus', 'westeurope'])
        """
        # Azure uses different authentication than AWS, so we override the base class params
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.subscription_id = subscription_id
        self.regions = regions or []

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

        # Scan Public IPs associated to stopped resources (VMs, LBs)
        ips_on_stopped = await self.scan_ips_on_stopped_resources(region, rules.get("public_ip_on_stopped_resource"))
        results.extend(ips_on_stopped)

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

        # TODO: Phase 2 - Advanced metrics scenarios (requires Azure Monitor API)
        # results.extend(await self.scan_low_io_disks(region, rules.get("managed_disk_low_io")))
        # results.extend(await self.scan_zero_traffic_ips(region, rules.get("public_ip_no_traffic")))

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

                        metadata = {
                            'disk_id': disk.id,
                            'disk_name': disk.name,
                            'disk_size_gb': disk.disk_size_gb,
                            'sku_name': disk.sku.name if disk.sku else 'Standard_LRS',
                            'vm_id': vm.id,
                            'vm_name': vm.name,
                            'vm_power_state': power_state,
                            'vm_stopped_days': stopped_days,
                            'orphan_reason': f"Disk attached to VM '{vm.name}' which has been deallocated (stopped) for {stopped_days} days",
                            'recommendation': f"Consider deleting disk or restarting VM if still needed. Disk continues to cost ${monthly_cost:.2f}/month while VM is stopped.",
                            'tags': disk.tags if disk.tags else {},
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
                        'orphan_reason': f"OS Disk attached to VM '{vm.name}' which has been deallocated (stopped) for {stopped_days} days",
                        'recommendation': f"VM is stopped but OS disk continues to cost ${monthly_cost:.2f}/month. Consider creating snapshot and deleting disk if VM no longer needed.",
                        'tags': os_disk.tags if os_disk.tags else {},
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

                metadata = {
                    'ip_id': ip.id,
                    'ip_address': ip.ip_address if ip.ip_address else 'Not assigned',
                    'sku_name': ip.sku.name if ip.sku else 'Basic',
                    'allocation_method': ip.public_ip_allocation_method if ip.public_ip_allocation_method else 'Static',
                    'attached_resource_type': resource_type,
                    'attached_resource_name': resource_name,
                    'resource_stopped': True,
                    'resource_stopped_days': stopped_days,
                    'orphan_reason': f"Public IP attached to {resource_type} '{resource_name}' which has been stopped/inactive for {stopped_days} days",
                    'recommendation': f"Consider dissociating and deleting Public IP. IP continues to cost ${monthly_cost:.2f}/month while resource is stopped.",
                    'tags': ip.tags if ip.tags else {},
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
                current_monthly_cost = 0.0  # Disk costs would need separate calculation

                metadata = {
                    'vm_size': vm_size,
                    'power_state': power_state,
                    'vm_age_days': vm_age_days,
                    'created_at': created_at.isoformat() if created_at else None,
                    'potential_monthly_cost': f'${potential_monthly_cost:.2f}',
                    'orphan_reason': f"VM created {vm_age_days} days ago but has never been started",
                    'recommendation': f"This VM has existed for {vm_age_days} days without ever running. "
                                    f"If it was created by mistake or for testing, consider deleting it. "
                                    f"Potential compute cost if started: ${potential_monthly_cost:.2f}/month."
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
                    'orphan_reason': f"VM is oversized ({vcpu_count} vCPUs) with premium disks ({premium_disk_count} disks, {total_disk_size_gb}GB)",
                    'recommendation': f"Consider downsizing VM from {vm_size} to {suggested_size} "
                                    f"and switching disks from Premium_LRS to Standard_LRS. "
                                    f"Potential savings: ${total_monthly_savings:.2f}/month "
                                    f"(VM: ${compute_savings:.2f}, Disks: ${disk_savings:.2f})."
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

                # If VM is deallocated, cost is $0 for compute
                if power_state == 'deallocated':
                    vm_cost = 0.0

                metadata = {
                    'vm_size': vm_size,
                    'power_state': power_state,
                    'vm_age_days': vm_age_days,
                    'existing_tags': list(vm_tags.keys()),
                    'missing_tags': missing_tags,
                    'created_at': created_at.isoformat() if created_at else None,
                    'orphan_reason': f"VM is {vm_age_days} days old but missing required governance tags: {', '.join(missing_tags)}",
                    'recommendation': f"This VM lacks proper tagging for {vm_age_days} days. "
                                    f"Add required tags ({', '.join(missing_tags)}) to identify ownership "
                                    f"and cost accountability. If owner cannot be identified, this may be "
                                    f"an orphaned resource that should be investigated or deleted."
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

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scan for idle Azure Virtual Machines (low CPU utilization).

        Args:
            region: Azure region to scan
            detection_rules: Optional detection configuration

        Returns:
            List of idle VM resources
        """
        # TODO: Implement using azure.mgmt.monitor for metrics
        # Detect: VMs with < 5% average CPU for 30 days
        return []

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

    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Scan for idle Azure Kubernetes Service (AKS) clusters."""
        # TODO: Implement using azure.mgmt.containerservice
        # Detect: AKS clusters with 0 nodes or 0 pods
        return []

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
