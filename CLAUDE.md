# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CloudWaste** is a SaaS platform for detecting orphaned and unused cloud resources (zombies) that generate unnecessary costs for businesses. Currently supports **25 AWS resource types** + **Azure managed disks** with intelligent CloudWatch-based detection.

**Tech Stack:**
- **Frontend:** Next.js 14+ (App Router), TypeScript, React 18+, Tailwind CSS + shadcn/ui, Zustand
- **Backend:** FastAPI 0.110+, Python 3.11+, Pydantic v2, asyncio
- **Database:** PostgreSQL 15+ (SQLAlchemy 2.0 async), Redis 7+
- **Background Jobs:** Celery + Celery Beat + Redis
- **Cloud SDKs:** boto3 + aioboto3 (AWS async), azure-identity + azure-mgmt-* (Azure)

## Directory Structure

```
cloudwaste/
├── frontend/                    # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── (auth)/         # Auth pages (login, register)
│   │   │   └── (dashboard)/    # Dashboard pages (accounts, scans, resources, settings)
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui components
│   │   │   ├── layout/         # Header, Sidebar, Footer
│   │   │   ├── dashboard/      # Dashboard-specific components
│   │   │   └── charts/         # Chart components
│   │   ├── lib/                # API client, auth, utilities
│   │   ├── hooks/              # Custom React hooks
│   │   ├── stores/             # Zustand stores
│   │   ├── types/              # TypeScript types
│   │   └── config/             # App configuration
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── api/
│   │   │   ├── deps.py         # Dependencies (auth, db)
│   │   │   └── v1/             # API v1 endpoints (auth, accounts, scans, resources, costs)
│   │   ├── core/               # config.py, security.py (JWT, passwords), database.py
│   │   ├── models/             # SQLAlchemy models (user, account, scan, resource)
│   │   ├── schemas/            # Pydantic schemas (request/response)
│   │   ├── crud/               # CRUD operations
│   │   ├── providers/          # Cloud provider abstractions
│   │   │   ├── base.py         # Abstract base class
│   │   │   └── aws.py          # AWS implementation
│   │   ├── services/           # Business logic (scanner, cost_calculator)
│   │   └── workers/            # Celery tasks
│   │       ├── celery_app.py   # Celery configuration
│   │       └── tasks.py        # Celery tasks
│   ├── alembic/                # Database migrations
│   └── tests/
```

## Architecture

### Backend API Layer
- **FastAPI** serves REST API at `/api/v1/*`
- **Authentication:** JWT tokens (access + refresh pattern)
  - Access token: 15 minutes expiration
  - Refresh token: 7 days expiration
- **Key Endpoints:**
  - `/api/v1/auth/*` - JWT authentication
  - `/api/v1/accounts/*` - Cloud accounts CRUD
  - `/api/v1/scans/*` - Trigger/get scans
  - `/api/v1/resources/*` - Orphan resources
  - `/api/v1/costs/*` - Cost estimations

### Scanning System
- **Provider Abstraction:** `providers/base.py` defines abstract interface, `providers/aws.py` implements AWS-specific logic
- **Scanner Service:** `services/scanner.py` orchestrates scans across regions and resource types
- **Celery Workers:** Async background tasks for scanning cloud accounts
- **Celery Beat:** Scheduled daily scans (1x/day)

### Data Flow
1. User triggers scan (manual) or Celery Beat triggers (scheduled)
2. Scan job queued to Celery via Redis
3. Celery worker retrieves cloud credentials (decrypted from PostgreSQL)
4. AWS scanner uses boto3/aioboto3 to query resources across regions
5. Orphan resources identified and stored in `orphan_resources` table with cost estimates
6. Frontend polls/fetches scan results via API

## Development Commands

### Backend (Python)

**Setup:**
```bash
cd backend
python -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows
pip install -r requirements.txt
```

**Run development server:**
```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

**Database migrations:**
```bash
cd backend
alembic revision --autogenerate -m "description"
alembic upgrade head
```

**Run Celery worker:**
```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

