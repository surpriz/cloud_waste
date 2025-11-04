# 🔧 Référence Technique - Microsoft 365 Provider

Documentation technique complète du provider Microsoft 365 de CloudWaste pour les développeurs.

---

## 📖 Table des Matières

1. [Architecture](#architecture)
2. [Microsoft Graph API](#microsoft-graph-api)
3. [Implémentation Provider](#implémentation-provider)
4. [Calculs de Coûts](#calculs-de-coûts)
5. [Schéma Base de Données](#schéma-base-de-données)
6. [Celery Integration](#celery-integration)
7. [API Endpoints](#api-endpoints)
8. [Extension & Customisation](#extension--customisation)

---

## Architecture

### Vue d'Ensemble

```
┌─────────────────────────────────────────────────────────────┐
│                    CloudWaste Frontend                       │
│  (Next.js 14 - TypeScript - React 18 - Tailwind CSS)       │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP/REST
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    CloudWaste Backend API                    │
│          (FastAPI 0.110 - Python 3.11 - Pydantic v2)        │
│                                                              │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  POST /api/v1/accounts                               │  │
│  │  POST /api/v1/accounts/validate-credentials          │  │
│  │  POST /api/v1/scans/start                            │  │
│  │  GET  /api/v1/resources                              │  │
│  └───────────────────┬──────────────────────────────────┘  │
│                      │                                      │
│  ┌───────────────────▼─────────────────┐                   │
│  │   Microsoft365Provider               │                   │
│  │   (app/providers/microsoft365.py)   │                   │
│  │   - validate_credentials()          │                   │
│  │   - scan_all_resources()            │                   │
│  │   - scan_sharepoint()               │                   │
│  │   - scan_onedrive()                 │                   │
│  └────────┬────────────────────────────┘                   │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                       Celery Workers                         │
│     (celery 5.3.6 - redis 7+ - asyncio - aioboto3)         │
│                                                              │
│  Task: app.workers.tasks.scan_cloud_account                 │
│  - Decrypt credentials (Fernet symmetric encryption)        │
│  - Instantiate Microsoft365Provider                         │
│  - Execute scan (async/await pattern)                       │
│  - Save orphan resources to PostgreSQL                      │
│  - Update scan status                                       │
└───────────────────────┬─────────────────────────────────────┘
                        │ OAuth 2.0 + REST API
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                   Microsoft Graph API                        │
│          (https://graph.microsoft.com/v1.0/)                │
│                                                              │
│  - GET /organization                                         │
│  - GET /sites?search=*                                       │
│  - GET /sites/{site-id}/drive/root/children                 │
│  - GET /sites/{site-id}/analytics/allTime                   │
│  - GET /users                                                │
│  - GET /users/{user-id}/drive/root/children                 │
│  - GET /users/{user-id}/drive/root/analytics/allTime        │
│  - GET /drives/{drive-id}/items/{item-id}/versions          │
└─────────────────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│                  Microsoft 365 Tenant                        │
│     (SharePoint Online + OneDrive for Business)             │
└─────────────────────────────────────────────────────────────┘
```

### Flux de Données - Scan Microsoft 365

```
1. User triggers scan (Frontend → Backend API)
   ↓
2. Backend creates Scan record (status: pending)
   ↓
3. Celery task queued (Redis)
   ↓
4. Celery worker picks task
   ↓
5. Decrypt M365 credentials (Fernet)
   ↓
6. Acquire OAuth 2.0 token (Microsoft Identity Platform)
   ↓
7. Scan SharePoint sites (parallel):
   - List all sites (Graph API)
   - For each site:
     * Get drive items (files/folders)
     * Get analytics (last accessed, views)
     * Get versions (if file)
     * Calculate storage size
     * Apply detection rules (5 scenarios)
   ↓
8. Scan OneDrive drives (parallel):
   - List all users (Graph API)
   - For each user:
     * Get OneDrive drive
     * Get drive items
     * Get analytics
     * Check user account status
     * Apply detection rules (5 scenarios)
   ↓
9. Save orphan resources to PostgreSQL
   ↓
10. Update scan status (completed)
    ↓
11. Return results to Frontend (polling)
```

---

## Microsoft Graph API

### Authentication

CloudWaste utilise **OAuth 2.0 Client Credentials Flow** (service principal).

#### Token Acquisition

```python
# app/providers/microsoft365.py

import aiohttp

async def _get_access_token(self) -> str:
    """Acquire OAuth 2.0 access token from Microsoft Identity Platform."""
    url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"

    data = {
        "client_id": self.client_id,
        "client_secret": self.client_secret,
        "scope": "https://graph.microsoft.com/.default",
        "grant_type": "client_credentials",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=data) as response:
            result = await response.json()

            if "access_token" not in result:
                raise AuthenticationError(f"Failed to acquire token: {result.get('error_description')}")

            return result["access_token"]

# Token lifetime: 3599 seconds (59m 59s)
# CloudWaste caches token and refreshes automatically before expiration
```

#### Required Permissions

| Permission | Type | Description |
|------------|------|-------------|
| `Files.Read.All` | Application | Read all files in SharePoint and OneDrive |
| `Sites.Read.All` | Application | Read all SharePoint sites |
| `User.Read.All` | Application | Read all user profiles |
| `Directory.Read.All` | Application | Read organization and directory info |

**⚠️ Admin Consent Required** : Must be granted by Global Administrator.

### Graph API Endpoints Used

#### Organization Info

```http
GET https://graph.microsoft.com/v1.0/organization
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "value": [
    {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "displayName": "Contoso Corporation",
      "verifiedDomains": [
        {
          "name": "contoso.onmicrosoft.com",
          "type": "Managed",
          "isDefault": true
        }
      ]
    }
  ]
}
```

**Usage** : Validate credentials + get organization name.

---

#### SharePoint Sites

```http
GET https://graph.microsoft.com/v1.0/sites?search=*
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "value": [
    {
      "id": "contoso.sharepoint.com,xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx,yyyyyyyy-yyyy-yyyy-yyyy-yyyyyyyyyyyy",
      "displayName": "Sales Team Site",
      "webUrl": "https://contoso.sharepoint.com/sites/sales",
      "createdDateTime": "2024-01-15T10:30:00Z",
      "lastModifiedDateTime": "2024-06-20T14:22:00Z"
    }
  ]
}
```

**Usage** : List all SharePoint sites in tenant.

---

#### Site Drive Items (Files/Folders)

```http
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drive/root/children
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "value": [
    {
      "id": "01ABCDEFGHIJKLMNOPQRSTUVWXYZ",
      "name": "Presentation-Q4-2023.pptx",
      "size": 786432000,
      "createdDateTime": "2023-10-01T09:00:00Z",
      "lastModifiedDateTime": "2023-10-05T16:30:00Z",
      "file": {
        "mimeType": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "hashes": {
          "quickXorHash": "ABC123XYZ789=="
        }
      },
      "parentReference": {
        "path": "/drive/root:/Shared Documents"
      }
    }
  ]
}
```

**Usage** : List files in SharePoint site, get sizes, hashes (for duplicate detection).

---

#### File Analytics (Last Accessed)

```http
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drive/items/{item-id}/analytics/allTime
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "access": {
    "actionCount": 0,
    "actorCount": 0
  },
  "lastActivityDate": "2023-06-01"
}
```

**Usage** : Detect unused files (0 access in X days).

---

#### File Versions

```http
GET https://graph.microsoft.com/v1.0/sites/{site-id}/drive/items/{item-id}/versions
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "value": [
    {"id": "1.0", "size": 1048576},
    {"id": "2.0", "size": 1048600},
    ...
    {"id": "85.0", "size": 1049000}
  ]
}
```

**Usage** : Detect excessive versioning (>50 versions).

---

#### Users (OneDrive)

```http
GET https://graph.microsoft.com/v1.0/users
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "value": [
    {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "userPrincipalName": "john.doe@contoso.com",
      "displayName": "John Doe",
      "accountEnabled": true,
      "assignedLicenses": [...]
    }
  ]
}
```

**Usage** : List all users + check account status (disabled users).

---

#### User OneDrive

```http
GET https://graph.microsoft.com/v1.0/users/{user-id}/drive
Authorization: Bearer {access_token}
```

**Response:**
```json
{
  "id": "b!xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx",
  "driveType": "business",
  "owner": {
    "user": {
      "id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
      "displayName": "John Doe"
    }
  },
  "quota": {
    "total": 1099511627776,
    "used": 48318382080,
    "remaining": 1051193245696,
    "state": "normal"
  }
}
```

**Usage** : Get OneDrive storage quota + usage.

---

### Rate Limiting

Microsoft Graph API enforces **rate limits** :

| Limit Type | Value |
|------------|-------|
| Per-app per tenant | 2000 requests / 10 seconds |
| Per-app per user | 200 requests / 10 seconds |
| Retry-After header | Wait time in seconds when throttled (HTTP 429) |

**CloudWaste Handling:**
```python
# Automatic retry with exponential backoff
import asyncio

async def _make_request(self, url: str):
    retries = 0
    max_retries = 5

    while retries < max_retries:
        response = await self.session.get(url, headers={"Authorization": f"Bearer {self.token}"})

        if response.status == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            logger.warning(f"Rate limited, waiting {retry_after}s")
            await asyncio.sleep(retry_after)
            retries += 1
            continue

        return await response.json()

    raise Exception("Max retries exceeded")
```

---

## Implémentation Provider

### Classe Microsoft365Provider

**Fichier** : `backend/app/providers/microsoft365.py` (1800 lignes)

**Hérite de** : `CloudProvider` (abstract base class)

#### Méthodes Principales

```python
class Microsoft365Provider(CloudProvider):
    """
    Microsoft 365 provider for SharePoint Online and OneDrive for Business.

    Detects 10 waste scenarios:
    - SharePoint: large unused files, duplicates, abandoned sites, excessive versions, old recycle bin
    - OneDrive: large unused files, disabled users, temp files, excessive sharing, duplicate attachments
    """

    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.token: str | None = None
        self.token_expires_at: datetime | None = None

    async def validate_credentials(self) -> dict:
        """
        Validate M365 credentials by:
        1. Acquiring OAuth token
        2. Fetching organization info
        3. Returning tenant details

        Returns:
            {
                "tenant_id": str,
                "organization_name": str,
                "verified_domains": list[str],
                "valid": bool
            }

        Raises:
            AuthenticationError: If credentials invalid
        """

    async def scan_all_resources(
        self,
        region: str,  # Always "global" for M365
        detection_rules: dict[str, dict],
        scan_global_resources: bool = True
    ) -> list[OrphanResource]:
        """
        Scan entire M365 tenant for waste.

        Steps:
        1. Acquire Graph API token
        2. Scan SharePoint sites (parallel)
        3. Scan OneDrive drives (parallel)
        4. Apply detection rules
        5. Return orphan resources

        Returns:
            List of OrphanResource objects with metadata
        """

    async def _scan_sharepoint(self, rules: dict) -> list[OrphanResource]:
        """
        Scan all SharePoint sites in tenant.

        Detection scenarios:
        - sharepoint_large_files_unused
        - sharepoint_duplicate_files
        - sharepoint_sites_abandoned
        - sharepoint_excessive_versions
        - sharepoint_recycle_bin_old
        """

    async def _scan_onedrive(self, rules: dict) -> list[OrphanResource]:
        """
        Scan all OneDrive drives in tenant.

        Detection scenarios:
        - onedrive_large_files_unused
        - onedrive_disabled_users
        - onedrive_temp_files_accumulated
        - onedrive_excessive_sharing
        - onedrive_duplicate_attachments
        """
```

#### Exemple Implémentation - Large Files Unused

```python
async def _detect_large_files_unused(
    self,
    site_id: str,
    site_name: str,
    site_url: str,
    rules: dict
) -> list[OrphanResource]:
    """
    Detect large files (>100 MB) not accessed for 180+ days.
    """
    rule = rules.get("sharepoint_sites", {}).get("large_files_unused", {})

    if not rule.get("enabled", True):
        return []

    min_size_mb = rule.get("min_file_size_mb", 100)
    min_age_days = rule.get("min_age_days", 180)

    # Get all files in site
    drive_items = await self._list_drive_items(site_id)

    orphans = []

    for item in drive_items:
        # Skip folders
        if "folder" in item:
            continue

        # Check file size
        size_bytes = item.get("size", 0)
        size_mb = size_bytes / (1024 * 1024)

        if size_mb < min_size_mb:
            continue

        # Check last accessed date
        analytics = await self._get_item_analytics(site_id, item["id"])
        last_accessed_str = analytics.get("lastActivityDate")

        if not last_accessed_str:
            # Never accessed
            days_since_access = 9999
        else:
            last_accessed = datetime.fromisoformat(last_accessed_str)
            days_since_access = (datetime.utcnow() - last_accessed).days

        if days_since_access < min_age_days:
            continue

        # Calculate cost
        storage_gb = size_bytes / (1024**3)
        monthly_cost = storage_gb * 0.20  # $0.20/GB/month for SharePoint

        # Create orphan resource
        orphan = OrphanResource(
            resource_type="sharepoint_large_files_unused",
            resource_id=item["id"],
            resource_name=item["name"],
            region="global",
            estimated_monthly_cost=round(monthly_cost, 2),
            resource_metadata={
                "site_name": site_name,
                "site_url": site_url,
                "file_path": item["parentReference"]["path"],
                "file_size_gb": round(storage_gb, 2),
                "last_accessed_days_ago": days_since_access,
                "reason": f"Large file ({size_mb:.0f} MB) not accessed for {days_since_access} days",
                "recommendation": "Archive to Azure Blob Cool tier or delete",
                "confidence": self._get_confidence_level(days_since_access)
            }
        )

        orphans.append(orphan)

    return orphans

def _get_confidence_level(self, days: int) -> str:
    """Map age to confidence level."""
    if days >= 365:
        return "critical"
    elif days >= 180:
        return "high"
    elif days >= 90:
        return "medium"
    else:
        return "low"
```

---

## Calculs de Coûts

### Tarifs Microsoft 365

CloudWaste utilise les **tarifs standard Microsoft 365** pour calculer les coûts estimés :

| Service | Coût Base | Coût par GB/mois | Notes |
|---------|-----------|------------------|-------|
| **SharePoint Online** | Inclus dans plan | $0.20 / GB / mois | Au-delà du quota plan |
| **OneDrive for Business** | Inclus dans plan | $0.20 / GB / mois | Au-delà du quota plan |
| **SharePoint Storage Add-On** | - | $0.20 / GB / mois | Storage supplémentaire acheté |

**Quotas Standard :**
- Microsoft 365 Business Basic : 1 TB par organisation + 10 GB par licence
- Microsoft 365 Business Standard : Idem
- Office 365 E3/E5 : Illimité (avec 5+ utilisateurs)

### Formule de Calcul

```python
def calculate_monthly_cost(storage_bytes: int, service: str = "sharepoint") -> float:
    """
    Calculate monthly cost for M365 storage.

    Args:
        storage_bytes: Size in bytes
        service: "sharepoint" or "onedrive"

    Returns:
        Monthly cost in USD
    """
    # Convert bytes to GB
    storage_gb = storage_bytes / (1024 ** 3)

    # Microsoft 365 pricing
    COST_PER_GB_MONTH = {
        "sharepoint": 0.20,  # $0.20/GB/month
        "onedrive": 0.20,
    }

    cost_per_gb = COST_PER_GB_MONTH.get(service, 0.20)

    monthly_cost = storage_gb * cost_per_gb

    return round(monthly_cost, 2)

# Example
file_size = 750 * 1024 * 1024  # 750 MB
monthly_cost = calculate_monthly_cost(file_size, "sharepoint")
# Result: 0.15 (750 MB = 0.73 GB × $0.20 = $0.15/month)
```

### Coût Total Annuel

```python
def calculate_annual_savings(orphan_resources: list[OrphanResource]) -> dict:
    """
    Calculate total annual savings if all orphan resources are deleted.

    Returns:
        {
            "monthly_waste": float,      # $ per month
            "annual_waste": float,        # $ per year
            "total_storage_gb": float,   # Total wasted storage in GB
            "resources_count": int       # Number of orphan resources
        }
    """
    total_monthly_cost = sum(r.estimated_monthly_cost for r in orphan_resources)
    total_annual_cost = total_monthly_cost * 12
    total_storage_gb = sum(
        r.resource_metadata.get("file_size_gb", 0)
        for r in orphan_resources
    )

    return {
        "monthly_waste": round(total_monthly_cost, 2),
        "annual_waste": round(total_annual_cost, 2),
        "total_storage_gb": round(total_storage_gb, 2),
        "resources_count": len(orphan_resources)
    }
```

---

## Schéma Base de Données

### Table `cloud_accounts`

```sql
CREATE TABLE cloud_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL,  -- "microsoft365"
    account_name VARCHAR(255) NOT NULL,
    account_identifier VARCHAR(255) NOT NULL,  -- tenant_id or contoso.onmicrosoft.com
    credentials_encrypted TEXT NOT NULL,  -- Fernet encrypted JSON
    regions TEXT[],  -- NULL for M365 (global)
    resource_groups TEXT[],  -- NULL for M365
    description TEXT,
    is_active BOOLEAN DEFAULT true,
    last_scan_at TIMESTAMP,
    scheduled_scan_enabled BOOLEAN DEFAULT false,
    scheduled_scan_frequency VARCHAR(20) DEFAULT 'daily',
    scheduled_scan_hour INTEGER DEFAULT 2,
    scheduled_scan_day_of_week INTEGER,
    scheduled_scan_day_of_month INTEGER,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Example M365 account record
INSERT INTO cloud_accounts (user_id, provider, account_name, account_identifier, credentials_encrypted)
VALUES (
    'user-123',
    'microsoft365',
    'Contoso M365 Tenant',
    'contoso.onmicrosoft.com',
    'gAAAAABhxxxxx...'  -- Fernet encrypted: {"tenant_id": "...", "client_id": "...", "client_secret": "..."}
);
```

### Table `orphan_resources`

```sql
CREATE TABLE orphan_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID NOT NULL REFERENCES scans(id) ON DELETE CASCADE,
    cloud_account_id UUID NOT NULL REFERENCES cloud_accounts(id) ON DELETE CASCADE,
    resource_type VARCHAR(100) NOT NULL,  -- "sharepoint_large_files_unused", etc.
    resource_id VARCHAR(500) NOT NULL,  -- Microsoft Graph API item ID
    resource_name VARCHAR(500),
    region VARCHAR(50) DEFAULT 'global',  -- Always "global" for M365
    estimated_monthly_cost DECIMAL(12, 2) DEFAULT 0.00,
    resource_metadata JSONB,  -- Detailed metadata (see below)
    status VARCHAR(50) DEFAULT 'active',  -- "active", "ignored", "marked_for_deletion", "deleted"
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_orphan_resources_resource_type ON orphan_resources(resource_type);
CREATE INDEX idx_orphan_resources_cloud_account ON orphan_resources(cloud_account_id);
CREATE INDEX idx_orphan_resources_status ON orphan_resources(status);
```

### Table `detection_rules`

```sql
CREATE TABLE detection_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,  -- NULL = default global rules
    resource_type VARCHAR(100) NOT NULL,  -- "sharepoint_sites", "onedrive_drives"
    rules JSONB NOT NULL,  -- Custom detection rules
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(user_id, resource_type)
);

-- Default M365 rules (inserted by migration)
INSERT INTO detection_rules (user_id, resource_type, rules)
VALUES
(
    NULL,  -- Global default
    'sharepoint_sites',
    '{
        "large_files_unused": {"enabled": true, "min_file_size_mb": 100, "min_age_days": 180},
        "duplicate_files": {"enabled": true},
        "sites_abandoned": {"enabled": true, "min_inactive_days": 90},
        "excessive_versions": {"enabled": true, "max_versions_threshold": 50},
        "recycle_bin_old": {"enabled": true, "max_retention_days": 30}
    }'::jsonb
),
(
    NULL,
    'onedrive_drives',
    '{
        "large_files_unused": {"enabled": true, "min_file_size_mb": 100, "min_age_days": 180},
        "disabled_users": {"enabled": true, "retention_days": 93},
        "temp_files_accumulated": {"enabled": true, "min_age_days": 7, "file_patterns": [".tmp", "~$", ".bak", ".swp"]},
        "excessive_sharing": {"enabled": true, "min_age_days": 90},
        "duplicate_attachments": {"enabled": true}
    }'::jsonb
);
```

### Metadata JSON Structure

**SharePoint Large Files Unused:**
```json
{
  "site_name": "Sales Team Site",
  "site_url": "https://contoso.sharepoint.com/sites/sales",
  "file_path": "/Shared Documents/Presentations/Q4-2023.pptx",
  "file_size_gb": 0.75,
  "last_accessed_days_ago": 210,
  "reason": "Large file (750 MB) not accessed for 210 days",
  "recommendation": "Archive to Azure Blob Cool tier or delete",
  "confidence": "critical"
}
```

**OneDrive Disabled Users:**
```json
{
  "user_principal_name": "jane.smith@contoso.com",
  "user_display_name": "Jane Smith",
  "account_disabled_date": "2024-02-15",
  "days_since_disabled": 120,
  "onedrive_storage_gb": 45.3,
  "reason": "User account disabled for 120 days, OneDrive still consuming 45.3 GB",
  "recommendation": "Export important files to archive, then delete OneDrive",
  "confidence": "high"
}
```

---

## Celery Integration

### Task Définition

**Fichier** : `backend/app/workers/tasks.py`

```python
from celery import shared_task
from app.providers.microsoft365 import Microsoft365Provider

@shared_task(bind=True, max_retries=3)
def scan_cloud_account(self, account_id: str) -> dict:
    """
    Celery task to scan a cloud account (AWS, Azure, GCP, or Microsoft 365).
    """
    # Get account from database
    account = crud.get_cloud_account(db, account_id)

    # Create scan record
    scan = crud.create_scan(db, account_id, scan_type="manual", status="in_progress")

    try:
        # Decrypt credentials
        credentials = decrypt_credentials(account.credentials_encrypted)

        # Instantiate provider
        if account.provider == "microsoft365":
            provider = Microsoft365Provider(
                tenant_id=credentials["tenant_id"],
                client_id=credentials["client_id"],
                client_secret=credentials["client_secret"],
            )

            # Validate credentials
            await provider.validate_credentials()

            # Get detection rules
            user_detection_rules = crud.get_user_detection_rules(db, account.user_id)

            # Scan all resources (M365 is global, no regions)
            orphan_resources = await provider.scan_all_resources(
                region="global",
                detection_rules=user_detection_rules,
                scan_global_resources=True,
            )

            # Save orphan resources to database
            for orphan in orphan_resources:
                crud.create_orphan_resource(
                    db,
                    scan_id=scan.id,
                    cloud_account_id=account.id,
                    resource_type=orphan.resource_type,
                    resource_id=orphan.resource_id,
                    resource_name=orphan.resource_name,
                    region=orphan.region,
                    estimated_monthly_cost=orphan.estimated_monthly_cost,
                    resource_metadata=orphan.resource_metadata,
                )

            # Update scan status
            crud.update_scan(
                db,
                scan_id=scan.id,
                status="completed",
                total_resources_scanned=len(orphan_resources),
                orphan_resources_found=len(orphan_resources),
                estimated_monthly_waste=sum(r.estimated_monthly_cost for r in orphan_resources),
                completed_at=datetime.utcnow(),
            )

        else:
            raise ValueError(f"Unsupported provider: {account.provider}")

        return {"scan_id": scan.id, "status": "completed"}

    except Exception as e:
        # Mark scan as failed
        crud.update_scan(db, scan_id=scan.id, status="failed", error_message=str(e))
        raise self.retry(exc=e, countdown=60)  # Retry after 60s
```

---

## API Endpoints

### POST /api/v1/accounts

**Créer compte Microsoft 365**

```http
POST /api/v1/accounts
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "provider": "microsoft365",
  "account_name": "Contoso M365 Tenant",
  "account_identifier": "contoso.onmicrosoft.com",
  "microsoft365_tenant_id": "contoso.onmicrosoft.com",
  "microsoft365_client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "microsoft365_client_secret": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz",
  "description": "Production M365 tenant"
}
```

**Response:**
```json
{
  "id": "abc123-...",
  "provider": "microsoft365",
  "account_name": "Contoso M365 Tenant",
  "account_identifier": "contoso.onmicrosoft.com",
  "is_active": true,
  "last_scan_at": null,
  "created_at": "2025-11-02T12:00:00Z"
}
```

---

### POST /api/v1/accounts/validate-credentials

**Valider credentials avant création compte**

```http
POST /api/v1/accounts/validate-credentials
Authorization: Bearer {jwt_token}
Content-Type: application/json

{
  "provider": "microsoft365",
  "account_name": "Test",
  "account_identifier": "contoso.onmicrosoft.com",
  "microsoft365_tenant_id": "contoso.onmicrosoft.com",
  "microsoft365_client_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "microsoft365_client_secret": "zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
}
```

**Response (Success):**
```json
{
  "valid": true,
  "provider": "microsoft365",
  "tenant_id": "contoso.onmicrosoft.com",
  "organization_name": "Contoso Corporation",
  "verified_domains": ["contoso.onmicrosoft.com", "contoso.com"],
  "message": "✅ Microsoft 365 credentials are valid! Organization: Contoso Corporation"
}
```

**Response (Error):**
```json
{
  "valid": false,
  "error": "Insufficient privileges to complete the operation",
  "message": "Admin consent required for API permissions"
}
```

---

## Extension & Customisation

### Ajouter un Nouveau Scénario de Détection

**Étape 1** : Ajouter resource type dans `backend/app/models/orphan_resource.py`

```python
class ResourceType(str, Enum):
    # ... existing types ...
    SHAREPOINT_EXTERNAL_SHARING = "sharepoint_external_sharing"  # NEW
```

**Étape 2** : Ajouter règle par défaut dans migration Alembic

```sql
-- alembic/versions/xxxxx_add_external_sharing_rule.py

op.execute("""
    UPDATE detection_rules
    SET rules = rules || '{"external_sharing": {"enabled": true, "min_age_days": 30}}'::jsonb
    WHERE resource_type = 'sharepoint_sites' AND user_id IS NULL;
""")
```

**Étape 3** : Implémenter détection dans `Microsoft365Provider`

```python
async def _detect_external_sharing(self, site_id: str, rules: dict) -> list[OrphanResource]:
    """Detect files shared externally but not accessed."""
    rule = rules.get("sharepoint_sites", {}).get("external_sharing", {})

    if not rule.get("enabled", True):
        return []

    min_age_days = rule.get("min_age_days", 30)

    # Get all shared items
    shared_items = await self._list_shared_items(site_id)

    orphans = []

    for item in shared_items:
        # Check if externally shared
        permissions = item.get("permissions", [])
        has_external_share = any(
            p.get("grantedToIdentitiesV2", [{}])[0].get("siteUser", {}).get("email", "").endswith("@external.com")
            for p in permissions
        )

        if not has_external_share:
            continue

        # Check last accessed
        analytics = await self._get_item_analytics(site_id, item["id"])
        days_since_access = self._calculate_age(analytics.get("lastActivityDate"))

        if days_since_access >= min_age_days:
            orphans.append(OrphanResource(
                resource_type="sharepoint_external_sharing",
                resource_id=item["id"],
                resource_name=item["name"],
                region="global",
                estimated_monthly_cost=0.05,  # Security risk cost
                resource_metadata={
                    "shared_with": [p["email"] for p in permissions],
                    "days_since_access": days_since_access,
                    "reason": f"File shared externally but not accessed for {days_since_access} days",
                    "recommendation": "Revoke external sharing link",
                    "confidence": "high"
                }
            ))

    return orphans
```

**Étape 4** : Appeler dans `_scan_sharepoint()`

```python
async def _scan_sharepoint(self, rules: dict) -> list[OrphanResource]:
    orphans = []

    sites = await self._list_all_sites()

    for site in sites:
        # ... existing detections ...
        orphans.extend(await self._detect_external_sharing(site["id"], rules))  # NEW

    return orphans
```

**Étape 5** : Frontend - Ajouter type dans `frontend/src/types/index.ts`

```typescript
export type ResourceType =
  | "sharepoint_large_files_unused"
  // ... existing types ...
  | "sharepoint_external_sharing";  // NEW
```

---

## 📚 Ressources Supplémentaires

- **Microsoft Graph API Documentation** : https://learn.microsoft.com/en-us/graph/overview
- **SharePoint REST API** : https://learn.microsoft.com/en-us/sharepoint/dev/sp-add-ins/get-to-know-the-sharepoint-rest-service
- **Microsoft 365 Pricing** : https://www.microsoft.com/en-us/microsoft-365/business/compare-all-microsoft-365-business-products
- **Entra ID App Registrations** : https://learn.microsoft.com/en-us/entra/identity-platform/quickstart-register-app

---

## 🔐 Security Best Practices

1. **Credentials Storage** : Always encrypt credentials using Fernet before storing in database
2. **Token Caching** : Cache Graph API tokens (59 min TTL) to reduce auth requests
3. **Least Privilege** : Only request necessary Graph API permissions
4. **Rate Limiting** : Respect Microsoft Graph API throttling (429 responses)
5. **Audit Logging** : Log all scan operations and credential access
6. **HTTPS Only** : Always use HTTPS for Graph API calls (enforced by Microsoft)

---

**Version** : 1.0.0
**Dernière mise à jour** : 2025-11-02
**Auteur** : CloudWaste Team
