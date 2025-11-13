# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CloudWaste** is a SaaS platform for detecting orphaned and unused cloud resources (zombies) that generate unnecessary costs for businesses. Currently supports **25 AWS resource types** + **Azure resources** + **14+ GCP resource types** + **Microsoft 365** with intelligent CloudWatch-based detection.


**Key Features:**
- **Multi-Cloud Support:** AWS (25 types), Azure (managed disks + more), GCP (14+ types), Microsoft 365 (SharePoint/OneDrive)
- **AI Chat Assistant:** Anthropic Claude Haiku 4.5 integration with context-aware responses
- **ML Data Collection:** Phase 1 complete with 6 PostgreSQL tables for future ML model training
- **Dynamic Pricing:** Real-time AWS Pricing API integration with PostgreSQL cache
- **GDPR Compliance:** Full data export, deletion, consent management, and legal pages
- **Onboarding System:** 5-step wizard for new users
- **Impact Tracking:** CO2 emissions and environmental impact visualization
- **Email Verification:** Token-based verification with auto-cleanup
- **Comprehensive Error Handling:** Custom error boundaries, states, and pages

**Tech Stack:**
- **Frontend:** Next.js 14+ (App Router), TypeScript, React 18+, Tailwind CSS + shadcn/ui, Zustand
- **Backend:** FastAPI 0.110+, Python 3.11+, Pydantic v2, asyncio
- **Database:** PostgreSQL 15+ (SQLAlchemy 2.0 async), Redis 7+
- **Background Jobs:** Celery + Celery Beat + Redis
- **Cloud SDKs:** boto3 + aioboto3 (AWS async), azure-identity + azure-mgmt-* (Azure), google-cloud-* (GCP), msgraph-core (M365)
- **AI:** Anthropic Claude Haiku 4.5 (claude-haiku-4-5-20250818)
- **Rate Limiting:** SlowAPI + Redis
- **Streaming:** SSE (Server-Sent Events) for chat responses
- **Error Tracking:** Sentry (backend + frontend integration)

## Directory Structure