**Run Celery Beat scheduler:**
```bash
cd backend
celery -A app.workers.celery_app beat --loglevel=info
```

**Testing:**
```bash
cd backend
pytest                          # Run all tests
pytest tests/api/               # Run specific directory
pytest -v --cov=app --cov-report=html  # With coverage
```

**Linting & Formatting:**
```bash
cd backend
black .                         # Format code
ruff check .                    # Lint code
mypy app/                       # Type checking
```

### Frontend (TypeScript/Next.js)

**Setup:**
```bash
cd frontend
npm install
```

**Run development server:**
```bash
cd frontend
npm run dev
```

**Build:**
```bash
cd frontend
npm run build
npm start  # Run production build
```

**Testing:**
```bash
cd frontend
npm test                        # Run tests
npm run test:watch              # Watch mode
npm run test:coverage           # With coverage
```

**Linting & Formatting:**
```bash
cd frontend
npm run lint                    # ESLint
npm run format                  # Prettier
```

### Docker Compose (Full stack)

```bash
docker-compose up -d            # Start all services
docker-compose down             # Stop all services
docker-compose logs -f          # View logs
docker-compose ps               # Check status
```

## Code Standards

### Backend (Python)

- **Type hints:** MANDATORY on all functions/methods
- **Docstrings:** Google style format
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes
- **Async/await:** Use async for all I/O bound operations
- **Line length:** 100 characters (black, ruff)
- **Error handling:** Custom exceptions in `app/core/exceptions.py`
- **Logging:** Use structlog with JSON output

Example:
```python
async def get_orphan_volumes(
    region: str,
    account_id: str
) -> List[OrphanResource]:
    """
    Retrieve all unattached EBS volumes in a specific region.

    Args:
        region: AWS region code (e.g., 'eu-west-1')
        account_id: AWS account ID

    Returns:
        List of orphan EBS volumes with cost estimates

    Raises:
        AWSCredentialsError: If AWS credentials are invalid
        RateLimitError: If AWS API rate limit exceeded
    """
    # Implementation
```

### Frontend (TypeScript)

- **Type safety:** NO `any` types, use `unknown` if necessary
- **Naming:** `camelCase` for variables/functions, `PascalCase` for components
- **Components:** React Function Components with TypeScript
- **Props:** Always type with interfaces
- **Hooks:** Custom hooks prefixed with `use`
- **API calls:** Centralized in `lib/api.ts`
- **Strict mode:** Enabled in tsconfig.json

Example:
```typescript
interface OrphanResourceCardProps {
  resource: OrphanResource;
  onIgnore: (resourceId: string) => void;
  onMarkForDeletion: (resourceId: string) => void;
}

export function OrphanResourceCard({
  resource,
  onIgnore,
  onMarkForDeletion
}: OrphanResourceCardProps) {
  // Implementation
}
```

## Security - CRITICAL RULES

### AWS Credentials
- **READ-ONLY permissions only** - NEVER allow write/delete operations
- **Encryption:** All cloud credentials encrypted in PostgreSQL using Fernet (symmetric encryption)
- **Master key:** Stored in environment variable `ENCRYPTION_KEY`
- **Rotation:** Alert users every 90 days to rotate credentials

