# CloudWaste Backend

FastAPI backend application for CloudWaste multi-cloud orphan resource detection platform.

---

## Tech Stack

- **Framework:** FastAPI 0.110+
- **Language:** Python 3.11+
- **Database:** PostgreSQL 15+ (async with SQLAlchemy 2.0)
- **Cache:** Redis 7+
- **Background Jobs:** Celery + Celery Beat
- **Cloud SDKs:** boto3/aioboto3 (AWS), azure-* (Azure), google-cloud-* (GCP), msgraph-core (M365)
- **Authentication:** JWT (access + refresh tokens)
- **Validation:** Pydantic v2
- **Testing:** pytest + pytest-asyncio + pytest-cov
- **Linting:** black, ruff, mypy
- **Error Tracking:** Sentry

---

## Quick Start

### 1. Setup Virtual Environment

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your configuration
```

**Key variables:**
- `DATABASE_URL` - PostgreSQL connection (use Docker port 5433)
- `REDIS_URL` - Redis connection
- `ENCRYPTION_KEY` - Fernet key for credential encryption (generate with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`)
- `JWT_SECRET_KEY` - JWT signing key
- `ANTHROPIC_API_KEY` - For AI chat assistant

### 3. Start Services

**Option A: Docker Compose (Recommended)**
```bash
cd ..  # Go to project root
docker-compose up -d postgres redis
```

**Option B: Local Services**
```bash
# PostgreSQL
brew services start postgresql@15

# Redis
brew services start redis
```

### 4. Run Migrations

```bash
cd backend
alembic upgrade head
```

### 5. Start Development Server

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

API will be available at:
- **API:** http://localhost:8000
- **Docs:** http://localhost:8000/api/docs
- **Health:** http://localhost:8000/api/v1/health

---

## Database Access

CloudWaste uses **PostgreSQL running in Docker**.

### Quick Access

**Connect to Docker PostgreSQL:**
```bash
PGPASSWORD=cloudwaste_dev_password psql -h localhost -p 5433 -U cloudwaste -d cloudwaste
```

**Run queries from outside container:**
```bash
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM users;"
```

### Connection Details

- **Host:** `localhost` (from host machine)
- **Port:** `5433` (forwarded to container port 5432)
- **User:** `cloudwaste`
- **Password:** `cloudwaste_dev_password`
- **Database:** `cloudwaste`

### ⚠️ Important

- **Always use port 5433** (Docker PostgreSQL)
- **Never use port 5432** (local PostgreSQL)
- Stop local PostgreSQL if interfering: `brew services stop postgresql@15`

### Common Queries

```bash
# List users
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT email, is_active FROM users;"

# Count orphan resources
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM orphan_resources;"

# Recent scans
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT id, status, started_at FROM scans ORDER BY started_at DESC LIMIT 5;"
```

---

## Development Commands

### Run Tests

```bash
cd backend

# Run all tests
pytest

# With coverage
pytest --cov=app --cov-report=html

# Specific test file
pytest tests/api/test_auth.py -v

# Watch mode (requires pytest-watch)
ptw
```

### Run Celery Worker

```bash
celery -A app.workers.celery_app worker --loglevel=info
```

### Run Celery Beat (Scheduled Tasks)

```bash
celery -A app.workers.celery_app beat --loglevel=info
```

### Database Migrations

```bash
# Create migration
alembic revision --autogenerate -m "add users table"

# Apply migrations
alembic upgrade head

# Rollback one migration
alembic downgrade -1

# View migration history
alembic history
```

### Code Quality

```bash
# Format code
black .

# Lint code
ruff check .

# Type check
mypy app/

# Run all checks
black . && ruff check . && mypy app/
```

---

