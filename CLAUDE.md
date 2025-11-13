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
├── frontend/                    # Next.js 14+ application
│   ├── src/
│   │   ├── app/                # App Router (auth, dashboard, legal, onboarding)
│   │   ├── components/         # UI, layout, dashboard, chat, errors, legal
│   │   ├── lib/                # API client, auth, utilities
│   │   ├── hooks/              # Custom React hooks
│   │   ├── stores/             # Zustand state management
│   │   ├── types/              # TypeScript definitions
│   │   └── config/             # App configuration
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py             # Entry point
│   │   ├── api/v1/             # API endpoints (auth, accounts, scans, resources, etc.)
│   │   ├── core/               # Config, security, database, rate limiting
│   │   ├── models/             # SQLAlchemy ORM models
│   │   ├── schemas/            # Pydantic request/response schemas
│   │   ├── crud/               # Database operations
│   │   ├── providers/          # Cloud provider implementations (AWS, Azure, GCP, M365)
│   │   ├── services/           # Business logic
│   │   ├── ml/                 # ML data pipeline
│   │   ├── middleware/         # Custom middleware
│   │   └── workers/            # Celery background tasks
│   ├── alembic/                # Database migrations
│   └── tests/                  # Test suite
│
├── deployment/                  # Production deployment (see deployment/README.md)
├── docs/ml/                     # ML documentation
├── docker-compose.yml           # Dev environment
├── README.md                    # Project overview
├── CLAUDE.md                    # This file
├── TESTING.md                   # Testing guide
└── ML_README.md                 # ML documentation index
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

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
pytest -v --cov=app              # Tests
black . && ruff check . && mypy app/  # Linting
```

### Frontend
```bash
cd frontend
npm install
npm run dev                      # Development server
npm run build && npm start       # Production build
npm test                         # Tests
npm run lint && npm run format   # Linting
```

### Docker Compose
```bash
docker-compose up -d             # Start all services
docker-compose down              # Stop
docker-compose logs -f           # View logs
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

### Required Cloud Permissions (Read-Only)

**AWS:** IAM user with read-only permissions (ec2:Describe*, rds:Describe*, s3:List*, cloudwatch:GetMetricStatistics, etc.)
**Azure:** Service Principal with Reader + Monitoring Reader roles
**GCP:** Service Account with Compute Viewer, Monitoring Viewer, Storage Object Viewer, Container Engine Viewer
**Microsoft 365:** Application with Sites.Read.All + Files.Read.All

**📄 Full IAM policy examples:** See README.md Security section

### Authentication
- Password hashing: bcrypt (cost factor 12)
- JWT tokens with access/refresh pattern
- HTTPS only (TLS 1.3)
- Input validation: Strict Pydantic validation, ORM only (NO raw SQL)
- Email verification: 7-day token expiration
- Auto-cleanup: Unverified accounts deleted after 14 days

### CORS Security
**Strict CORS validation** to prevent cross-origin attacks, credential theft, and wildcard exploits.

**Key Rules:**
- ✅ No wildcards - Explicit whitelist only
- ✅ HTTPS enforced in production (except localhost)
- ✅ Pydantic validation at startup (fail-fast)
- ✅ Explicit methods/headers (no `["*"]`)
- ✅ CORS logging for security monitoring

**Configuration:**
```bash
# Development
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Production
ALLOWED_ORIGINS=https://cloudwaste.com,https://www.cloudwaste.com
```

**📄 Implementation details:** See `backend/app/core/config.py` and `backend/app/main.py`

### Rate Limiting
**SlowAPI + Redis** to prevent DDoS, brute-force attacks, resource enumeration, and API abuse.

**Key Limits:**
- Authentication: 3-10/minute (login, register, refresh)
- Scans: 10/minute (cloud scans)
- Standard API: 100/minute (default)
- Admin: 50/minute

**Configuration:**
```bash
RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTH_LOGIN=5/minute
RATE_LIMIT_SCANS=10/minute
RATE_LIMIT_API_DEFAULT=100/minute
```

**Response:** 429 Too Many Requests with `X-RateLimit-*` headers

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

