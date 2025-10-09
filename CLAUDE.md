# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**CloudWaste** is a SaaS platform for detecting orphaned and unused cloud resources (zombies) that generate unnecessary costs for businesses. The MVP focuses on AWS-only detection of the most common resource types (quick wins).

**Tech Stack:**
- **Frontend:** Next.js 14+ (App Router), TypeScript, React 18+, Tailwind CSS + shadcn/ui, Zustand
- **Backend:** FastAPI 0.110+, Python 3.11+, Pydantic v2, asyncio
- **Database:** PostgreSQL 15+ (SQLAlchemy 2.0 async), Redis 7+
- **Background Jobs:** Celery + Celery Beat + Redis
- **Cloud SDKs:** boto3 + aioboto3 (async)

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
      "s3:ListAllMyBuckets",
      "s3:ListBucket",
      "s3:GetBucketLocation",
      "s3:ListBucketMultipartUploads",
      "s3:GetBucketLifecycleConfiguration",
      "elasticloadbalancing:Describe*",
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

### Authentication
- Password hashing: bcrypt (cost factor 12)
- JWT tokens with access/refresh pattern
- Rate limiting: 100 req/min per user (FastAPI-limiter + Redis)
- CORS: Whitelist authorized domains only
- HTTPS only (TLS 1.3)
- Input validation: Strict Pydantic validation, ORM only (NO raw SQL)

## Database Schema

### Core Tables
- **users:** User accounts (id, email, hashed_password, full_name, is_active, created_at)
- **cloud_accounts:** Cloud provider accounts (id, user_id, provider, account_identifier, credentials_encrypted, regions, last_scan_at)
- **scans:** Scan jobs (id, cloud_account_id, status, scan_type, total_resources_scanned, orphan_resources_found, estimated_monthly_waste, started_at, completed_at)
- **orphan_resources:** Detected resources (id, scan_id, cloud_account_id, resource_type, resource_id, resource_name, region, estimated_monthly_cost, resource_metadata, status)

## MVP Scope - AWS Resource Detections

Focus on detecting the following orphaned resources (quick wins):

1. **EBS Volumes (unattached)** - state = 'available', cost: ~$0.10/GB/month
2. **Elastic IPs (unassigned)** - no association, cost: ~$3.60/month
3. **EBS Snapshots (orphaned)** - snapshot > 90 days + source volume deleted, cost: ~$0.05/GB/month
4. **EC2 Instances (stopped > 30 days)** - state = 'stopped', last_state_transition > 30 days
5. **Load Balancers (no backends)** - 0 healthy targets, cost: ~$16-22/month
6. **RDS Instances (stopped > 7 days)** - state = 'stopped'
7. **NAT Gateways (unused)** - BytesOutToDestination = 0 over 30 days, cost: ~$32/month

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