```
cloudwaste/
├── frontend/                    # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── (auth)/         # Auth pages (login, register, verify-email)
│   │   │   ├── (dashboard)/    # Dashboard pages (accounts, scans, resources, settings, admin)
│   │   │   │   └── dashboard/
│   │   │       ├── page.tsx    # Main dashboard
│   │   │       ├── accounts/   # Cloud accounts management
│   │   │       ├── scans/      # Scan history
│   │   │       ├── resources/  # Orphan resources list
│   │   │       ├── settings/   # User settings
│   │   │       ├── impact/     # Environmental impact dashboard
│   │   │       ├── assistant/  # AI chat assistant
│   │   │       ├── docs/       # Documentation page
│   │   │       └── admin/      # Admin panel (pricing, stats)
│   │   │   ├── legal/          # Legal pages (privacy, terms, cookies, legal-notice)
│   │   │   ├── onboarding/     # Onboarding wizard
│   │   │   ├── error.tsx       # Error page
│   │   │   ├── not-found.tsx   # 404 page
│   │   │   └── global-error.tsx # Global error handler
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui components
│   │   │   ├── layout/         # Header, Sidebar, Footer, BackToTop
│   │   │   ├── dashboard/      # Dashboard-specific components
│   │   │   ├── charts/         # Chart components
│   │   │   ├── chat/           # AI chat components (ChatWindow, ChatMessage, etc.)
│   │   │   ├── onboarding/     # Onboarding wizard components
│   │   │   ├── errors/         # Error handling components (ErrorBoundary, ErrorState, etc.)
│   │   │   ├── legal/          # Legal components (CookieBanner, Footer)
│   │   │   └── detection/      # Detection rules UI (BasicModeView, ExpertModeView)
│   │   ├── lib/                # API client, auth, utilities
│   │   ├── hooks/              # Custom React hooks (useOnboarding, useErrorHandler, useNotifications)
│   │   ├── stores/             # Zustand stores (auth, accounts, scans, resources, chat, onboarding, impact)
│   │   ├── types/              # TypeScript types (index, errors, onboarding, impact)
│   │   └── config/             # App configuration
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── api/
│   │   │   ├── deps.py         # Dependencies (auth, db)
│   │   │   └── v1/             # API v1 endpoints
│   │   │       ├── auth.py         # Authentication (JWT, registration, email verification)
│   │   │       ├── accounts.py     # Cloud accounts CRUD
│   │   │       ├── scans.py        # Scan triggers and results
│   │   │       ├── resources.py    # Orphan resources
│   │   │       ├── costs.py        # Cost estimations
│   │   │       ├── detection_rules.py  # Detection rules management
│   │   │       ├── chat.py         # AI chat assistant (SSE streaming)
│   │   │       ├── impact.py       # Environmental impact tracking
│   │   │       ├── gdpr.py         # GDPR compliance (data export, deletion)
│   │   │       ├── admin.py        # Admin endpoints
│   │   │       ├── admin_pricing.py # Dynamic pricing management
│   │   │       ├── user_preferences.py # User settings
│   │   │       └── test_detection.py # Testing endpoints (DEBUG mode only)
│   │   ├── core/               # Core configuration
│   │   │   ├── config.py       # Settings (Pydantic BaseSettings)
│   │   │   ├── security.py     # JWT, password hashing
│   │   │   ├── database.py     # SQLAlchemy async engine
│   │   │   └── rate_limit.py   # SlowAPI rate limiting
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── user.py         # User accounts (with email verification)
│   │   │   ├── account.py      # Cloud accounts
│   │   │   ├── scan.py         # Scans
│   │   │   ├── resource.py     # Orphan resources
│   │   │   ├── detection_rule.py   # Detection rules
│   │   │   ├── chat.py         # Chat conversations & messages
│   │   │   ├── user_preferences.py # User preferences
│   │   │   ├── pricing_cache.py    # Dynamic pricing cache
│   │   │   ├── resource_families.py # Resource categorization
│   │   │   ├── ml_training_data.py # ML training data
│   │   │   ├── resource_lifecycle_event.py # Resource change tracking
│   │   │   ├── cloudwatch_metrics_history.py # Historical metrics
│   │   │   ├── user_action_pattern.py # User behavior tracking
│   │   │   └── cost_trend_data.py # Cost analysis
│   │   ├── schemas/            # Pydantic schemas (request/response)
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── scan.py
│   │   │   ├── resource.py
│   │   │   ├── detection_rule.py
│   │   │   ├── chat.py
│   │   │   ├── impact.py
│   │   │   ├── user_preferences.py
│   │   │   └── admin_pricing.py
│   │   ├── crud/               # CRUD operations
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── scan.py
│   │   │   ├── resource.py
│   │   │   ├── detection_rule.py
│   │   │   ├── chat.py
│   │   │   └── impact.py
│   │   ├── providers/          # Cloud provider abstractions
│   │   │   ├── base.py         # Abstract base class
│   │   │   ├── aws.py          # AWS implementation (25 resource types)
│   │   │   ├── azure.py        # Azure implementation
│   │   │   ├── gcp.py          # GCP implementation (14+ resource types)
│   │   │   └── microsoft365.py # Microsoft 365 implementation
│   │   ├── services/           # Business logic
│   │   │   ├── scanner.py          # Orchestration of scans
│   │   │   ├── cost_calculator.py  # Cost calculations
│   │   │   ├── chat_service.py     # AI chat logic (Anthropic)
│   │   │   ├── pricing_service.py  # Dynamic pricing (AWS Pricing API)
│   │   │   ├── email_service.py    # Email sending
│   │   │   ├── ses_metrics_service.py # AWS SES monitoring
│   │   │   ├── gdpr_compliance.py  # GDPR data export/deletion
│   │   │   ├── ml_anonymization.py # ML data anonymization
│   │   │   ├── ml_data_collector.py # ML data collection
│   │   │   ├── user_action_tracker.py # User behavior tracking
│   │   │   ├── aws_validator.py    # AWS credentials validation
│   │   │   ├── azure_validator.py  # Azure credentials validation
│   │   │   └── microsoft365_validator.py # M365 credentials validation
│   │   ├── ml/                 # Machine Learning pipeline
│   │   │   ├── __init__.py
│   │   │   └── data_pipeline.py    # ML data processing
│   │   ├── middleware/         # Custom middleware
│   │   │   ├── __init__.py
│   │   │   └── cors_logging.py # CORS logging for security
│   │   └── workers/            # Celery tasks
│   │       ├── celery_app.py   # Celery configuration
│   │       ├── tasks.py        # Scan tasks
│   │       └── ml_tasks.py     # ML data collection tasks
│   ├── alembic/                # Database migrations
│   └── tests/                  # Test suite
│       ├── api/                # API endpoint tests
│       ├── providers/          # Provider tests
│       ├── services/           # Service tests
│       └── core/               # Core tests (CORS, rate limiting)
│
├── docs/                        # Documentation
│   └── ml/                     # ML documentation
│       ├── README.md
│       ├── 01_CURRENT_STATUS.md
│       ├── 02_ARCHITECTURE.md
│       ├── 03_USAGE_GUIDE.md
│       ├── 04_NEXT_PHASES.md
│       └── 05_TROUBLESHOOTING.md
│
├── docker-compose.yml          # Dev environment
├── .env.example
├── .gitignore
├── README.md                   # Setup guide
├── CLAUDE.md                   # This file (project guide for Claude Code)
├── TESTING.md                  # Comprehensive testing guide
├── ML_README.md                # ML documentation index
└── STRATEGIC_VISION.md         # Product vision
```

## Architecture

### Backend API Layer
- **FastAPI** serves REST API at `/api/v1/*`
- **Authentication:** JWT tokens (access + refresh pattern)
  - Access token: 15 minutes expiration
  - Refresh token: 7 days expiration (30 days with "Remember Me")
  - Email verification required for new accounts
- **Key Endpoints:**
  - `/api/v1/auth/*` - JWT authentication, registration, email verification
  - `/api/v1/accounts/*` - Cloud accounts CRUD
  - `/api/v1/scans/*` - Trigger/get scans
  - `/api/v1/resources/*` - Orphan resources
  - `/api/v1/costs/*` - Cost estimations
  - `/api/v1/detection-rules/*` - Detection rules management
  - `/api/v1/chat/*` - AI chat assistant (SSE streaming)
  - `/api/v1/impact/*` - Environmental impact tracking
  - `/api/v1/gdpr/*` - GDPR compliance (data export, deletion)
  - `/api/v1/preferences/*` - User preferences
  - `/api/v1/admin/*` - Admin endpoints
  - `/api/v1/admin/pricing/*` - Dynamic pricing management
  - `/api/v1/test/*` - Testing endpoints (DEBUG mode only)

### Scanning System
- **Provider Abstraction:** `providers/base.py` defines abstract interface
- **Provider Implementations:**
  - `providers/aws.py` - AWS (25 resource types)
  - `providers/azure.py` - Azure (managed disks + more)
  - `providers/gcp.py` - GCP (14+ resource types)
  - `providers/microsoft365.py` - Microsoft 365 (SharePoint/OneDrive)
- **Scanner Service:** `services/scanner.py` orchestrates scans across regions and resource types
- **Celery Workers:** Async background tasks for scanning cloud accounts
- **Celery Beat:** Scheduled daily scans (1x/day)

