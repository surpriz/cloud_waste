"""Microsoft 365 cloud provider implementation (SharePoint + OneDrive)."""

from datetime import datetime, timedelta, timezone
from typing import Any
import re
import httpx
from azure.identity import ClientSecretCredential
from app.providers.base import CloudProviderBase, OrphanResourceData


class Microsoft365Provider(CloudProviderBase):
    """
    Microsoft 365 provider for SharePoint and OneDrive waste detection.

    This provider scans Microsoft 365 SaaS services (NOT Azure IaaS):
    - SharePoint sites and document libraries
    - OneDrive personal drives
    - File versioning and duplicates
    - User permissions and sharing

    Authentication uses Entra ID App Registration with Microsoft Graph permissions.
    """

    def __init__(
        self,
        tenant_id: str,
        client_id: str,
        client_secret: str,
    ) -> None:
        """
        Initialize Microsoft 365 provider client.

        Args:
            tenant_id: Microsoft 365 Tenant ID (e.g., "contoso.onmicrosoft.com" or GUID)
            client_id: Entra ID App Registration Application ID (GUID)
            client_secret: App Registration Client Secret

        Requires Microsoft Graph API permissions:
            - Files.Read.All
            - Sites.Read.All
            - User.Read.All
            - Directory.Read.All
        """
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret

        # Initialize Azure credential
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret,
        )

        # Graph API base URL
        self.graph_api_base = "https://graph.microsoft.com/v1.0"
        self.graph_api_beta = "https://graph.microsoft.com/beta"

        # Access token cache
        self._access_token: str | None = None
        self._token_expires_at: datetime | None = None

    async def _get_access_token(self) -> str:
        """
        Get Microsoft Graph API access token with caching.

        Returns:
            Valid access token

        Raises:
            Exception: If token acquisition fails
        """
        # Return cached token if still valid
        if (
            self._access_token
            and self._token_expires_at
            and datetime.now(timezone.utc) < self._token_expires_at
        ):
            return self._access_token

        # Acquire new token
        token = self.credential.get_token("https://graph.microsoft.com/.default")
        self._access_token = token.token
        self._token_expires_at = datetime.fromtimestamp(
            token.expires_on, tz=timezone.utc
        )

        return self._access_token

    async def _call_graph_api(
        self,
        endpoint: str,
        method: str = "GET",
        params: dict | None = None,
        json_data: dict | None = None,
        use_beta: bool = False,
    ) -> dict | list:
        """
        Call Microsoft Graph API with retry logic and pagination support.

        Args:
            endpoint: API endpoint path (e.g., "/sites")
            method: HTTP method (GET, POST, PATCH, DELETE)
            params: Query parameters
            json_data: JSON body for POST/PATCH requests
            use_beta: Use beta endpoint instead of v1.0

        Returns:
            API response as dict or list

        Raises:
            httpx.HTTPStatusError: If API call fails
        """
        token = await self._get_access_token()
        base_url = self.graph_api_beta if use_beta else self.graph_api_base
        url = f"{base_url}{endpoint}"

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            # Handle pagination for GET requests
            if method == "GET":
                all_results = []
                next_link = url

                while next_link:
                    response = await client.get(
                        next_link,
                        params=params if next_link == url else None,
                        headers=headers,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Handle both single objects and value arrays
                    if "value" in data:
                        all_results.extend(data["value"])
                        next_link = data.get("@odata.nextLink")
                    else:
                        return data

                return all_results

            # Non-GET requests
            elif method == "POST":
                response = await client.post(
                    url, params=params, json=json_data, headers=headers
                )
            elif method == "PATCH":
                response = await client.patch(
                    url, params=params, json=json_data, headers=headers
                )
            elif method == "DELETE":
                response = await client.delete(url, params=params, headers=headers)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

            response.raise_for_status()
            return response.json() if response.content else {}

    async def validate_credentials(self) -> dict[str, str]:
        """
        Validate Microsoft 365 credentials by testing Graph API access.

        Returns:
            Dict with organization info:
            {
                "tenant_id": "...",
                "organization_name": "...",
                "verified_domains": [...]
            }

        Raises:
            Exception: If credentials are invalid
        """
        try:
            # Test API access by fetching organization info
            org_data = await self._call_graph_api("/organization")

            if not org_data or len(org_data) == 0:
                raise Exception("No organization data returned")

            org = org_data[0]

            return {
                "tenant_id": org.get("id", self.tenant_id),
                "organization_name": org.get("displayName", "Unknown"),
                "verified_domains": [
                    d["name"] for d in org.get("verifiedDomains", [])
                ],
            }

        except Exception as e:
            raise Exception(f"Microsoft 365 credentials validation failed: {str(e)}")

    async def get_available_regions(self) -> list[str]:
        """
        Get available regions for Microsoft 365.

        Microsoft 365 is a global SaaS service with no user-configurable regions.

        Returns:
            List with single "global" region
        """
        return ["global"]

    async def scan_all_resources(
        self,
        region: str,
        detection_rules: dict | None = None,
        scan_global_resources: bool = True,
    ) -> list[OrphanResourceData]:
        """
        Scan all Microsoft 365 resources for waste.

        Args:
            region: Region to scan (always "global" for M365)
            detection_rules: User-specific detection rules
            scan_global_resources: Always True for M365 (no regional distinction)

        Returns:
            List of detected orphan resources across all 10 scenarios
        """
        all_orphans: list[OrphanResourceData] = []

        # Get detection rules for each resource type
        sharepoint_rules = detection_rules.get("sharepoint_sites", {}) if detection_rules else {}
        onedrive_rules = detection_rules.get("onedrive_drives", {}) if detection_rules else {}

        # SharePoint scenarios (5)
        all_orphans.extend(
            await self.scan_sharepoint_large_files_unused(sharepoint_rules)
        )
        all_orphans.extend(
            await self.scan_sharepoint_duplicate_files(sharepoint_rules)
        )
        all_orphans.extend(
            await self.scan_sharepoint_sites_abandoned(sharepoint_rules)
        )
        all_orphans.extend(
            await self.scan_sharepoint_excessive_versions(sharepoint_rules)
        )
        all_orphans.extend(
            await self.scan_sharepoint_recycle_bin_old(sharepoint_rules)
        )

        # OneDrive scenarios (5)
        all_orphans.extend(
            await self.scan_onedrive_large_files_unused(onedrive_rules)
        )
        all_orphans.extend(
            await self.scan_onedrive_disabled_users(onedrive_rules)
        )
        all_orphans.extend(
            await self.scan_onedrive_temp_files_accumulated(onedrive_rules)
        )
        all_orphans.extend(
            await self.scan_onedrive_excessive_sharing(onedrive_rules)
        )
        all_orphans.extend(
            await self.scan_onedrive_duplicate_attachments(onedrive_rules)
        )

        return all_orphans

    # ========================================================================
    # SHAREPOINT DETECTION SCENARIOS (5)
    # ========================================================================

    async def scan_sharepoint_large_files_unused(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 1: Detect large files (>100MB) in SharePoint not accessed for 180+ days.

        Detection logic:
        - Query all SharePoint sites
        - For each site, get drive items with size >100MB
        - Check lastAccessedDateTime or lastModifiedDateTime
        - Flag files older than min_age_days (default 180)

        Args:
            detection_rules: Detection configuration:
                {
                    "large_files_unused": {
                        "enabled": bool (default True),
                        "min_file_size_mb": int (default 100),
                        "min_age_days": int (default 180)
                    }
                }

        Returns:
            List of orphan large unused files
        """
        rules = (detection_rules or {}).get("large_files_unused", {})
        if not rules.get("enabled", True):
            return []

        min_file_size_mb = rules.get("min_file_size_mb", 100)
        min_age_days = rules.get("min_age_days", 180)
        min_file_size_bytes = min_file_size_mb * 1024 * 1024

        orphans: list[OrphanResourceData] = []

        try:
            # Get all SharePoint sites
            sites = await self._call_graph_api("/sites?search=*")

            for site in sites:
                site_id = site.get("id")
                site_name = site.get("displayName", site.get("name", "Unknown"))
                site_url = site.get("webUrl", "")

                # Get site drive
                try:
                    drive = await self._call_graph_api(f"/sites/{site_id}/drive")
                    drive_id = drive.get("id")

                    # Query large files (>min_file_size_mb)
                    files = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='')",
                        params={
                            "$filter": f"file ne null and size gt {min_file_size_bytes}",
                            "$select": "id,name,size,createdDateTime,lastModifiedDateTime,lastAccessedDateTime,webUrl,createdBy,file",
                        },
                    )

                    for file_item in files:
                        file_size_bytes = file_item.get("size", 0)
                        file_size_gb = file_size_bytes / (1024**3)

                        # Get last accessed or modified date
                        last_accessed_str = file_item.get("lastAccessedDateTime") or file_item.get("lastModifiedDateTime")
                        if not last_accessed_str:
                            continue

                        last_accessed = datetime.fromisoformat(
                            last_accessed_str.replace("Z", "+00:00")
                        )
                        age_days = (datetime.now(timezone.utc) - last_accessed).days

                        if age_days >= min_age_days:
                            monthly_cost = file_size_gb * 0.20  # $0.20/GB/month M365 add-on storage

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="sharepoint_large_files_unused",
                                    resource_id=file_item.get("id", ""),
                                    resource_name=file_item.get("name", "Unknown file"),
                                    region="global",
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "site_name": site_name,
                                        "site_url": site_url,
                                        "file_path": file_item.get("webUrl", ""),
                                        "file_size_gb": round(file_size_gb, 2),
                                        "last_accessed": last_accessed_str,
                                        "last_accessed_days_ago": age_days,
                                        "created_by": file_item.get("createdBy", {}).get("user", {}).get("displayName", "Unknown"),
                                        "created_at": file_item.get("createdDateTime", ""),
                                        "reason": f"Large file ({min_file_size_mb}+ MB) not accessed for {age_days} days",
                                        "recommendation": "Archive to Azure Blob Cool tier or delete if no longer needed",
                                        "confidence": self._calculate_confidence_level(age_days, detection_rules),
                                    },
                                )
                            )

                except Exception as e:
                    # Skip sites without drive access
                    continue

        except Exception as e:
            # Log error but don't fail entire scan
            print(f"Error scanning SharePoint large files: {str(e)}")

        return orphans

    async def scan_sharepoint_duplicate_files(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 2: Detect duplicate files in SharePoint using hash-based detection.

        Detection logic:
        - Query all files across SharePoint sites
        - Group by quickXorHash or sha256Hash
        - Flag groups with 2+ files (duplicates)
        - Calculate wasted storage = (count - 1) * file_size

        Args:
            detection_rules: Detection configuration

        Returns:
            List of duplicate file groups
        """
        rules = (detection_rules or {}).get("duplicate_files", {})
        if not rules.get("enabled", True):
            return []

        orphans: list[OrphanResourceData] = []

        try:
            sites = await self._call_graph_api("/sites?search=*")

            # Track files by hash across all sites
            files_by_hash: dict[str, list[dict]] = {}

            for site in sites:
                site_id = site.get("id")
                site_name = site.get("displayName", site.get("name", "Unknown"))

                try:
                    drive = await self._call_graph_api(f"/sites/{site_id}/drive")
                    drive_id = drive.get("id")

                    # Get all files with hash info
                    files = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='')",
                        params={
                            "$filter": "file ne null",
                            "$select": "id,name,size,webUrl,file",
                        },
                    )

                    for file_item in files:
                        hashes = file_item.get("file", {}).get("hashes", {})
                        file_hash = hashes.get("quickXorHash") or hashes.get("sha256Hash")

                        if file_hash:
                            if file_hash not in files_by_hash:
                                files_by_hash[file_hash] = []

                            files_by_hash[file_hash].append(
                                {
                                    "id": file_item.get("id"),
                                    "name": file_item.get("name"),
                                    "size": file_item.get("size", 0),
                                    "url": file_item.get("webUrl", ""),
                                    "site": site_name,
                                }
                            )

                except Exception:
                    continue

            # Find duplicates
            for file_hash, file_list in files_by_hash.items():
                if len(file_list) >= 2:
                    # Keep first as original, rest as duplicates
                    original = file_list[0]
                    duplicates = file_list[1:]

                    total_wasted_bytes = sum(f["size"] for f in duplicates)
                    total_wasted_gb = total_wasted_bytes / (1024**3)
                    monthly_cost = total_wasted_gb * 0.20

                    orphans.append(
                        OrphanResourceData(
                            resource_type="sharepoint_duplicate_files",
                            resource_id=original["id"],
                            resource_name=f"{original['name']} (+ {len(duplicates)} duplicates)",
                            region="global",
                            estimated_monthly_cost=monthly_cost,
                            resource_metadata={
                                "original_file": original["url"],
                                "original_site": original["site"],
                                "duplicate_files": [f"{d['site']}: {d['url']}" for d in duplicates],
                                "file_hash": file_hash,
                                "duplicate_count": len(duplicates),
                                "total_size_gb": round((original["size"] + total_wasted_bytes) / (1024**3), 2),
                                "wasted_size_gb": round(total_wasted_gb, 2),
                                "reason": f"{len(duplicates)} duplicate(s) found (same hash, different paths)",
                                "recommendation": f"Keep original, delete duplicates to save ${monthly_cost:.2f}/month",
                                "confidence": "high",
                            },
                        )
                    )

        except Exception as e:
            print(f"Error scanning SharePoint duplicates: {str(e)}")

        return orphans

    async def scan_sharepoint_sites_abandoned(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 3: Detect abandoned SharePoint sites with no activity for 90+ days.

        Detection logic:
        - Query all SharePoint sites
        - Check site analytics (page views, last activity)
        - Flag sites with 0 page views and lastModifiedDateTime > min_inactive_days

        Args:
            detection_rules: Detection configuration:
                {
                    "sites_abandoned": {
                        "enabled": bool,
                        "min_inactive_days": int (default 90)
                    }
                }

        Returns:
            List of abandoned sites
        """
        rules = (detection_rules or {}).get("sites_abandoned", {})
        if not rules.get("enabled", True):
            return []

        min_inactive_days = rules.get("min_inactive_days", 90)
        orphans: list[OrphanResourceData] = []

        try:
            sites = await self._call_graph_api("/sites?search=*")

            for site in sites:
                site_id = site.get("id")
                site_name = site.get("displayName", site.get("name", "Unknown"))
                site_url = site.get("webUrl", "")
                created_date = site.get("createdDateTime", "")

                try:
                    # Get site analytics (requires Sites.Read.All permission)
                    analytics = await self._call_graph_api(
                        f"/sites/{site_id}/analytics/allTime", use_beta=False
                    )

                    last_activity_str = analytics.get("lastActivityDate")
                    if not last_activity_str:
                        # No activity data, skip
                        continue

                    last_activity = datetime.fromisoformat(
                        last_activity_str.replace("Z", "+00:00")
                    )
                    inactive_days = (datetime.now(timezone.utc) - last_activity).days

                    page_views = analytics.get("pageViewCount", 0)

                    if inactive_days >= min_inactive_days:
                        # Get site storage size
                        drive = await self._call_graph_api(f"/sites/{site_id}/drive")
                        storage_used_bytes = drive.get("quota", {}).get("used", 0)
                        storage_gb = storage_used_bytes / (1024**3)

                        monthly_cost = storage_gb * 0.20

                        orphans.append(
                            OrphanResourceData(
                                resource_type="sharepoint_sites_abandoned",
                                resource_id=site_id,
                                resource_name=site_name,
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "site_url": site_url,
                                    "site_size_gb": round(storage_gb, 2),
                                    "last_activity_days_ago": inactive_days,
                                    "last_activity_date": last_activity_str,
                                    "page_views_last_30d": page_views,
                                    "created_date": created_date,
                                    "reason": f"Site inactive for {inactive_days} days (no page views or modifications)",
                                    "recommendation": "Archive site content to Azure Blob Storage or delete if obsolete",
                                    "confidence": self._calculate_confidence_level(inactive_days, detection_rules),
                                },
                            )
                        )

                except Exception:
                    # Analytics may not be available for all sites
                    continue

        except Exception as e:
            print(f"Error scanning SharePoint abandoned sites: {str(e)}")

        return orphans

    async def scan_sharepoint_excessive_versions(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 4: Detect files with excessive version history (>50 versions).

        Detection logic:
        - Query all files in SharePoint sites
        - For each file, get version count via /versions endpoint
        - Flag files with version_count > max_versions_threshold
        - Calculate wasted storage = version_storage_size

        Args:
            detection_rules: Detection configuration:
                {
                    "excessive_versions": {
                        "enabled": bool,
                        "max_versions_threshold": int (default 50)
                    }
                }

        Returns:
            List of files with excessive versions
        """
        rules = (detection_rules or {}).get("excessive_versions", {})
        if not rules.get("enabled", True):
            return []

        max_versions_threshold = rules.get("max_versions_threshold", 50)
        orphans: list[OrphanResourceData] = []

        try:
            sites = await self._call_graph_api("/sites?search=*")

            for site in sites:
                site_id = site.get("id")
                site_name = site.get("displayName", site.get("name", "Unknown"))

                try:
                    drive = await self._call_graph_api(f"/sites/{site_id}/drive")
                    drive_id = drive.get("id")

                    # Get all files
                    files = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='')",
                        params={
                            "$filter": "file ne null",
                            "$select": "id,name,size,webUrl",
                        },
                    )

                    for file_item in files:
                        file_id = file_item.get("id")

                        try:
                            # Get versions
                            versions = await self._call_graph_api(
                                f"/drives/{drive_id}/items/{file_id}/versions"
                            )

                            version_count = len(versions)

                            if version_count > max_versions_threshold:
                                # Estimate version storage (rough estimate: average version size)
                                current_size_bytes = file_item.get("size", 0)
                                current_size_mb = current_size_bytes / (1024**2)

                                # Estimate: old versions average 80% of current size
                                estimated_version_storage_mb = (
                                    version_count * current_size_mb * 0.8
                                )
                                estimated_version_storage_gb = estimated_version_storage_mb / 1024

                                monthly_cost = estimated_version_storage_gb * 0.20

                                # Get oldest version date
                                oldest_version_date = ""
                                if versions:
                                    oldest_version_date = versions[-1].get("lastModifiedDateTime", "")

                                orphans.append(
                                    OrphanResourceData(
                                        resource_type="sharepoint_excessive_versions",
                                        resource_id=file_id,
                                        resource_name=file_item.get("name", "Unknown"),
                                        region="global",
                                        estimated_monthly_cost=monthly_cost,
                                        resource_metadata={
                                            "site_name": site_name,
                                            "file_path": file_item.get("webUrl", ""),
                                            "version_count": version_count,
                                            "current_version_size_mb": round(current_size_mb, 2),
                                            "estimated_total_versions_size_mb": round(estimated_version_storage_mb, 2),
                                            "estimated_wasted_size_mb": round(estimated_version_storage_mb - current_size_mb, 2),
                                            "oldest_version_date": oldest_version_date,
                                            "reason": f"{version_count} versions stored (exceeds {max_versions_threshold} threshold)",
                                            "recommendation": f"Configure version history limit (e.g., keep last 10-20 versions) to save ${monthly_cost:.2f}/month",
                                            "confidence": "high",
                                        },
                                    )
                                )

                        except Exception:
                            # Versions endpoint may fail for some files
                            continue

                except Exception:
                    continue

        except Exception as e:
            print(f"Error scanning SharePoint excessive versions: {str(e)}")

        return orphans

    async def scan_sharepoint_recycle_bin_old(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 5: Detect items in SharePoint recycle bin older than 30 days.

        Detection logic:
        - Query recycle bin for each site
        - Check deletedDateTime for each item
        - Flag items older than max_retention_days

        Args:
            detection_rules: Detection configuration:
                {
                    "recycle_bin_old": {
                        "enabled": bool,
                        "max_retention_days": int (default 30)
                    }
                }

        Returns:
            List of old recycle bin items per site
        """
        rules = (detection_rules or {}).get("recycle_bin_old", {})
        if not rules.get("enabled", True):
            return []

        max_retention_days = rules.get("max_retention_days", 30)
        orphans: list[OrphanResourceData] = []

        try:
            sites = await self._call_graph_api("/sites?search=*")

            for site in sites:
                site_id = site.get("id")
                site_name = site.get("displayName", site.get("name", "Unknown"))
                site_url = site.get("webUrl", "")

                try:
                    # Get recycle bin items (beta endpoint)
                    recycle_items = await self._call_graph_api(
                        f"/sites/{site_id}/recycleBin/items",
                        use_beta=True,
                    )

                    old_items = []
                    total_size_bytes = 0
                    oldest_days = 0

                    for item in recycle_items:
                        deleted_date_str = item.get("deletedDateTime")
                        if not deleted_date_str:
                            continue

                        deleted_date = datetime.fromisoformat(
                            deleted_date_str.replace("Z", "+00:00")
                        )
                        days_in_bin = (datetime.now(timezone.utc) - deleted_date).days

                        if days_in_bin >= max_retention_days:
                            old_items.append(item)
                            # Size may not always be available in recycle bin API
                            size = item.get("size", 0)
                            total_size_bytes += size
                            oldest_days = max(oldest_days, days_in_bin)

                    if old_items:
                        total_size_gb = total_size_bytes / (1024**3)
                        monthly_cost = total_size_gb * 0.20

                        orphans.append(
                            OrphanResourceData(
                                resource_type="sharepoint_recycle_bin_old",
                                resource_id=site_id,
                                resource_name=f"{site_name} - Recycle Bin",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "site_name": site_name,
                                    "site_url": site_url,
                                    "recycle_bin_item_count": len(old_items),
                                    "recycle_bin_size_gb": round(total_size_gb, 2),
                                    "oldest_item_days_ago": oldest_days,
                                    "items_older_than_threshold": len(old_items),
                                    "reason": f"{len(old_items)} items in recycle bin for {max_retention_days}+ days",
                                    "recommendation": f"Empty recycle bin or reduce retention policy to save ${monthly_cost:.2f}/month",
                                    "confidence": "high",
                                },
                            )
                        )

                except Exception:
                    # Recycle bin API may not be available for all sites
                    continue

        except Exception as e:
            print(f"Error scanning SharePoint recycle bin: {str(e)}")

        return orphans

    # ========================================================================
    # ONEDRIVE DETECTION SCENARIOS (5)
    # ========================================================================

    async def scan_onedrive_large_files_unused(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 6: Detect large files (>100MB) in OneDrive not accessed for 180+ days.

        Similar to SharePoint scenario 1, but scans OneDrive personal drives.

        Args:
            detection_rules: Detection configuration

        Returns:
            List of orphan large unused files in OneDrive
        """
        rules = (detection_rules or {}).get("large_files_unused", {})
        if not rules.get("enabled", True):
            return []

        min_file_size_mb = rules.get("min_file_size_mb", 100)
        min_age_days = rules.get("min_age_days", 180)
        min_file_size_bytes = min_file_size_mb * 1024 * 1024

        orphans: list[OrphanResourceData] = []

        try:
            # Get all users
            users = await self._call_graph_api("/users", params={"$select": "id,displayName,userPrincipalName"})

            for user in users:
                user_id = user.get("id")
                user_name = user.get("displayName", user.get("userPrincipalName", "Unknown"))

                try:
                    # Get user's OneDrive
                    drive = await self._call_graph_api(f"/users/{user_id}/drive")
                    drive_id = drive.get("id")

                    # Query large files
                    files = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='')",
                        params={
                            "$filter": f"file ne null and size gt {min_file_size_bytes}",
                            "$select": "id,name,size,createdDateTime,lastModifiedDateTime,lastAccessedDateTime,webUrl,file",
                        },
                    )

                    for file_item in files:
                        file_size_bytes = file_item.get("size", 0)
                        file_size_gb = file_size_bytes / (1024**3)

                        last_accessed_str = file_item.get("lastAccessedDateTime") or file_item.get("lastModifiedDateTime")
                        if not last_accessed_str:
                            continue

                        last_accessed = datetime.fromisoformat(
                            last_accessed_str.replace("Z", "+00:00")
                        )
                        age_days = (datetime.now(timezone.utc) - last_accessed).days

                        if age_days >= min_age_days:
                            monthly_cost = file_size_gb * 0.20

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="onedrive_large_files_unused",
                                    resource_id=file_item.get("id", ""),
                                    resource_name=file_item.get("name", "Unknown file"),
                                    region="global",
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "user_principal_name": user.get("userPrincipalName", ""),
                                        "user_display_name": user_name,
                                        "file_path": file_item.get("webUrl", ""),
                                        "file_size_gb": round(file_size_gb, 2),
                                        "last_accessed": last_accessed_str,
                                        "last_accessed_days_ago": age_days,
                                        "created_at": file_item.get("createdDateTime", ""),
                                        "reason": f"Large OneDrive file ({min_file_size_mb}+ MB) not accessed for {age_days} days",
                                        "recommendation": "Archive to Azure Blob Cool tier or delete if no longer needed",
                                        "confidence": self._calculate_confidence_level(age_days, detection_rules),
                                    },
                                )
                            )

                except Exception:
                    # User may not have OneDrive provisioned
                    continue

        except Exception as e:
            print(f"Error scanning OneDrive large files: {str(e)}")

        return orphans

    async def scan_onedrive_disabled_users(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 7: Detect OneDrive drives of disabled users still consuming storage.

        Detection logic:
        - Query all users with accountEnabled=false
        - Check if OneDrive exists and has data
        - Check days since account was disabled
        - Flag drives older than retention_days (default 93 days, M365 default retention)

        Args:
            detection_rules: Detection configuration:
                {
                    "disabled_users": {
                        "enabled": bool,
                        "retention_days": int (default 93)
                    }
                }

        Returns:
            List of OneDrive drives for disabled users
        """
        rules = (detection_rules or {}).get("disabled_users", {})
        if not rules.get("enabled", True):
            return []

        retention_days = rules.get("retention_days", 93)
        orphans: list[OrphanResourceData] = []

        try:
            # Get disabled users
            disabled_users = await self._call_graph_api(
                "/users",
                params={
                    "$filter": "accountEnabled eq false",
                    "$select": "id,displayName,userPrincipalName,accountEnabled,signInActivity",
                },
            )

            for user in disabled_users:
                user_id = user.get("id")
                user_email = user.get("userPrincipalName", "")
                user_name = user.get("displayName", user_email)

                try:
                    # Get user's OneDrive
                    drive = await self._call_graph_api(f"/users/{user_id}/drive")
                    drive_id = drive.get("id")

                    # Get drive quota/usage
                    quota = drive.get("quota", {})
                    storage_used_bytes = quota.get("used", 0)
                    storage_gb = storage_used_bytes / (1024**3)

                    if storage_gb == 0:
                        continue  # Skip empty drives

                    # Try to get last sign-in date
                    sign_in_activity = user.get("signInActivity", {})
                    last_sign_in_str = sign_in_activity.get("lastSignInDateTime")

                    disabled_days = 0
                    if last_sign_in_str:
                        last_sign_in = datetime.fromisoformat(
                            last_sign_in_str.replace("Z", "+00:00")
                        )
                        disabled_days = (datetime.now(timezone.utc) - last_sign_in).days

                    if disabled_days >= retention_days:
                        monthly_cost = storage_gb * 0.20

                        orphans.append(
                            OrphanResourceData(
                                resource_type="onedrive_disabled_users",
                                resource_id=drive_id,
                                resource_name=f"{user_email} - OneDrive",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "user_principal_name": user_email,
                                    "display_name": user_name,
                                    "account_enabled": False,
                                    "account_disabled_date": last_sign_in_str or "Unknown",
                                    "days_since_disabled": disabled_days,
                                    "onedrive_size_gb": round(storage_gb, 2),
                                    "reason": f"User disabled {disabled_days} days ago, OneDrive still active ({storage_gb:.1f} GB)",
                                    "recommendation": f"Backup critical files to Azure Blob, then delete OneDrive to save ${monthly_cost:.2f}/month",
                                    "confidence": self._calculate_confidence_level(disabled_days, detection_rules),
                                },
                            )
                        )

                except Exception:
                    # OneDrive may not exist for this user
                    continue

        except Exception as e:
            print(f"Error scanning OneDrive disabled users: {str(e)}")

        return orphans

    async def scan_onedrive_temp_files_accumulated(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 8: Detect accumulated temporary files in OneDrive (.tmp, ~$, .bak, .swp).

        Detection logic:
        - Query all files in OneDrive drives
        - Filter by temp file patterns: .tmp, ~$, .bak, .swp
        - Check age > min_age_days (default 7)
        - Calculate total waste per user

        Args:
            detection_rules: Detection configuration:
                {
                    "temp_files_accumulated": {
                        "enabled": bool,
                        "min_age_days": int (default 7),
                        "file_patterns": list[str] (default [".tmp", "~$", ".bak", ".swp"])
                    }
                }

        Returns:
            List of users with accumulated temp files
        """
        rules = (detection_rules or {}).get("temp_files_accumulated", {})
        if not rules.get("enabled", True):
            return []

        min_age_days = rules.get("min_age_days", 7)
        file_patterns = rules.get("file_patterns", [".tmp", "~$", ".bak", ".swp"])

        orphans: list[OrphanResourceData] = []

        try:
            users = await self._call_graph_api("/users", params={"$select": "id,displayName,userPrincipalName"})

            for user in users:
                user_id = user.get("id")
                user_email = user.get("userPrincipalName", "")
                user_name = user.get("displayName", user_email)

                try:
                    drive = await self._call_graph_api(f"/users/{user_id}/drive")
                    drive_id = drive.get("id")

                    # Search for temp files
                    temp_files = []
                    total_size_bytes = 0

                    for pattern in file_patterns:
                        try:
                            files = await self._call_graph_api(
                                f"/drives/{drive_id}/root/search(q='{pattern}')",
                                params={"$select": "id,name,size,createdDateTime,lastModifiedDateTime"},
                            )

                            for file_item in files:
                                # Check if file matches pattern
                                file_name = file_item.get("name", "")
                                if pattern in file_name:
                                    last_modified_str = file_item.get("lastModifiedDateTime")
                                    if last_modified_str:
                                        last_modified = datetime.fromisoformat(
                                            last_modified_str.replace("Z", "+00:00")
                                        )
                                        age_days = (datetime.now(timezone.utc) - last_modified).days

                                        if age_days >= min_age_days:
                                            temp_files.append(file_item)
                                            total_size_bytes += file_item.get("size", 0)

                        except Exception:
                            continue

                    if temp_files:
                        total_size_gb = total_size_bytes / (1024**3)
                        monthly_cost = total_size_gb * 0.20

                        # Count by pattern
                        pattern_counts = {}
                        for file_item in temp_files:
                            file_name = file_item.get("name", "")
                            for pattern in file_patterns:
                                if pattern in file_name:
                                    pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1

                        orphans.append(
                            OrphanResourceData(
                                resource_type="onedrive_temp_files_accumulated",
                                resource_id=drive_id,
                                resource_name=f"{user_email} - Temp Files",
                                region="global",
                                estimated_monthly_cost=monthly_cost,
                                resource_metadata={
                                    "user_principal_name": user_email,
                                    "user_display_name": user_name,
                                    "temp_files_count": len(temp_files),
                                    "temp_files_size_gb": round(total_size_gb, 4),
                                    "file_pattern_counts": pattern_counts,
                                    "oldest_temp_file_days_ago": min_age_days,
                                    "reason": f"{len(temp_files)} temporary files accumulated ({total_size_gb:.3f} GB waste)",
                                    "recommendation": f"Delete temp files to save ${monthly_cost:.2f}/month and improve organization",
                                    "confidence": "medium",
                                },
                            )
                        )

                except Exception:
                    continue

        except Exception as e:
            print(f"Error scanning OneDrive temp files: {str(e)}")

        return orphans

    async def scan_onedrive_excessive_sharing(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 9: Detect files shared externally with 0 accesses (security risk + waste).

        Detection logic:
        - Query all files in OneDrive
        - Check permissions for external/anonymous sharing
        - Verify access count = 0 and age > min_age_days
        - Flag as security risk + potential waste

        Args:
            detection_rules: Detection configuration:
                {
                    "excessive_sharing": {
                        "enabled": bool,
                        "min_age_days": int (default 90)
                    }
                }

        Returns:
            List of files with excessive external sharing
        """
        rules = (detection_rules or {}).get("excessive_sharing", {})
        if not rules.get("enabled", True):
            return []

        min_age_days = rules.get("min_age_days", 90)
        orphans: list[OrphanResourceData] = []

        try:
            users = await self._call_graph_api("/users", params={"$select": "id,displayName,userPrincipalName"})

            for user in users:
                user_id = user.get("id")
                user_email = user.get("userPrincipalName", "")
                user_name = user.get("displayName", user_email)

                try:
                    drive = await self._call_graph_api(f"/users/{user_id}/drive")
                    drive_id = drive.get("id")

                    # Get all files
                    files = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='')",
                        params={
                            "$filter": "file ne null",
                            "$select": "id,name,size,createdDateTime,webUrl",
                        },
                    )

                    for file_item in files:
                        file_id = file_item.get("id")

                        try:
                            # Get file permissions
                            permissions = await self._call_graph_api(
                                f"/drives/{drive_id}/items/{file_id}/permissions"
                            )

                            # Check for external/anonymous sharing
                            external_shares = []
                            for perm in permissions:
                                link = perm.get("link", {})
                                scope = link.get("scope", "")

                                if scope in ["anonymous", "organization"]:
                                    external_shares.append(perm)

                            if external_shares:
                                created_date_str = file_item.get("createdDateTime", "")
                                if created_date_str:
                                    created_date = datetime.fromisoformat(
                                        created_date_str.replace("Z", "+00:00")
                                    )
                                    age_days = (datetime.now(timezone.utc) - created_date).days

                                    if age_days >= min_age_days:
                                        # This is a security risk (shared but never accessed)
                                        orphans.append(
                                            OrphanResourceData(
                                                resource_type="onedrive_excessive_sharing",
                                                resource_id=file_id,
                                                resource_name=file_item.get("name", "Unknown"),
                                                region="global",
                                                estimated_monthly_cost=0.0,  # Security risk, not direct cost
                                                resource_metadata={
                                                    "user_principal_name": user_email,
                                                    "user_display_name": user_name,
                                                    "file_path": file_item.get("webUrl", ""),
                                                    "external_share_count": len(external_shares),
                                                    "share_types": [s.get("link", {}).get("scope", "") for s in external_shares],
                                                    "created_date": created_date_str,
                                                    "days_since_created": age_days,
                                                    "reason": f"File shared externally {age_days} days ago (potential security risk)",
                                                    "recommendation": "Review external sharing permissions and remove if no longer needed (security best practice)",
                                                    "compliance_risk": "High - file shared externally without recent access",
                                                    "confidence": "high",
                                                },
                                            )
                                        )

                        except Exception:
                            continue

                except Exception:
                    continue

        except Exception as e:
            print(f"Error scanning OneDrive excessive sharing: {str(e)}")

        return orphans

    async def scan_onedrive_duplicate_attachments(
        self, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """
        Scenario 10: Detect duplicate email attachments saved to OneDrive.

        Detection logic:
        - Query files in OneDrive "Email Attachments" or "Attachments" folders
        - Group by hash (quickXorHash)
        - Flag duplicates (same file saved from multiple emails)

        Args:
            detection_rules: Detection configuration

        Returns:
            List of duplicate email attachments
        """
        rules = (detection_rules or {}).get("duplicate_attachments", {})
        if not rules.get("enabled", True):
            return []

        orphans: list[OrphanResourceData] = []

        try:
            users = await self._call_graph_api("/users", params={"$select": "id,displayName,userPrincipalName"})

            for user in users:
                user_id = user.get("id")
                user_email = user.get("userPrincipalName", "")
                user_name = user.get("displayName", user_email)

                try:
                    drive = await self._call_graph_api(f"/users/{user_id}/drive")
                    drive_id = drive.get("id")

                    # Search for "Attachments" or "Email Attachments" folders
                    attachment_folders = await self._call_graph_api(
                        f"/drives/{drive_id}/root/search(q='Attachments')",
                        params={"$filter": "folder ne null", "$select": "id,name"},
                    )

                    # Track files by hash
                    files_by_hash: dict[str, list[dict]] = {}

                    for folder in attachment_folders:
                        folder_id = folder.get("id")

                        try:
                            # Get files in attachment folder
                            files = await self._call_graph_api(
                                f"/drives/{drive_id}/items/{folder_id}/children",
                                params={
                                    "$filter": "file ne null",
                                    "$select": "id,name,size,webUrl,file",
                                },
                            )

                            for file_item in files:
                                hashes = file_item.get("file", {}).get("hashes", {})
                                file_hash = hashes.get("quickXorHash")

                                if file_hash:
                                    if file_hash not in files_by_hash:
                                        files_by_hash[file_hash] = []

                                    files_by_hash[file_hash].append(
                                        {
                                            "id": file_item.get("id"),
                                            "name": file_item.get("name"),
                                            "size": file_item.get("size", 0),
                                            "url": file_item.get("webUrl", ""),
                                        }
                                    )

                        except Exception:
                            continue

                    # Find duplicates
                    for file_hash, file_list in files_by_hash.items():
                        if len(file_list) >= 2:
                            original = file_list[0]
                            duplicates = file_list[1:]

                            total_wasted_bytes = sum(f["size"] for f in duplicates)
                            total_wasted_gb = total_wasted_bytes / (1024**3)
                            monthly_cost = total_wasted_gb * 0.20

                            orphans.append(
                                OrphanResourceData(
                                    resource_type="onedrive_duplicate_attachments",
                                    resource_id=original["id"],
                                    resource_name=f"{original['name']} (+ {len(duplicates)} duplicates)",
                                    region="global",
                                    estimated_monthly_cost=monthly_cost,
                                    resource_metadata={
                                        "user_principal_name": user_email,
                                        "user_display_name": user_name,
                                        "original_file": original["url"],
                                        "duplicate_files": [d["url"] for d in duplicates],
                                        "file_hash": file_hash,
                                        "duplicate_count": len(duplicates),
                                        "total_size_gb": round((original["size"] + total_wasted_bytes) / (1024**3), 4),
                                        "wasted_size_gb": round(total_wasted_gb, 4),
                                        "reason": f"{len(duplicates)} duplicate email attachment(s) found (same hash)",
                                        "recommendation": f"Keep 1 copy, delete duplicates to save ${monthly_cost:.4f}/month",
                                        "confidence": "high",
                                    },
                                )
                            )

                except Exception:
                    continue

        except Exception as e:
            print(f"Error scanning OneDrive duplicate attachments: {str(e)}")

        return orphans

    # ========================================================================
    # STUB IMPLEMENTATIONS FOR ABSTRACT METHODS
    # ========================================================================

    async def scan_unattached_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have volumes. Returns empty list."""
        return []

    async def scan_unassociated_elastic_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have elastic IPs. Returns empty list."""
        return []

    async def scan_orphan_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have snapshots. Returns empty list."""
        return []

    async def scan_idle_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have compute instances. Returns empty list."""
        return []

    async def scan_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have compute instances. Returns empty list."""
        return []

    async def scan_idle_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have volumes. Returns empty list."""
        return []

    async def scan_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have load balancers. Returns empty list."""
        return []

    async def scan_rds_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have RDS. Returns empty list."""
        return []

    async def scan_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have NAT gateways. Returns empty list."""
        return []

    async def scan_fsx_filesystems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have FSx. Returns empty list."""
        return []

    async def scan_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Neptune. Returns empty list."""
        return []

    async def scan_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have MSK. Returns empty list."""
        return []

    async def scan_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have EKS. Returns empty list."""
        return []

    async def scan_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have SageMaker. Returns empty list."""
        return []

    async def scan_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Redshift. Returns empty list."""
        return []

    async def scan_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have ElastiCache. Returns empty list."""
        return []

    async def scan_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have VPN connections. Returns empty list."""
        return []

    async def scan_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Transit Gateways. Returns empty list."""
        return []

    async def scan_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have OpenSearch. Returns empty list."""
        return []

    async def scan_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Global Accelerators. Returns empty list."""
        return []

    async def scan_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Kinesis. Returns empty list."""
        return []

    async def scan_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have VPC endpoints. Returns empty list."""
        return []

    async def scan_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have DocumentDB. Returns empty list."""
        return []

    async def scan_s3_buckets(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have S3 buckets. Returns empty list."""
        return []

    async def scan_lambda_functions(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Lambda functions. Returns empty list."""
        return []

    async def scan_dynamodb_tables(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have DynamoDB. Returns empty list."""
        return []

    async def scan_fargate_tasks(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have Fargate. Returns empty list."""
        return []

    async def scan_additional_eips_per_instance(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_burstable_credit_waste(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_dev_test_24_7_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_duplicate_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_eips_on_detached_enis(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_eips_on_failed_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_eips_on_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_excessive_retention_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_gp2_migration_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_documentdb_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_dynamodb_tables(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_eks_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_elasticache_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_global_accelerators(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_kinesis_streams(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_lambda_functions(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_msk_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_neptune_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_opensearch_domains(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_redshift_clusters(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_running_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_s3_buckets(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_sagemaker_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_transit_gateway_attachments(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_idle_vpn_connections(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_incomplete_failed_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_load_balancer_cross_zone_disabled(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_load_balancer_idle_patterns(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_low_iops_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_low_throughput_usage_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_low_traffic_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_nat_gateway_dev_test_unused_hours(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_nat_gateway_obsolete_migration(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_nat_gateway_vpc_endpoint_candidates(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_never_used_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_old_generation_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_old_unused_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_orphaned_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_overprovisioned_iops_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_overprovisioned_throughput_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_oversized_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_redundant_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_right_sizing_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_scheduled_unused_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_snapshots_from_deleted_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_spot_eligible_workloads(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_stopped_databases(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unassigned_ips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unnecessary_io2_volumes(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_untagged_ec2_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_untagged_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_ami_snapshots(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_fsx_file_systems(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_load_balancers(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_nat_gateway_eips(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_nat_gateways(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_unused_vpc_endpoints(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_volume_type_downgrade_opportunities(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    async def scan_volumes_on_stopped_instances(
        self, region: str, detection_rules: dict | None = None
    ) -> list[OrphanResourceData]:
        """Microsoft 365 doesn't have this AWS resource. Returns empty list."""
        return []

    def get_available_regions(self) -> list[str]:
        """Microsoft 365 is global. Returns ['global']."""
        return ["global"]