### Required AWS IAM Permissions (Read-Only)
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": [
      "ec2:Describe*",
      "rds:Describe*",
      "s3:List*",
      "s3:Get*",
      "s3:GetBucketLocation",
      "s3:ListBucket",
      "s3:ListBucketMultipartUploads",
      "s3:ListAllMyBuckets",
      "elasticloadbalancing:Describe*",
      "fsx:Describe*",
      "neptune:Describe*",
      "neptune:List*",
      "kafka:ListClusters",
      "kafka:ListClustersV2",
      "kafka:DescribeCluster",
      "kafka:DescribeClusterV2",
      "eks:ListClusters",
      "eks:DescribeCluster",
      "eks:ListNodegroups",
      "eks:DescribeNodegroup",
      "sagemaker:ListEndpoints",
      "sagemaker:DescribeEndpoint",
      "sagemaker:DescribeEndpointConfig",
      "redshift:DescribeClusters",
      "elasticache:DescribeCacheClusters",
      "elasticache:DescribeReplicationGroups",
      "globalaccelerator:ListAccelerators",
      "globalaccelerator:ListListeners",
      "globalaccelerator:ListEndpointGroups",
      "kinesis:ListStreams",
      "kinesis:DescribeStream",
      "kinesis:DescribeStreamSummary",
      "es:DescribeDomains",
      "es:ListDomainNames",
      "docdb:DescribeDBClusters",
      "docdb:DescribeDBInstances",
      "lambda:ListFunctions",
      "lambda:GetFunction",
      "lambda:GetFunctionConfiguration",
      "lambda:GetProvisionedConcurrencyConfig",
      "dynamodb:ListTables",
      "dynamodb:DescribeTable",
      "dynamodb:DescribeTimeToLive",
      "ce:GetCostAndUsage",
      "ce:GetCostForecast",
      "cloudwatch:GetMetricStatistics",
      "cloudwatch:ListMetrics",
      "sts:GetCallerIdentity"
    ],
    "Resource": "*"
  }]
}
```

### Required Azure Permissions (Read-Only)
Azure requires a **Service Principal** with:
- **Reader** role on subscription
- **Monitoring Reader** role (for metrics)

```bash
az ad sp create-for-rbac --name "CloudWaste-Scanner" \
  --role "Reader" \
  --scopes "/subscriptions/{subscription-id}"
```

### Authentication
- Password hashing: bcrypt (cost factor 12)
- JWT tokens with access/refresh pattern
- HTTPS only (TLS 1.3)
- Input validation: Strict Pydantic validation, ORM only (NO raw SQL)

### CORS Security
CloudWaste implements **strict CORS (Cross-Origin Resource Sharing) validation** to prevent:
- **Cross-origin attacks** - Unauthorized websites accessing the API
- **Header injection** - Malicious custom headers
- **Credential theft** - Cookies/tokens stolen via CORS misconfiguration
- **Wildcard exploits** - `*` origin bypassing security

**Security Rules:**
1. **No Wildcards** - `allow_origins` uses explicit whitelist only (no `*`)
2. **Strict Validation** - All origins validated at startup via Pydantic validators
3. **HTTPS in Production** - Only HTTPS origins allowed (except localhost/127.0.0.1)
4. **Valid URL Format** - Origins must include scheme and hostname (e.g., `https://cloudwaste.com`)
5. **Explicit Methods** - Only required HTTP methods allowed (no `allow_methods=["*"]`)
6. **Explicit Headers** - Only required headers allowed (no `allow_headers=["*"]`)
7. **CORS Logging** - All cross-origin requests logged for security monitoring

**Implementation:**
```python
# backend/app/core/config.py - Strict Pydantic validation
ALLOWED_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

@field_validator("ALLOWED_ORIGINS")
def validate_cors_origins(cls, origins: List[str], info) -> List[str]:
    # Rejects wildcards, validates URL format, enforces HTTPS in production
    # See backend/app/core/config.py:validate_cors_origins for full implementation
```

```python
# backend/app/main.py - Explicit CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,              # Validated whitelist
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,   # JWT cookies
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],  # Explicit
    allow_headers=[
        "Content-Type",
        "Authorization",
        "Accept",
        "Origin",
        "X-Requested-With",
        "X-CSRF-Token",
    ],  # Explicit whitelist (no *)
    max_age=settings.CORS_MAX_AGE,  # Preflight cache (600s default)
)
```

**Configuration:**
```bash
# Development (HTTP allowed for localhost)
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=true
CORS_MAX_AGE=600

# Production (HTTPS only)
APP_ENV=production
ALLOWED_ORIGINS=https://cloudwaste.com,https://www.cloudwaste.com,https://app.cloudwaste.com
CORS_ALLOW_CREDENTIALS=true
CORS_MAX_AGE=600
```

**Validation Rules:**