### Data Flow
1. User triggers scan (manual) or Celery Beat triggers (scheduled)
2. Scan job queued to Celery via Redis
3. Celery worker retrieves cloud credentials (decrypted from PostgreSQL)
4. Provider scanner uses cloud SDK to query resources across regions
5. Orphan resources identified and stored in `orphan_resources` table with cost estimates
6. **ML Data Collection:** Anonymized metrics collected in parallel (opt-in)
7. Frontend polls/fetches scan results via API

### AI Chat Assistant Flow
1. User sends message via `/api/v1/chat/messages` (SSE endpoint)
2. Backend fetches user's recent orphan resources for context
3. Anthropic Claude API called with streaming enabled
4. Response streamed back to frontend via Server-Sent Events
5. Conversation saved to `chat_conversations` and `chat_messages` tables
6. Rate limiting: 50 messages/user/day

### Dynamic Pricing Flow
1. **Celery Beat** triggers daily pricing refresh (2 AM UTC)
2. `pricing_service.py` queries AWS Pricing API for each service/region
3. Prices cached in `pricing_cache` table with 24h TTL
4. During scans, pricing service checks cache first (fallback to hardcoded if stale)
5. Admin can manually trigger refresh via `/api/v1/admin/pricing/refresh`
6. Dashboard shows cache statistics (hit rate, API success rate)

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
docker-compose logs -f celery_worker  # View Celery worker logs
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
- **Key validation:** Startup checks ensure key hasn't changed (data loss protection)
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
      "sts:GetCallerIdentity",
      "pricing:GetProducts"
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

### Required GCP Permissions (Read-Only)
GCP requires a **Service Account** with these roles:
- **Compute Viewer** (compute.viewer)
- **Monitoring Viewer** (monitoring.viewer)
- **Storage Object Viewer** (storage.objectViewer)
- **Container Engine Viewer** (container.viewer)

### Required Microsoft 365 Permissions (Read-Only)
Microsoft 365 requires:
- **Sites.Read.All** (SharePoint)
- **Files.Read.All** (OneDrive)

### Authentication
- Password hashing: bcrypt (cost factor 12)
- JWT tokens with access/refresh pattern
- HTTPS only (TLS 1.3)
- Input validation: Strict Pydantic validation, ORM only (NO raw SQL)
- Email verification: 7-day token expiration
- Auto-cleanup: Unverified accounts deleted after 14 days

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
- **users:** User accounts (id, email, hashed_password, full_name, is_active, is_superuser, email_verified, email_verification_token, verification_token_expires_at, email_scan_notifications, created_at, updated_at)
- **cloud_accounts:** Cloud provider accounts (id, user_id, provider ['aws'|'azure'|'gcp'|'microsoft365'], account_identifier, credentials_encrypted, regions, resource_groups, scheduled_scan_enabled, scheduled_scan_time, last_scan_at, created_at, updated_at)
- **scans:** Scan jobs (id, cloud_account_id, status, scan_type, total_resources_scanned, orphan_resources_found, estimated_monthly_waste, started_at, completed_at, duration_seconds, error_message, created_at)
- **orphan_resources:** Detected resources (id, scan_id, cloud_account_id, resource_type, resource_id, resource_name, region, estimated_monthly_cost, currency, resource_metadata, last_used_at, created_at_cloud, status ['active'|'ignored'|'marked_for_deletion'], ignored_at, ignored_reason, created_at, updated_at)
- **detection_rules:** User-specific detection rules (id, user_id, resource_type, rules [JSON], created_at, updated_at)

### AI & Chat Tables
- **chat_conversations:** Chat sessions (id, user_id, title, created_at, updated_at)
- **chat_messages:** Chat messages (id, conversation_id, role ['user'|'assistant'], content, created_at)

### User Preferences & Settings
- **user_preferences:** User settings (id, user_id, theme, language, timezone, notifications_enabled, ml_data_collection_consent, data_retention_days, created_at, updated_at)

### Dynamic Pricing Tables
- **pricing_cache:** Cached pricing data (id, provider, service, region, price_per_unit, unit, currency, source ['api'|'fallback'], last_updated, expires_at, metadata, created_at)

### ML Data Collection Tables (Phase 1)
- **ml_training_data:** Anonymized resource data (id, provider, resource_type, region, detection_scenario, confidence_level, resource_age_days, estimated_monthly_cost, resource_size_gb, anonymized_metadata, user_action ['ignored'|'deleted'|'kept'], user_action_at, scan_timestamp, created_at)
- **resource_lifecycle_event:** Resource change tracking (id, resource_id, event_type, previous_state, new_state, anonymized_metadata, created_at)
- **cloudwatch_metrics_history:** Historical metrics (id, resource_id, metric_name, metric_value, timestamp, created_at)
- **user_action_pattern:** User behavior (id, user_id_anonymized, resource_type, action_type, action_frequency, created_at)
- **cost_trend_data:** Cost analysis (id, provider, resource_type, region, avg_monthly_cost, median_monthly_cost, p95_monthly_cost, sample_count, period_start, period_end, created_at)
- **resource_families:** Resource categories (id, family_name, resource_types, description, created_at)

## Resource Detection Scope

CloudWaste detects **25 AWS resource types** + **Azure resources** + **14+ GCP resource types** + **Microsoft 365** with intelligent detection:

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
25. **EC2 Instances (Enhanced)** - Stopped instances + idle running instances

### Azure Resources
- **Managed Disks** - Unattached Azure disks with SKU-based cost calculation
- **Public IPs** - Unassociated public IP addresses
- **Virtual Machines** - Stopped/deallocated VMs
- **AKS Clusters** - Azure Kubernetes Service clusters (Phase A detection)
- *(Note: Azure support is expanding with additional resource types in development)*