## Project Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI entry point
│   ├── api/
│   │   ├── deps.py              # Dependencies (auth, db)
│   │   └── v1/                  # API v1 endpoints
│   │       ├── auth.py          # JWT authentication, registration
│   │       ├── accounts.py      # Cloud accounts CRUD
│   │       ├── scans.py         # Scan triggers and results
│   │       ├── resources.py     # Orphan resources
│   │       ├── detection_rules.py
│   │       ├── chat.py          # AI chat assistant (SSE)
│   │       ├── gdpr.py          # GDPR compliance
│   │       ├── admin.py         # Admin endpoints
│   │       └── ...
│   ├── core/
│   │   ├── config.py            # Settings (Pydantic BaseSettings)
│   │   ├── security.py          # JWT, password hashing
│   │   ├── database.py          # SQLAlchemy async engine
│   │   └── rate_limit.py        # SlowAPI rate limiting
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── crud/                    # Database operations
│   ├── providers/               # Cloud provider implementations
│   │   ├── base.py              # Abstract base class
│   │   ├── aws.py               # AWS scanner (25 resource types)
│   │   ├── azure.py             # Azure scanner
│   │   ├── gcp.py               # GCP scanner (14+ types)
│   │   └── microsoft365.py      # M365 scanner
│   ├── services/                # Business logic
│   │   ├── scanner.py           # Scan orchestration
│   │   ├── cost_calculator.py   # Cost estimation
│   │   ├── chat_service.py      # AI chat (Anthropic)
│   │   ├── pricing_service.py   # Dynamic pricing (AWS API)
│   │   ├── email_service.py     # Email sending
│   │   ├── gdpr_compliance.py   # GDPR data export/deletion
│   │   └── ...
│   ├── ml/                      # ML data pipeline
│   ├── middleware/              # Custom middleware
│   └── workers/                 # Celery background tasks
│       ├── celery_app.py        # Celery configuration
│       ├── tasks.py             # Scan tasks
│       └── ml_tasks.py          # ML data collection
├── alembic/                     # Database migrations
├── tests/                       # Test suite
│   ├── api/                     # API endpoint tests
│   ├── providers/               # Provider tests
│   ├── services/                # Service tests
│   └── core/                    # Core tests
├── requirements.txt             # Python dependencies
└── README.md                    # This file
```

---

## Code Standards

### Type Hints (MANDATORY)

```python
from typing import List, Optional
from app.models.user import User

async def get_user_by_email(
    email: str,
    db: AsyncSession
) -> Optional[User]:
    """Retrieve user by email address."""
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()
```

### Docstrings (Google Style)

```python
async def scan_orphan_resources(
    account_id: str,
    region: str
) -> List[OrphanResource]:
    """
    Scan cloud account for orphan resources.

    Args:
        account_id: Cloud account UUID
        region: AWS region code (e.g., 'us-east-1')

    Returns:
        List of detected orphan resources with cost estimates

    Raises:
        CredentialsError: If cloud credentials are invalid
        RateLimitError: If API rate limit exceeded
    """
    # Implementation
```

### Async/Await

All I/O operations must use `async`/`await`:

```python
# ✅ Good
async def get_users(db: AsyncSession):
    result = await db.execute(select(User))
    return result.scalars().all()

# ❌ Bad
def get_users(db: Session):
    return db.query(User).all()
```

### Error Handling

```python
from app.core.exceptions import CredentialsError

try:
    result = await aws_client.describe_volumes()
except ClientError as e:
    raise CredentialsError(f"AWS credentials invalid: {e}")
```

### Naming Conventions

- **Functions/Variables:** `snake_case`
- **Classes:** `PascalCase`
- **Constants:** `UPPER_SNAKE_CASE`
- **Private methods:** `_leading_underscore`

---

## Testing

### Test Structure

```python
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    """Test user registration."""
    response = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "test@example.com",
            "password": "securepass123",
            "full_name": "Test User"
        }
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
```

### Running Specific Tests

```bash
# Test specific module
pytest tests/api/test_auth.py

# Test specific function
pytest tests/api/test_auth.py::test_create_user