✅ **Valid Origins:**
```python
# Development
"http://localhost:3000"
"http://127.0.0.1:8080"
"https://cloudwaste.com"

# Production (HTTPS required except localhost)
"https://cloudwaste.com"
"https://www.cloudwaste.com"
"http://localhost:3000"  # Still allowed in production for local testing
```

❌ **Rejected Origins:**
```python
"*"                              # Wildcard rejected
"http://*.cloudwaste.com"        # Wildcard in domain rejected
"cloudwaste.com"                 # Missing scheme
"http://"                        # Missing hostname
""                               # Empty string
"http://cloudwaste.com"          # HTTP rejected in production (non-localhost)
```

**CORS Logging Middleware:**
All cross-origin requests are logged via `CORSLoggingMiddleware` for security monitoring:
```json
{
  "event": "cors.request",
  "method": "GET",
  "path": "/api/v1/resources",
  "origin": "https://cloudwaste.com",
  "is_preflight": false,
  "status_code": 200,
  "user_agent": "Mozilla/5.0..."
}
```

Rejected CORS requests (403) are logged at **warning level** for alerting:
```json
{
  "event": "cors.request_forbidden",
  "origin": "https://malicious-site.com",
  "status_code": 403,
  "reason": "Origin likely not in ALLOWED_ORIGINS whitelist"
}
```

**Adding New Origins:**
1. Update `.env` (development) or `.env.production` (production):
```bash
ALLOWED_ORIGINS=https://cloudwaste.com,https://new-domain.com
```

2. Restart backend:
```bash
docker-compose restart backend
```

3. Verify in logs:
```
INFO: ✅ CORS origins validated: ['https://cloudwaste.com', 'https://new-domain.com']
```

**Testing:**
```bash
cd backend

# Unit tests - CORS validation logic
pytest tests/core/test_cors_validation.py -v

# Integration tests - CORS middleware behavior
pytest tests/api/test_cors_integration.py -v
```

**Security Checklist:**
- ✅ No wildcards in `ALLOWED_ORIGINS`
- ✅ HTTPS enforced in production (except localhost)
- ✅ Explicit `allow_methods` (no `["*"]`)
- ✅ Explicit `allow_headers` (no `["*"]`)
- ✅ CORS logging enabled
- ✅ Origins validated at startup (fail-fast)
- ✅ Tests covering validation rules

### Rate Limiting
CloudWaste implements API rate limiting using **SlowAPI** with Redis backend to prevent:
- **DDoS attacks** - Distributed denial of service
- **Brute-force attacks** - Password guessing on login
- **Resource enumeration** - Scanning for valid accounts
- **API abuse** - Excessive scan requests

**Implementation:**
- Rate limiting by user ID (authenticated) or IP address (unauthenticated)
- Redis-backed storage for distributed rate limiting
- Automatic retry headers (X-RateLimit-*)
- Configurable limits per endpoint type

**Default Rate Limits:**
```
Authentication Endpoints:
- POST /api/v1/auth/login            → 5/minute   (brute-force protection)
- POST /api/v1/auth/register         → 3/minute   (spam prevention)
- POST /api/v1/auth/refresh          → 10/minute  (token refresh)
- POST /api/v1/auth/resend-verification → 3/minute (email spam prevention)

Resource-Intensive Endpoints:
- POST /api/v1/scans/                → 10/minute  (cloud scans)

Standard API Endpoints:
- POST /api/v1/accounts/             → 100/minute (account creation)
- GET  /api/v1/resources/*           → 100/minute (default)
- GET  /api/v1/scans/*               → 100/minute (default)

Admin Endpoints:
- /api/v1/admin/*                    → 50/minute
```

**Configuration:**
Rate limits can be adjusted via environment variables:
```bash
RATE_LIMIT_ENABLED=true                    # Enable/disable rate limiting
RATE_LIMIT_AUTH_LOGIN=5/minute            # Login attempts
RATE_LIMIT_AUTH_REGISTER=3/minute         # Registration
RATE_LIMIT_AUTH_REFRESH=10/minute         # Token refresh
RATE_LIMIT_SCANS=10/minute                # Cloud scans
RATE_LIMIT_ADMIN=50/minute                # Admin operations
RATE_LIMIT_API_DEFAULT=100/minute         # Default for all endpoints
```