### GCP Resources (14+ types)
1. **Compute Engine Instances** - Stopped/idle VMs
2. **Persistent Disks** - Unattached disks
3. **Snapshots** - Orphaned snapshots
4. **Cloud Storage Buckets** - Empty/unused buckets
5. **GKE Clusters** - Idle Kubernetes clusters
6. **Cloud Run Services** - Unused serverless services
7. **Cloud Functions** - Unused functions (1st and 2nd gen)
8. **Cloud Filestore** - Unused NFS instances
9. **Cloud Firestore** - Idle NoSQL databases
10. **Cloud Bigtable** - Unused Bigtable instances
11. **Cloud Memorystore (Redis)** - Idle Redis instances
12. **BigQuery** - Unused datasets/tables
13. **Cloud Dataproc** - Idle Hadoop/Spark clusters
14. **Vertex AI** - Unused ML endpoints and notebooks

### Microsoft 365 Resources
- **SharePoint Sites** - Unused sites with no activity
- **OneDrive Files** - Abandoned files with no access

### Key Detection Features
- **CloudWatch/Azure Monitor/Cloud Monitoring** - Actual usage patterns, not just status checks
- **Confidence Levels** - Critical (90+ days), High (30+ days), Medium (7-30 days), Low (<7 days)
- **Cost Calculation** - Future waste (monthly) + Already wasted (cumulative since creation)
- **Detection Rules System** - User-customizable thresholds per resource type
- **Multi-Scenario Detection** - Advanced resources have 4-8 detection scenarios each
- **Dynamic Pricing** - Real-time pricing from AWS Pricing API (with fallback)

## AI Chat Assistant

CloudWaste includes an **AI-powered chat assistant** using **Anthropic Claude Haiku 4.5** for intelligent resource analysis and recommendations.

### Features
- **Context-Aware:** Automatically includes user's recent orphan resources in chat context
- **Streaming Responses:** Real-time streaming via Server-Sent Events (SSE)
- **Conversation History:** Persistent chat sessions stored in PostgreSQL
- **Rate Limited:** 50 messages per user per day (configurable)
- **Multi-turn Conversations:** Maintains conversation context across messages

### Architecture
- **Model:** Claude Haiku 4.5 (claude-haiku-4-5-20250818)
- **Streaming:** SSE (Server-Sent Events) via `sse-starlette`
- **Context:** Up to 20 recent orphan resources included in each message
- **Backend:** `/api/v1/chat/*` endpoints
- **Frontend:** Real-time chat UI with streaming message display

### Configuration
```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional (defaults shown)
CHAT_MAX_MESSAGES_PER_USER_PER_DAY=50
CHAT_CONTEXT_MAX_RESOURCES=20
CHAT_MODEL=claude-haiku-4-5-20250818
```

### Usage
**Start conversation:**
```bash
POST /api/v1/chat/conversations
```

**Send message (SSE):**
```bash
POST /api/v1/chat/messages
Content-Type: text/event-stream
{
  "conversation_id": "uuid",
  "content": "What are my most expensive orphan resources?"
}
```

**Response (streaming):**
```
data: {"type": "content_block_start", "index": 0}
data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Based"}}
data: {"type": "content_block_delta", "delta": {"type": "text_delta", "text": " on your"}}
...
data: {"type": "message_stop"}
```

### Frontend Integration
- `components/chat/ChatWindow.tsx` - Main chat interface
- `components/chat/ChatMessage.tsx` - Message rendering
- `components/chat/ChatInput.tsx` - Message input with streaming
- `stores/useChatStore.ts` - Zustand store for chat state

## ML Data Collection (Phase 1 Complete)

CloudWaste automatically collects **anonymized machine learning data** during every scan to build a future ML model for intelligent waste detection.

### Status: Phase 1 Complete ✅
- **6 PostgreSQL tables** for ML data
- **Automatic collection** during scans (opt-in via user consent)
- **Full anonymization** - No PII, no AWS account IDs, no resource names
- **Admin export** - JSON/CSV export for analysis
- **AWS + Azure support** - GCP and M365 in Phase 3

### Data Collected (Anonymized)
1. **Resource Metadata** - Type, region, age, size, cost
2. **Detection Scenarios** - Why resource was flagged
3. **CloudWatch Metrics** - Historical usage patterns
4. **User Actions** - Did user ignore, delete, or keep the resource?
5. **Cost Trends** - Aggregated cost data by resource type/region
6. **Lifecycle Events** - Resource state changes over time

### Privacy & GDPR Compliance
- **Opt-in Only** - Users must explicitly consent via Settings → Privacy
- **Fully Anonymized** - Uses SHA-256 hashing for all identifiers
- **No PII** - No emails, names, or account IDs stored
- **Right to Erasure** - Users can delete their ML data anytime
- **Data Export** - Users can export their ML data in JSON format

### Database Tables
1. **ml_training_data** - Core anonymized resource data
2. **resource_lifecycle_event** - Resource state changes
3. **cloudwatch_metrics_history** - Historical metrics
4. **user_action_pattern** - Aggregated user behavior
5. **cost_trend_data** - Cost analysis by resource type
6. **resource_families** - Resource categorization

### Admin Panel
Access ML statistics at: `http://localhost:3000/dashboard/admin`
- Total ML samples collected
- Samples by provider (AWS, Azure, GCP)
- Samples by resource type
- User consent rate
- Export last 30/60/90 days (JSON/CSV)

### Future Phases
- **Phase 2:** Data enrichment (tags, real costs, relationships)
- **Phase 3:** GCP + Microsoft 365 support
- **Phase 4:** Optimization & automation
- **Phase 5:** ML model training (when 100K+ samples collected)

**Documentation:** See `/docs/ml/` for detailed ML architecture and usage guides.

## Onboarding System

CloudWaste includes a **comprehensive onboarding wizard** to guide new users through their first scan.

### Features
- **5-Step Wizard:**
  1. Welcome - Introduction to CloudWaste
  2. Add Account - Connect first cloud account
  3. Run Scan - Trigger first scan
  4. Review Results - View detected resources
  5. Complete - Onboarding complete