**Multi-cloud detection:** 25 AWS types + Azure + 14+ GCP types + Microsoft 365

### AWS (25 types)
**Core (7):** EBS Volumes, Elastic IPs, Snapshots, EC2 Instances, Load Balancers, RDS, NAT Gateways
**Advanced (18):** FSx, Neptune, MSK, EKS, SageMaker, Redshift, ElastiCache, VPN, Transit Gateway, OpenSearch, Global Accelerator, Kinesis, VPC Endpoints, DocumentDB, S3, Lambda, DynamoDB

### Azure
Managed Disks, Public IPs, Virtual Machines, AKS Clusters *(expanding)*

### GCP (14+ types)
Compute Engine, Persistent Disks, Snapshots, Cloud Storage, GKE, Cloud Run, Cloud Functions, Filestore, Firestore, Bigtable, Memorystore, BigQuery, Dataproc, Vertex AI

### Microsoft 365
SharePoint Sites, OneDrive Files

### Detection Features
- **CloudWatch/Monitor/Cloud Monitoring** - Actual usage patterns
- **Confidence Levels** - Critical (90+ days), High (30+), Medium (7-30), Low (<7)
- **Cost Calculation** - Future waste + already wasted
- **Detection Rules** - User-customizable thresholds
- **Multi-Scenario** - 4-8 scenarios per advanced resource
- **Dynamic Pricing** - AWS Pricing API (with fallback)

## AI Chat Assistant

**AI-powered assistant** using **Anthropic Claude Haiku 4.5** for intelligent resource analysis and recommendations.

### Features
- Context-aware (includes recent orphan resources)
- Streaming responses (SSE via `sse-starlette`)
- Conversation history (PostgreSQL)
- Rate limited (50 messages/user/day)
- Multi-turn conversations

### Configuration
```bash
ANTHROPIC_API_KEY=sk-ant-...
CHAT_MAX_MESSAGES_PER_USER_PER_DAY=50
CHAT_CONTEXT_MAX_RESOURCES=20
CHAT_MODEL=claude-haiku-4-5-20250818
```

### API Endpoints
- `POST /api/v1/chat/conversations` - Start conversation
- `POST /api/v1/chat/messages` - Send message (SSE streaming)

### Frontend
`components/chat/` - ChatWindow, ChatMessage, ChatInput
`stores/useChatStore.ts` - Zustand store

## ML Data Collection (Phase 1 Complete)

**Anonymized machine learning data** collected during scans to build future ML model for intelligent waste detection.

### Status ✅
- 6 PostgreSQL tables (ml_training_data, resource_lifecycle_event, cloudwatch_metrics_history, etc.)
- Automatic collection (opt-in via user consent)
- Full anonymization (SHA-256 hashing, no PII, no account IDs)
- Admin export (JSON/CSV)
- AWS + Azure support (GCP + M365 in Phase 3)

### Data Collected
Resource metadata, detection scenarios, CloudWatch metrics, user actions, cost trends, lifecycle events

### Privacy
✅ Opt-in only | ✅ Fully anonymized | ✅ Right to erasure | ✅ Data export

**📄 Documentation:** See `/docs/ml/` for detailed architecture

## Onboarding System

**5-step wizard** to guide new users through their first scan.

### Steps
1. Welcome → 2. Add Account → 3. Run Scan → 4. Review Results → 5. Complete

### Features
- Progress tracking (visual indicators)
- User state (`onboarding_completed` flag)
- Smart redirect (auto-redirect new users)
- Skip option + checklist widget

### Components
`components/onboarding/` - OnboardingWizard, WelcomeStep, AddAccountStep, etc.
`hooks/useOnboarding.ts` - State management
`stores/useOnboardingStore.ts` - Zustand store

**Access:** `http://localhost:3000/onboarding`

## Error Handling System

**Comprehensive error handling** with custom boundaries, states, and pages.

### Features
Error boundaries (React errors), custom error pages (404, error, global), error states, `useErrorHandler` hook, type-safe errors

### Components
`components/errors/` - ErrorBoundary, ErrorState, EmptyState, LoadingError
`app/error.tsx`, `app/not-found.tsx`, `app/global-error.tsx`
`hooks/useErrorHandler.ts` - Centralized error handling
`types/errors.ts` - Error type definitions