**Response Headers:**
All API responses include rate limit information:
```
X-RateLimit-Limit: 5                      # Max requests allowed
X-RateLimit-Remaining: 3                  # Requests remaining
X-RateLimit-Reset: 1699876543             # Unix timestamp when limit resets
```

**Error Response (429 Too Many Requests):**
```json
{
  "error": "Rate limit exceeded: 5 per 1 minute"
}
```

**Testing:**
```bash
cd backend
pytest tests/api/test_rate_limiting.py -v
```

## Database Schema

### Core Tables
- **users:** User accounts (id, email, hashed_password, full_name, is_active, created_at)
- **cloud_accounts:** Cloud provider accounts (id, user_id, provider ['aws'|'azure'], account_identifier, credentials_encrypted, regions, last_scan_at)
- **scans:** Scan jobs (id, cloud_account_id, status, scan_type, total_resources_scanned, orphan_resources_found, estimated_monthly_waste, started_at, completed_at)
- **orphan_resources:** Detected resources (id, scan_id, cloud_account_id, resource_type, resource_id, resource_name, region, estimated_monthly_cost, resource_metadata, status ['active'|'ignored'|'marked_for_deletion'])
- **detection_rules:** User-specific detection rules (id, user_id, resource_type, rules [JSON], created_at, updated_at)

## Resource Detection Scope

CloudWaste detects **25 AWS resource types** + **Azure managed disks** with intelligent detection:

### Core AWS Resources (7 types)
1. **EBS Volumes** - Unattached + idle volumes with CloudWatch I/O analysis
2. **Elastic IPs** - Unassociated IP addresses (~$3.60/month)
3. **EBS Snapshots** - Orphaned, redundant, and unused AMI snapshots
4. **EC2 Instances** - Stopped >30 days + idle running (<5% CPU)
5. **Load Balancers** - 7 scenarios: no backends, no listeners, never used, etc. (ALB/NLB/CLB/GWLB)
6. **RDS Instances** - 5 scenarios: stopped, idle, zero I/O, never connected, no backups
7. **NAT Gateways** - 4 scenarios: no traffic, no routing, misconfigured

### Advanced AWS Resources (18 types)
8. **FSx File Systems** - 8 scenarios across Lustre/Windows/ONTAP/OpenZFS
9. **Neptune Clusters** - Graph databases with no connections
10. **MSK Clusters** - Kafka clusters with no data traffic
11. **EKS Clusters** - 5 scenarios: no nodes, unhealthy, low CPU, misconfigured
12. **SageMaker Endpoints** - ML endpoints with no invocations
13. **Redshift Clusters** - Data warehouses with no connections
14. **ElastiCache** - 4 scenarios: zero hits, low hit rate, no connections, over-provisioned
15. **VPN Connections** - VPN with no data transfer
16. **Transit Gateway Attachments** - Attachments with no traffic
17. **OpenSearch Domains** - Domains with no search requests
18. **Global Accelerator** - Accelerators with no endpoints
19. **Kinesis Streams** - 6 scenarios: inactive, under-utilized, excessive retention
20. **VPC Endpoints** - Endpoints with no network interfaces
21. **DocumentDB Clusters** - Document databases with no connections
22. **S3 Buckets** - 4 scenarios: empty, old objects, incomplete uploads, no lifecycle
23. **Lambda Functions** - 4 scenarios: unused provisioned concurrency, never invoked, 100% failures
24. **DynamoDB Tables** - 5 scenarios: over-provisioned, unused GSI, never used, empty

### Azure Resources (1 type)
25. **Managed Disks** - Unattached Azure disks with SKU-based cost calculation

### Key Detection Features
- **CloudWatch Metrics Analysis** - Actual usage patterns, not just status checks
- **Confidence Levels** - Critical (90+ days), High (30+ days), Medium (7-30 days), Low (<7 days)
- **Cost Calculation** - Future waste (monthly) + Already wasted (cumulative since creation)
- **Detection Rules System** - User-customizable thresholds per resource type
- **Multi-Scenario Detection** - Advanced resources have 4-8 detection scenarios each