- **Progress Tracking** - Visual progress bar with step indicators
- **User State** - Tracks `onboarding_completed` flag in database
- **Smart Redirect** - Automatically redirects new users to onboarding
- **Skip Option** - Users can skip onboarding and explore manually
- **Checklist Widget** - Persistent checklist in dashboard for incomplete steps

### Components
- `components/onboarding/OnboardingWizard.tsx` - Main wizard container
- `components/onboarding/WelcomeStep.tsx` - Step 1
- `components/onboarding/AddAccountStep.tsx` - Step 2
- `components/onboarding/RunScanStep.tsx` - Step 3
- `components/onboarding/ReviewResultsStep.tsx` - Step 4
- `components/onboarding/CompletionStep.tsx` - Step 5
- `components/onboarding/OnboardingChecklist.tsx` - Dashboard checklist widget
- `components/onboarding/OnboardingBanner.tsx` - Reminder banner

### Hooks
- `hooks/useOnboarding.ts` - Onboarding state management
- `hooks/useOnboardingRedirect.ts` - Automatic redirect logic

### State Management
- `stores/useOnboardingStore.ts` - Zustand store for onboarding state

### Usage
Access onboarding at: `http://localhost:3000/onboarding`

Users are automatically redirected to onboarding after registration if:
- `onboarding_completed` is false
- Not accessing auth pages or legal pages

## Error Handling System

CloudWaste includes a **comprehensive error handling system** with custom error boundaries, states, and pages.

### Features
- **Error Boundaries** - Catch React errors at component and page level
- **Custom Error Pages** - 404, error, and global error pages
- **Error States** - Reusable error state components
- **Error Hook** - `useErrorHandler` for centralized error handling
- **Type-Safe Errors** - TypeScript error types for consistency

### Components
- `components/errors/ErrorBoundary.tsx` - React error boundary wrapper
- `components/errors/ErrorState.tsx` - Error display component
- `components/errors/EmptyState.tsx` - Empty data state
- `components/errors/LoadingError.tsx` - Loading failure state

### Pages
- `app/error.tsx` - Page-level error handler
- `app/not-found.tsx` - 404 Not Found page
- `app/global-error.tsx` - Global error fallback

### Hooks
- `hooks/useErrorHandler.ts` - Centralized error handling logic

### Types
- `types/errors.ts` - Error type definitions

### Usage Example
```typescript
import { ErrorBoundary } from '@/components/errors/ErrorBoundary';
import { ErrorState } from '@/components/errors/ErrorState';

function MyComponent() {
  const { error, handleError } = useErrorHandler();

  if (error) {
    return <ErrorState error={error} onRetry={() => handleError(null)} />;
  }

  return (
    <ErrorBoundary>
      {/* Component content */}
    </ErrorBoundary>
  );
}
```

## Sentry Error Tracking

CloudWaste uses **Sentry** for real-time error tracking and performance monitoring in both backend and frontend.

### Features
- **Automatic Error Capture** - All unhandled exceptions captured with full stack traces
- **Performance Monitoring** - Transaction tracing for API endpoints and page loads
- **User Context** - Errors tagged with user email and account info
- **Breadcrumbs** - Action trail before errors occur
- **Custom Context** - Scan details, cloud account info, resource metadata
- **Production Source Maps** - Readable stack traces in production (minified code)

### Architecture

**Backend (FastAPI):**
- `app/main.py` - Sentry initialization with integrations (FastAPI, SQLAlchemy, Redis, Celery)
- `app/workers/tasks.py` - Celery task error capture with scan context
- `app/providers/aws.py` - AWS credential validation error capture
- `app/api/v1/test_sentry.py` - Test endpoints (DEBUG mode only)

**Frontend (Next.js 14):**
- `src/components/providers/SentryProvider.tsx` - React component for client-side initialization
- `instrumentation.ts` - Server-side rendering (Node.js + Edge runtime) initialization
- `next.config.js` - Webpack plugin for automatic source map uploads
- `lib/api.ts` - Automatic API error capture (except 401/403)

**Key Design Decision:**
CloudWaste uses a **SentryProvider React component** instead of the traditional `sentry.client.config.ts` file. This ensures Sentry initializes correctly without conflicts and makes `window.Sentry` available for console testing.

### Configuration

**Backend `.env`:**
```bash
SENTRY_DSN=https://your-backend-dsn@o123456.ingest.sentry.io/456789
SENTRY_ENVIRONMENT=development  # development, staging, production
SENTRY_TRACES_SAMPLE_RATE=0.1  # 10% of transactions
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

**Frontend `.env.local`:**
```bash
NEXT_PUBLIC_SENTRY_DSN=https://your-frontend-dsn@o123456.ingest.sentry.io/789012
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
SENTRY_ORG=cloudwaste
SENTRY_PROJECT=cloudwaste-frontend
SENTRY_AUTH_TOKEN=  # For source map uploads in production
```

### API Endpoints (DEBUG mode only)

**Test Sentry backend:**
```bash
# Trigger test error
POST /api/v1/test/sentry/error
Authorization: Bearer <token>

# Check Sentry status
GET /api/v1/test/sentry/status
Authorization: Bearer <token>

# Send test message
POST /api/v1/test/sentry/message
Authorization: Bearer <token>
```

### Testing

**Backend:**
```bash
curl -X POST "http://localhost:8000/api/v1/test/sentry/error" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

**Frontend (browser console):**
```javascript
// Verify Sentry is initialized
window.Sentry  // Should be available

// Capture test exception
window.Sentry.captureException(new Error("🚨 TEST ERROR"));
```

### What Sentry Captures