# Test with markers
pytest -m "not slow"

# Verbose mode
pytest -v

# Stop on first failure
pytest -x
```

### Coverage Requirements

- **Minimum:** 70% coverage
- **Target:** 80%+ coverage
- Generate report: `pytest --cov=app --cov-report=html`

---

## API Endpoints

### Authentication
- `POST /api/v1/auth/register` - User registration
- `POST /api/v1/auth/login` - JWT login
- `POST /api/v1/auth/refresh` - Refresh access token
- `POST /api/v1/auth/resend-verification` - Resend email verification
- `GET /api/v1/auth/verify-email/{token}` - Verify email

### Cloud Accounts
- `GET /api/v1/accounts/` - List cloud accounts
- `POST /api/v1/accounts/` - Add cloud account
- `PATCH /api/v1/accounts/{id}` - Update account
- `DELETE /api/v1/accounts/{id}` - Delete account

### Scans
- `POST /api/v1/scans/` - Trigger new scan
- `GET /api/v1/scans/` - List scans
- `GET /api/v1/scans/{id}` - Get scan details

### Resources
- `GET /api/v1/resources/` - List orphan resources
- `PATCH /api/v1/resources/{id}/ignore` - Ignore resource
- `PATCH /api/v1/resources/{id}/mark-for-deletion` - Mark for deletion

### AI Chat
- `POST /api/v1/chat/conversations` - Create conversation
- `POST /api/v1/chat/messages` - Send message (SSE streaming)

### Admin
- `GET /api/v1/admin/stats` - Platform statistics
- `GET /api/v1/admin/pricing/stats` - Pricing cache stats
- `POST /api/v1/admin/pricing/refresh` - Trigger pricing refresh

**Full API documentation:** http://localhost:8000/api/docs

---

## Environment Variables

```bash
# Application
APP_NAME=CloudWaste
DEBUG=True
SECRET_KEY=your-secret-key

# Database
DATABASE_URL=postgresql+asyncpg://cloudwaste:cloudwaste_dev_password@localhost:5433/cloudwaste

# Redis
REDIS_URL=redis://localhost:6379/0

# Security (CRITICAL)
ENCRYPTION_KEY=your-fernet-key  # Generate with: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
JWT_SECRET_KEY=your-jwt-secret
ACCESS_TOKEN_EXPIRE_MINUTES=15

# CORS
ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Email
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_PASSWORD=your-sendgrid-api-key
FRONTEND_URL=http://localhost:3000

# AI & Error Tracking
ANTHROPIC_API_KEY=sk-ant-...
SENTRY_DSN=https://...@sentry.io/...

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_AUTH_LOGIN=5/minute
RATE_LIMIT_API_DEFAULT=100/minute

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Troubleshooting

### Database Connection Errors

```bash
# Check if PostgreSQL is running
docker ps | grep postgres

# Verify connection
PGPASSWORD=cloudwaste_dev_password psql -h localhost -p 5433 -U cloudwaste -d cloudwaste -c "SELECT 1;"

# Check logs
docker logs cloudwaste_postgres
```

### Import Errors

```bash
# Verify dependencies installed
pip list | grep fastapi

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Celery Not Processing Tasks

```bash
# Check Redis connection
redis-cli ping

# Check Celery worker logs
celery -A app.workers.celery_app worker --loglevel=debug

# Purge queue
celery -A app.workers.celery_app purge
```

---

## Additional Resources

- **Project Documentation:** `/README.md` (root)
- **Frontend README:** `/frontend/README.md`
- **Deployment Guide:** `/deployment/README.md`
- **Testing Guide:** `/TESTING.md`
- **ML Documentation:** `/docs/ml/`
- **CLAUDE.md:** Backend context for Claude Code

---

**Version:** 1.0
**Last Updated:** 2025-01-13
**Python:** 3.11+
**FastAPI:** 0.110+