## Sentry Error Tracking

**Real-time error tracking** and performance monitoring for backend (FastAPI) and frontend (Next.js).

### Features
- Automatic error capture with full stack traces
- Performance monitoring (API endpoints, page loads)
- User context (email, account info)
- Breadcrumbs and custom context
- Production source maps

### Configuration
```bash
# Backend
SENTRY_DSN=https://...@sentry.io/...
SENTRY_ENVIRONMENT=development
SENTRY_TRACES_SAMPLE_RATE=0.1

# Frontend
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
NEXT_PUBLIC_SENTRY_ENVIRONMENT=development
```

### Testing
```bash
# Backend (DEBUG mode)
curl -X POST "http://localhost:8000/api/v1/test/sentry/error" -H "Authorization: Bearer TOKEN"

# Frontend (browser console)
window.Sentry.captureException(new Error("TEST ERROR"));
```

**📄 Full documentation:** See `SENTRY_SETUP.md` for comprehensive guide

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

### Backend `.env` (Essential variables)
```bash
# Application
APP_NAME=CloudWaste
DEBUG=True
SECRET_KEY=your-secret-key

# Database & Cache
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/cloudwaste
REDIS_URL=redis://localhost:6379/0

# Security (CRITICAL)
ENCRYPTION_KEY=your-fernet-key  # DO NOT change in production
JWT_SECRET_KEY=your-jwt-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PASSWORD=your-api-key
FRONTEND_URL=http://localhost:3000

# AI & Error Tracking
ANTHROPIC_API_KEY=sk-ant-...
SENTRY_DSN=https://...@sentry.io/...

# Rate Limiting
RATE_LIMIT_ENABLED=true
```

### Frontend `.env.local`
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SENTRY_DSN=https://...@sentry.io/...
```

**📄 Full list:** See `.env.example` files in backend/ and frontend/

## GDPR/Legal Compliance

**Fully compliant** with GDPR (Regulation EU 2016/679) and applicable data protection laws.

### Legal Pages (Publicly accessible at `/legal/*`)
1. **Privacy Policy** (`/legal/privacy`) - GDPR Article 13/14 compliant, user rights, DPO contact
2. **Terms of Service** (`/legal/terms`) - User responsibilities, service limitations, governing law
3. **Cookie Policy** (`/legal/cookies`) - Cookie inventory (Essential, Functional, Analytics), DNT respect
4. **Legal Notice** (`/legal/legal-notice`) - Publisher info, hosting, DPO contact

### Cookie Consent Banner
**Component:** `components/legal/CookieBanner.tsx`
- ✅ Opt-in consent (not pre-checked)
- ✅ Granular control (Essential, Functional, Analytics)
- ✅ DNT browser signal respected
- ✅ Withdrawable anytime via "Cookie Settings"

### User Rights (GDPR Articles 15-22)
1. **Right to Access** - Settings → Privacy → Export My Data (JSON)
2. **Right to Erasure** - Settings → Privacy → Delete My ML Data
3. **Right to Rectification** - Settings → Profile (update info)
4. **Right to Data Portability** - Machine-readable JSON export
5. **Right to Object** - ML data opt-in, email marketing consent

**Response Time:** 30 days (GDPR Article 12)

### Data Protection by Design
**Technical Measures:**
- Encryption at rest (Fernet, bcrypt) + in transit (TLS 1.3)
- Pseudonymization (SHA-256 hashing for ML data)
- Access control (role-based, least-privilege)
- Data minimization + retention limits

**Organizational Measures:**
- DPO appointed, PIA conducted
- Staff training, breach notification (72h)

### Compliance Checklist
✅ Privacy Policy, Terms, Cookie Policy, Legal Notice
✅ Cookie Consent Banner (opt-in, granular, withdrawable)
✅ User data export/deletion, ML data opt-in
✅ Encrypted credentials, DNT respect
⏳ DPO contact setup, supervisory authority registration

**📄 Full legal pages:** `/legal/*` | **Risk:** Fines up to €20M or 4% turnover

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