**Backend:**
- ✅ Unhandled exceptions (FastAPI routes, background tasks)
- ✅ Celery task failures (with scan context)
- ✅ AWS/Azure/GCP provider errors (with credentials validation context)
- ✅ Database errors (SQLAlchemy)
- ✅ Redis connection errors
- ✅ Performance traces (API endpoint response times)

**Frontend:**
- ✅ React component errors (uncaught exceptions)
- ✅ API errors (except auth errors 401/403)
- ✅ Unhandled promise rejections
- ✅ Performance traces (page loads, route transitions)
- ❌ Session Replay disabled (to avoid conflicts)

### Troubleshooting

**"No outcomes to send" warning:**
- This is a benign warning in development mode with `debug: true`
- Events are still captured successfully
- Disappears in production with `debug: false`

**"Multiple Sentry Session Replay instances" error:**
- This error should NOT occur with the current architecture
- If it appears, verify `replaysSessionSampleRate: 0` in all configs
- Check that only ONE place calls `Sentry.init()` on the client-side

### Documentation

See `SENTRY_SETUP.md` for comprehensive setup guide.

## Impact Tracking

CloudWaste tracks **environmental impact** of cloud waste, converting cost savings to CO2 emissions and equivalent metrics.

### Features
- **CO2 Emissions Calculation** - Convert $ savings to CO2 saved
- **Equivalent Metrics:**
  - Trees planted equivalent
  - Car miles equivalent
  - Homes powered equivalent
- **Impact Dashboard** - Visualization of environmental impact
- **Historical Tracking** - Track impact over time

### Calculation
```
CO2 saved (kg) = Monthly waste ($) × 0.5 kg CO2/$ × 12 months
Trees equivalent = CO2 saved / 21 kg CO2/tree/year
Car miles equivalent = CO2 saved / 0.404 kg CO2/mile
Homes powered (days) = CO2 saved / (6000 kg CO2/year / 365 days)
```

### API Endpoints
- `GET /api/v1/impact/summary` - Get user's total environmental impact
- `GET /api/v1/impact/trends` - Get impact trends over time

### Frontend
- `app/(dashboard)/dashboard/impact/page.tsx` - Impact dashboard
- `stores/useImpactStore.ts` - Zustand store for impact data
- `types/impact.ts` - TypeScript types

## Dynamic Pricing System

CloudWaste uses **real-time pricing from AWS Pricing API** with PostgreSQL caching for accurate cost estimates.

### Architecture
- **AWS Pricing API** - Fetch real-time prices for EBS, Elastic IP, etc.
- **PostgreSQL Cache** - 24-hour TTL cache in `pricing_cache` table
- **Fallback Prices** - Hardcoded prices used if API fails or stale
- **Celery Beat** - Daily refresh at 2 AM UTC
- **Manual Refresh** - Admin can trigger immediate refresh

### Coverage (MVP)
| Resource Type | Pricing Source | Status |
|---------------|----------------|--------|
| EBS Volume | ✅ Dynamic (AWS Pricing API) | Fully implemented |
| Elastic IP | ✅ Dynamic (AWS Pricing API) | Fully implemented |
| EBS Snapshot | 🟠 Hardcoded fallback | Not implemented |
| EC2 Instance | 🟠 Hardcoded fallback | Not implemented |
| NAT Gateway | 🟠 Hardcoded fallback | Not implemented |
| Load Balancer | 🟠 Hardcoded fallback | Not implemented |
| RDS Instance | 🟠 Hardcoded fallback | Not implemented |
| EKS Cluster | 🟠 Hardcoded fallback | Not implemented |
| S3 Bucket | 🟠 Hardcoded fallback | Not implemented |

**Note:** All resources have fallback prices and won't crash. Dynamic pricing for remaining resources is future work.

### Admin Dashboard
Access pricing dashboard at: `http://localhost:3000/dashboard/admin/pricing`

**Metrics:**
- Total Cached Prices
- Last Refresh Time
- Cache Hit Rate (should be >90%)
- API Success Rate (should be >80%)

**Features:**
- Manual refresh button
- Filter by provider/region
- View price source (API vs Fallback)
- Task status monitoring

### API Endpoints
- `GET /api/v1/admin/pricing/stats` - Get pricing statistics
- `GET /api/v1/admin/pricing/cache` - List cached prices (with filters)
- `POST /api/v1/admin/pricing/refresh` - Trigger manual refresh
- `GET /api/v1/admin/pricing/refresh/{task_id}` - Check refresh task status

### Configuration
```bash
# Pricing refresh runs automatically via Celery Beat at 2 AM UTC
# Prices cached for 24 hours in pricing_cache table
# Fallback to hardcoded prices if cache expired or API fails
```

**Testing:** See `TESTING.md` for comprehensive testing guide.

## Testing Infrastructure

CloudWaste includes **test detection endpoints** for immediate testing without waiting 3 days for `min_age_days` threshold.

### Problem
By default, CloudWaste ignores resources created within the last 3 days to avoid false positives. This makes it difficult to test detection immediately after creating test resources.

### Solution: Test Detection Endpoint
A special endpoint allows overriding detection rules **in DEBUG mode only**.

### ⚠️ IMPORTANT: Temporary Test Scripts Cleanup
**ALWAYS delete temporary test scripts immediately after testing is complete.**

When creating test scripts (e.g., `test_*.sh`, `validate_*.py`, `debug_*.js`):
1. Use them for testing
2. Verify everything works correctly
3. **DELETE THEM IMMEDIATELY** - do not leave them in the codebase
4. Only keep permanent test files in the `tests/` directory

**Rationale:** Accumulation of temporary test scripts creates clutter and makes the codebase harder to maintain.

**Prerequisites:**
```bash
# Enable DEBUG mode in backend .env
DEBUG=True
```