## Testing Requirements

- **Backend coverage:** Minimum 70%
- **Frontend coverage:** Minimum 60%
- **Backend:** pytest + pytest-asyncio + pytest-cov
- **Frontend:** Jest + React Testing Library
- Use async fixtures for database tests
- Test critical user flows and API endpoints

## Git Workflow

- **Branches:** `main` (production), `develop` (integration), `feature/*`, `fix/*`
- **Commits:** Conventional Commits format
  ```
  feat(api): add AWS EBS volume scanner
  fix(frontend): resolve dashboard loading state
  docs(readme): update setup instructions
  ```
- **Pre-commit hooks:** black, ruff, mypy (backend), prettier, eslint (frontend)

## Critical Rules

### DO ✅
1. Always type variables (Python type hints + TypeScript)
2. Always validate inputs (Pydantic backend, Zod frontend)
3. Always handle errors with try/except
4. Always use async/await for I/O operations
5. Always encrypt credentials before storage
6. Always test AWS permissions are read-only
7. Always log errors using structlog
8. Always follow imposed directory structure

### DON'T ❌
1. NEVER store credentials in plain text
2. NEVER use `any` in TypeScript without strong reason
3. NEVER write raw SQL queries (ORM only)
4. NEVER commit secrets (keep .env in .gitignore)
5. NEVER give write/delete permissions to AWS IAM roles
6. NEVER skip input validation
7. NEVER expose stack traces in production
8. NEVER use unmaintained dependencies

## Performance Targets

- API response time: < 200ms (P95)
- Scan time: < 5 minutes for 1000 resources
- Frontend FCP: < 1.5s
- Database queries: < 50ms (with proper indexes)
- Concurrent scans: Support 10 accounts simultaneously

## Environment Variables

### Backend `.env`
```bash
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cloudwaste
REDIS_URL=redis://localhost:6379/0
ENCRYPTION_KEY=your-fernet-encryption-key
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Frontend `.env.local`
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=CloudWaste
```

## GDPR/Legal Compliance

CloudWaste is **fully compliant** with the General Data Protection Regulation (GDPR - Regulation EU 2016/679) and other applicable data protection laws.

### Legal Pages

All legal pages are publicly accessible at `/legal/*`:

1. **Privacy Policy** (`/legal/privacy`)
   - GDPR Article 13/14 compliant
   - Explains data collection, legal basis, retention, user rights
   - Clear instructions for exercising GDPR rights (access, rectification, erasure, portability)
   - Contact details for Data Protection Officer (DPO)
   - Complaint process to supervisory authorities

2. **Terms of Service** (`/legal/terms`)
   - User responsibilities and prohibited activities
   - Service description and limitations
   - Intellectual property rights
   - Liability disclaimers
   - Termination conditions
   - Governing law and jurisdiction

3. **Cookie Policy** (`/legal/cookies`)
   - Complete cookie inventory with purposes and durations
   - Three categories: Essential, Functional, Analytics
   - No advertising or tracking cookies
   - Instructions for managing cookies
   - Do Not Track (DNT) respect

4. **Legal Notice** (`/legal/legal-notice`)
   - Publisher information (company, SIRET, VAT)
   - Hosting information
   - Publication director
   - Data Protection Officer contact
   - Intellectual property notices

### Cookie Consent Banner

**Component:** `/frontend/src/components/legal/CookieBanner.tsx`

**GDPR Compliance Features:**
- ✅ Displayed before any non-essential cookies are set
- ✅ Clear and specific consent (not pre-checked boxes)
- ✅ Easy to accept or reject all cookies
- ✅ Granular control for cookie categories
- ✅ "Do Not Track" (DNT) browser signal respected
- ✅ Consent stored in localStorage with timestamp
- ✅ User can withdraw consent anytime via "Cookie Settings" link

**Implementation:**
```typescript
// Integrated in app/layout.tsx
import { CookieBanner } from "@/components/legal/CookieBanner";

// User can reopen settings via footer or:
window.openCookieSettings(); // Call from anywhere
```

**Cookie Categories:**
- **Essential** (always active): Authentication, security (JWT, CSRF)
- **Functional** (optional): Theme, language preferences
- **Analytics** (optional): Google Analytics 4 (anonymized)

### Footer with Legal Links

**Component:** `/frontend/src/components/legal/Footer.tsx`

**Features:**
- Links to all legal pages
- "Cookie Settings" button to reopen consent banner
- GDPR compliance badges
- Company contact information

**Integration:**
```typescript
import { Footer } from "@/components/layout/Footer";

// Add to page layouts:
<Footer />
```

### User Rights (GDPR Articles 15-22)

Users can exercise their rights via the dashboard or email:

1. **Right to Access (Art. 15):**
   - Dashboard: Settings → Privacy → Export My Data (JSON)
   - API: `GET /api/v1/gdpr/export-my-data`

2. **Right to Erasure (Art. 17):**
   - Dashboard: Settings → Privacy → Delete My ML Data
   - API: `DELETE /api/v1/gdpr/delete-my-ml-data`
   - Full account deletion: contact privacy@cloudwaste.com

3. **Right to Rectification (Art. 16):**
   - Dashboard: Settings → Profile (update name, email, preferences)
   - API: `PATCH /api/v1/auth/me`

4. **Right to Data Portability (Art. 20):**
   - Export returns machine-readable JSON format

5. **Right to Object (Art. 21):**
   - ML data collection is opt-in (explicit consent required)
   - Email marketing requires consent

**Response Time:** We respond to GDPR requests within **30 days** as required by Article 12.

### Data Protection by Design

**Technical Measures:**
- **Encryption at rest:** Fernet (cloud credentials), bcrypt (passwords)
- **Encryption in transit:** TLS 1.3
- **Pseudonymization:** ML data is fully anonymized (no AWS account IDs, no resource names)
- **Access control:** Role-based, least-privilege principle
- **Data minimization:** Only collect what's necessary for service delivery
- **Retention limits:** User-configurable (1-3 years), automatic cleanup

**Organizational Measures:**
- Data Protection Officer (DPO) appointed
- Privacy Impact Assessment (PIA) conducted
- Staff training on GDPR compliance
- Data breach notification procedures (72h requirement)

### Legal Placeholders to Update

Before production, update these placeholders in legal pages:

```bash
# Search and replace in /frontend/src/app/legal/**/page.tsx:
[YOUR COMPANY ADDRESS]      → Your actual address
[SIRET/VAT NUMBER]          → Your company registration numbers
[YOUR COUNTRY/STATE]        → Your jurisdiction
[HOSTING PROVIDER NAME]     → Your hosting provider
[YOUR JURISDICTION]         → Courts with jurisdiction
```

### Compliance Checklist

- ✅ Privacy Policy (GDPR-compliant)
- ✅ Terms of Service
- ✅ Cookie Policy
- ✅ Legal Notice (Mentions Légales)
- ✅ Cookie Consent Banner (opt-in, granular, withdrawable)
- ✅ Footer with legal links
- ✅ User data export (JSON format)
- ✅ User data deletion
- ✅ ML data opt-in consent
- ✅ Encrypted cloud credentials
- ✅ Do Not Track (DNT) respect
- ✅ Email verification
- ✅ GDPR rights UI (Settings → Privacy)
- ⏳ Data Protection Officer (DPO) contact setup
- ⏳ Supervisory authority registration (if required in your country)

**Non-Compliance Risk:** Failure to comply with GDPR can result in fines up to **€20 million or 4% of annual global turnover**, whichever is higher.

## Definition of Done

A feature is complete when:
1. Code implemented following standards
2. Tests written (≥70% backend, ≥60% frontend coverage)
3. Documentation updated (docstrings, README)
4. Code reviewed
5. Manual testing completed
6. No blocking bugs
7. Logging and error handling in place
8. Commits pushed to branch