**Test Elastic IP Detection (Immediate):**
```bash
curl -X POST "http://localhost:8000/api/v1/test/detect-resources" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -d '{
    "account_id": "YOUR_CLOUD_ACCOUNT_UUID",
    "region": "us-east-1",
    "resource_types": ["elastic_ip"],
    "overrides": {
      "elastic_ip": {
        "min_age_days": 0,
        "confidence_threshold_days": 0
      }
    }
  }'
```

**Security:**
⚠️ Test detection endpoint is **only available when `DEBUG=True`**. Never enable DEBUG mode in production.

**Documentation:** See `TESTING.md` for comprehensive testing guide including:
- Testing detection rules immediately
- Testing dynamic pricing system
- Manual testing checklist for all resource types
- Automated test creation/cleanup scripts

## Email System

CloudWaste includes **email verification** and **scan notification** features.

### Email Verification
- **Token-based verification** - 7-day expiration
- **Auto-cleanup** - Unverified accounts deleted after 14 days
- **Resend verification** - Users can request new verification email
- **Email required** - Users must verify email before accessing dashboard

### Scan Notifications
- **Scan completion emails** - Notify users when scans complete
- **User preference** - Users can opt-in/opt-out in Settings
- **Email templates** - HTML email templates with scan results summary

### Configuration
```bash
# SMTP Configuration
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAILS_FROM_EMAIL=noreply@cloudwaste.com
EMAILS_FROM_NAME=CloudWaste

# Email Verification
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=168  # 7 days
UNVERIFIED_ACCOUNT_CLEANUP_DAYS=14
FRONTEND_URL=http://localhost:3000

# AWS SES Monitoring (optional)
AWS_SES_REGION=eu-north-1
AWS_SES_ACCESS_KEY_ID=...
AWS_SES_SECRET_ACCESS_KEY=...
```

### API Endpoints
- `POST /api/v1/auth/resend-verification` - Resend verification email
- `GET /api/v1/auth/verify-email/{token}` - Verify email with token

## Testing Requirements

- **Backend coverage:** Minimum 70%
- **Frontend coverage:** Minimum 60%
- **Backend:** pytest + pytest-asyncio + pytest-cov
- **Frontend:** Jest + React Testing Library
- Use async fixtures for database tests
- Test critical user flows and API endpoints

**Comprehensive Testing Guide:** See `TESTING.md` for:
- Testing detection rules immediately (without 3-day wait)
- Testing dynamic pricing system
- Testing detection scenarios for all resource types
- Automated test creation/cleanup scripts
- Best practices for development testing

## Git Workflow

- **Branches:** `main` (production), `develop` (integration), `feature/*`, `fix/*`
- **Commits:** Conventional Commits format
  ```
  feat(api): add AWS EBS volume scanner
  fix(frontend): resolve dashboard loading state
  docs(readme): update setup instructions
  feat(ml): add ML data collection (Phase 1)
  feat(chat): add AI chat assistant with Claude Haiku 4.5
  ```
- **Pre-commit hooks:** black, ruff, mypy (backend), prettier, eslint (frontend)
- **NEVER add these commit messages:**
  - ❌ `🎯 Generated with Claude Code`
  - ❌ `Co-Authored-By: Claude <noreply@anthropic.com>`
  - Keep commits clean and professional without AI attribution

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
9. Always get ML data collection consent before collecting
10. Always anonymize ML data (no PII, no account IDs)
11. Always validate email addresses before allowing access
12. Always use dynamic pricing when available (fallback to hardcoded if stale)

### DON'T ❌
1. NEVER store credentials in plain text
2. NEVER use `any` in TypeScript without strong reason
3. NEVER write raw SQL queries (ORM only)
4. NEVER commit secrets (keep .env in .gitignore)
5. NEVER give write/delete permissions to AWS IAM roles
6. NEVER skip input validation
7. NEVER expose stack traces in production
8. NEVER use unmaintained dependencies
9. NEVER collect ML data without user consent
10. NEVER store PII in ML training data
11. NEVER enable DEBUG mode in production (disables test detection endpoint)
12. NEVER change ENCRYPTION_KEY in production (data loss!)
13. NEVER create documentation files (.md) automatically after code changes - documentation should only be created when explicitly requested by the user
14. NEVER leave temporary test scripts in the codebase - delete them immediately after the testing is complete and everything works correctly
15. NEVER add AI attribution in commit messages (no "Generated with Claude Code" or "Co-Authored-By: Claude")

## Performance Targets

- API response time: < 200ms (P95)
- Scan time: < 5 minutes for 1000 resources
- Frontend FCP: < 1.5s
- Database queries: < 50ms (with proper indexes)
- Concurrent scans: Support 10 accounts simultaneously
- Chat response: < 2s for first token (streaming)
- Pricing API: < 3s for full refresh per region

## Environment Variables

### Backend `.env`
```bash
# Application
APP_NAME=CloudWaste
APP_ENV=development
DEBUG=True
SECRET_KEY=your-secret-key-change-in-production

# Database
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cloudwaste

# Redis
REDIS_URL=redis://localhost:6379/0

# Security
ENCRYPTION_KEY=your-fernet-encryption-key
JWT_SECRET_KEY=your-jwt-secret
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_REMEMBER_ME_EXPIRE_DAYS=30

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000
CORS_ALLOW_CREDENTIALS=true
CORS_MAX_AGE=600

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAILS_FROM_EMAIL=noreply@cloudwaste.com
EMAILS_FROM_NAME=CloudWaste

# Email verification
EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS=168  # 7 days
UNVERIFIED_ACCOUNT_CLEANUP_DAYS=14
FRONTEND_URL=http://localhost:3000

# AWS (Optional - for testing)
AWS_ACCESS_KEY_ID=optional-for-dev
AWS_SECRET_ACCESS_KEY=optional-for-dev
AWS_DEFAULT_REGION=eu-west-1

# AWS SES (Optional - for cold email monitoring)
AWS_SES_REGION=eu-north-1
AWS_SES_ACCESS_KEY_ID=...
AWS_SES_SECRET_ACCESS_KEY=...

# AI Assistant (Anthropic)
ANTHROPIC_API_KEY=sk-ant-...
CHAT_MAX_MESSAGES_PER_USER_PER_DAY=50
CHAT_CONTEXT_MAX_RESOURCES=20
CHAT_MODEL=claude-haiku-4-5-20250818

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTH_LOGIN=5/minute
RATE_LIMIT_AUTH_REGISTER=3/minute
RATE_LIMIT_AUTH_REFRESH=10/minute
RATE_LIMIT_SCANS=10/minute
RATE_LIMIT_ADMIN=50/minute
RATE_LIMIT_API_DEFAULT=100/minute

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# Sentry Error Tracking
SENTRY_DSN=https://your-backend-dsn@o123456.ingest.sentry.io/456789
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1
```

### Frontend `.env.local`
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=CloudWaste

# Sentry Error Tracking
NEXT_PUBLIC_SENTRY_DSN=https://your-frontend-dsn@o123456.ingest.sentry.io/789012
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development

# Optionnel: Pour upload de source maps en production
SENTRY_ORG=cloudwaste
SENTRY_PROJECT=cloudwaste-frontend
SENTRY_AUTH_TOKEN=  # Obtenir dans sentry.io → Settings → Auth Tokens
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
   - Includes: User profile, cloud accounts, scans, resources, chat history, preferences, ML data

2. **Right to Erasure (Art. 17):**
   - Dashboard: Settings → Privacy → Delete My ML Data
   - API: `DELETE /api/v1/gdpr/delete-my-ml-data`
   - Full account deletion: contact privacy@cloudwaste.com

3. **Right to Rectification (Art. 16):**
   - Dashboard: Settings → Profile (update name, email, preferences)
   - API: `PATCH /api/v1/auth/me`

4. **Right to Data Portability (Art. 20):**
   - Export returns machine-readable JSON format
   - Includes all user data in structured format

5. **Right to Object (Art. 21):**
   - ML data collection is opt-in (explicit consent required)
   - Email marketing requires consent
   - Users can opt-out anytime

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

### ML Data & GDPR

**ML Data Collection:**
- **Opt-in Only** - Explicit consent required via Settings → Privacy
- **Fully Anonymized** - Uses SHA-256 hashing for all identifiers
- **No PII** - No emails, names, or account IDs stored
- **Right to Erasure** - Users can delete their ML data anytime
- **Data Export** - Users can export their ML data in JSON format

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
- ✅ ML data anonymization
- ✅ Chat data in exports
- ⏳ Data Protection Officer (DPO) contact setup
- ⏳ Supervisory authority registration (if required in your country)

**Non-Compliance Risk:** Failure to comply with GDPR can result in fines up to **€20 million or 4% of annual global turnover**, whichever is higher.

## Definition of Done

A feature is complete when:
1. Code implemented following standards
2. Tests written (≥70% backend, ≥60% frontend coverage)
3. Documentation updated (docstrings, README, CLAUDE.md)
4. Code reviewed
5. Manual testing completed
6. No blocking bugs
7. Logging and error handling in place
8. Commits pushed to branch
9. GDPR compliance verified (if handling user data)
10. ML data anonymized (if collecting ML data)
11. Email verification tested (if modifying auth flow)

## Additional Documentation

- **TESTING.md** - Comprehensive testing guide for detection rules, pricing, and manual testing
- **ML_README.md** - ML data collection documentation index
- **/docs/ml/** - Detailed ML documentation (architecture, usage, troubleshooting)
- **STRATEGIC_VISION.md** - Product vision and roadmap
- **SETUP_GUIDE.md** - Detailed setup instructions
- **README.md** - Project overview and quick start

### ⚠️ IMPORTANT: Documentation Creation Policy

**DO NOT create new documentation files (.md) automatically after every code change.**

Documentation should ONLY be created when:
- ✅ Explicitly requested by the user
- ✅ A major new feature is added that requires user-facing documentation
- ✅ API contracts change significantly

**DO NOT create documentation for:**
- ❌ Minor code changes or refactoring
- ❌ Bug fixes
- ❌ Internal implementation changes
- ❌ Routine maintenance
- ❌ "What I did" summaries

**Rationale:** Excessive documentation creates clutter and makes the codebase harder to navigate. Keep documentation minimal, high-quality, and user-focused.

## Quick Reference

### Most Common Tasks

**Start development environment:**
```bash
docker-compose up -d
```

**Access services:**
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/api/docs
- Admin Dashboard: http://localhost:3000/dashboard/admin
- Pricing Dashboard: http://localhost:3000/dashboard/admin/pricing

**Test detection immediately (DEBUG mode):**
```bash
curl -X POST "http://localhost:8000/api/v1/test/detect-resources" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"account_id":"uuid","region":"us-east-1","resource_types":["elastic_ip"],"overrides":{"elastic_ip":{"min_age_days":0}}}'
```

**Trigger pricing refresh:**
```bash
curl -X POST "http://localhost:8000/api/v1/admin/pricing/refresh" \
  -H "Authorization: Bearer $TOKEN"
```

**Export ML data:**
```bash
# Via admin dashboard: http://localhost:3000/dashboard/admin
# Click "Export Last 90 Days (JSON)"
```

**Check ML data collection:**
```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \
  "SELECT COUNT(*) FROM ml_training_data;"
```

---

**Version:** 2.1
**Last Updated:** 2025-11-13
**Status:** Phase 1 Complete (ML, Chat, Onboarding, Pricing, GDPR, Error Handling)

**Changelog v2.1:**
- Added rule: Never add AI attribution in commit messages
- Added rule: Never create documentation automatically after code changes
- Added rule: Always delete temporary test scripts after testing
