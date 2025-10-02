# CloudWaste - Cloud Resource Waste Detection Platform

**CloudWaste** is a SaaS platform that detects and identifies orphaned or unused cloud resources (zombies) to help businesses reduce unnecessary costs. Studies show that 30-35% of cloud spending is wasted.

## 🎯 Project Vision

**Problem:** Businesses waste significant money on orphaned cloud resources that are no longer in use.

**Solution:** Multi-cloud SaaS platform that connects to AWS/Azure/GCP accounts in read-only mode to scan and identify unused resources with cost-saving estimates.

**MVP Focus:** AWS-only, detecting the most common resource types (quick wins).

---

## 🏗️ Architecture

### Tech Stack

**Frontend:**
- Next.js 14+ (App Router)
- TypeScript (strict mode)
- React 18+
- Tailwind CSS + shadcn/ui
- Zustand (state management)
- Recharts (charts)
- React Hook Form + Zod (forms)

**Backend:**
- FastAPI 0.110+
- Python 3.11+
- Async I/O (asyncio + aiohttp)
- Pydantic v2 (validation)
- Celery + Redis (background jobs)
- Celery Beat (task scheduler)

**Database:**
- PostgreSQL 15+ (primary database)
- Redis 7+ (cache/queue)
- SQLAlchemy 2.0 (async ORM)
- Alembic (migrations)

**Cloud SDKs:**
- boto3 + aioboto3 (AWS async)

**Infrastructure:**
- Docker + Docker Compose
- Pre-commit hooks (black, ruff, mypy, prettier, eslint)

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CloudWaste
```

### 2. Generate Encryption Keys

Generate required encryption keys for production:

```bash
# Generate Fernet encryption key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Generate JWT secret key
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3. Configure Environment Variables

```bash
cp .env.example .env
```

Edit `.env` and update the following:
- `ENCRYPTION_KEY`: Your Fernet key (from step 2)
- `JWT_SECRET_KEY`: Your JWT secret (from step 2)
- `SECRET_KEY`: Any random secret string

### 4. Start the Application

```bash
docker-compose up -d
```

This will start:
- PostgreSQL (port 5432)
- Redis (port 6379)
- FastAPI Backend (port 8000)
- Celery Worker
- Celery Beat Scheduler
- Next.js Frontend (port 3000)

### 5. Access the Application

- **Frontend:** http://localhost:3000
- **Backend API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/api/docs
- **Health Check:** http://localhost:8000/api/v1/health

---

## 💻 Development Setup

### Backend (Python)

```bash
cd backend

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Run development server
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Celery worker (separate terminal)
celery -A app.workers.celery_app worker --loglevel=info

# Run Celery Beat (separate terminal)
celery -A app.workers.celery_app beat --loglevel=info

# Run tests
pytest

# Run tests with coverage
pytest --cov=app --cov-report=html

# Format code
black .

# Lint code
ruff check .

# Type check
mypy app/
```

### Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm start

# Run tests
npm test

# Run tests with coverage
npm run test:coverage

# Lint code
npm run lint

# Format code
npm run format
```

### Pre-commit Hooks

Install pre-commit hooks to ensure code quality:

```bash
pip install pre-commit
pre-commit install
```

Now hooks will run automatically on every commit.

---

## 📋 MVP Scope - AWS Resource Detection

The MVP focuses on detecting 7 types of orphaned AWS resources:

1. **EBS Volumes (unattached)** - state = 'available', ~$0.10/GB/month
2. **Elastic IPs (unassigned)** - no association, ~$3.60/month
3. **EBS Snapshots (orphaned)** - snapshot > 90 days + source deleted, ~$0.05/GB/month
4. **EC2 Instances (stopped > 30 days)** - state = 'stopped'
5. **Load Balancers (no backends)** - 0 healthy targets, ~$16-22/month
6. **RDS Instances (stopped > 7 days)** - state = 'stopped'
7. **NAT Gateways (unused)** - BytesOutToDestination = 0, ~$32/month

---

## 🔐 Security

### Critical Security Rules

1. **AWS Credentials:** READ-ONLY permissions ONLY (never write/delete)
2. **Encryption:** All cloud credentials encrypted using Fernet
3. **Authentication:** JWT tokens (access + refresh pattern)
4. **Password Hashing:** bcrypt with cost factor 12
5. **Rate Limiting:** 100 req/min per user
6. **CORS:** Whitelist authorized domains only
7. **HTTPS:** TLS 1.3 only in production

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

---

## 📊 Database Schema

### Core Tables

- **users** - User accounts
- **cloud_accounts** - Cloud provider accounts (credentials encrypted)
- **scans** - Scan jobs and results
- **orphan_resources** - Detected orphaned resources

See [CLAUDE_CODE_RULES.md](CLAUDE_CODE_RULES.md) for detailed schema.

---

## 🧪 Testing

### Backend Testing

- **Coverage Target:** ≥70%
- **Framework:** pytest + pytest-asyncio + pytest-cov

```bash
cd backend
pytest                                      # Run all tests
pytest tests/api/                          # Run specific directory
pytest -v --cov=app --cov-report=html      # With coverage
```

### Frontend Testing

- **Coverage Target:** ≥60%
- **Framework:** Jest + React Testing Library

```bash
cd frontend
npm test                                   # Run all tests
npm run test:watch                         # Watch mode
npm run test:coverage                      # With coverage
```

---

## 📚 Project Structure

```
cloudwaste/
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── main.py             # FastAPI entry point
│   │   ├── api/v1/             # API endpoints
│   │   ├── core/               # Config, security, database
│   │   ├── models/             # SQLAlchemy models
│   │   ├── schemas/            # Pydantic schemas
│   │   ├── crud/               # CRUD operations
│   │   ├── providers/          # Cloud provider abstractions
│   │   ├── services/           # Business logic
│   │   └── workers/            # Celery tasks
│   ├── alembic/                # Database migrations
│   └── tests/
│
├── frontend/                    # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   ├── components/         # React components
│   │   ├── lib/                # Utilities
│   │   ├── hooks/              # Custom hooks
│   │   ├── stores/             # Zustand stores
│   │   └── types/              # TypeScript types
│   └── public/
│
├── docker-compose.yml
├── .env.example
├── .gitignore
├── .pre-commit-config.yaml
├── CLAUDE.md                    # Claude Code guidance
└── CLAUDE_CODE_RULES.md         # Detailed specifications
```

---

## 🗓️ Development Roadmap

### Sprint 1: Infrastructure & Auth (Weeks 1-2)
- ✅ Project setup (monorepo structure)
- ✅ Docker Compose (PostgreSQL + Redis)
- ✅ Backend skeleton (FastAPI + SQLAlchemy)
- ✅ Frontend skeleton (Next.js + Tailwind)
- 🔄 Auth system (JWT, registration, login)

### Sprint 2: Cloud Accounts Management (Weeks 3-4)
- Models: CloudAccount
- API: CRUD cloud accounts
- AWS credentials validation
- Frontend: Account management pages
- Credentials encryption/decryption

### Sprint 3: AWS Scanner Core (Weeks 5-7)
- Provider abstraction
- AWS implementation (7 resource types)
- Cost calculator
- Celery setup + tasks
- API endpoints: scans & resources

### Sprint 4: Dashboard & UI (Weeks 8-9)
- Dashboard with metrics
- Resource list with filters
- Actions: ignore/mark for deletion
- Export CSV/JSON

### Sprint 5: Automation & Polish (Week 10)
- Celery Beat (daily scans)
- Email notifications
- Logging + error handling
- Tests coverage
- Documentation
- Beta release

---

## 🛠️ Useful Commands

### Docker Commands

```bash
# Start all services
docker-compose up -d

# Stop all services
docker-compose down

# View logs
docker-compose logs -f                    # All services
docker-compose logs -f backend            # Backend only
docker-compose logs -f celery_worker      # Worker only
docker-compose logs -f frontend           # Frontend only

# Restart a service
docker-compose restart backend
docker-compose restart celery_worker

# Rebuild images
docker-compose build backend
docker-compose up -d --build

# Check status
docker-compose ps
docker stats
```

### Database Commands

```bash
# Connect to PostgreSQL
docker-compose exec postgres psql -U cloudwaste -d cloudwaste

# Useful queries
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM cloud_accounts;
SELECT COUNT(*) FROM scans WHERE status = 'completed';
SELECT COUNT(*) FROM orphan_resources;

# Resources by type
SELECT resource_type, COUNT(*), SUM(estimated_monthly_cost)
FROM orphan_resources
GROUP BY resource_type;

# Resources by region
SELECT region, COUNT(*)
FROM orphan_resources
GROUP BY region;

# Latest scan
SELECT id, status, orphan_resources_found, estimated_monthly_waste, completed_at
FROM scans
ORDER BY created_at DESC
LIMIT 1;
```

### Database Migrations

```bash
# Create new migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec backend alembic upgrade head

# Rollback one migration
docker-compose exec backend alembic downgrade -1

# View migration history
docker-compose exec backend alembic history
```

### Celery Commands

```bash
# View active workers
docker-compose exec celery_worker celery -A app.workers.celery_app inspect active

# View queued tasks
docker-compose exec celery_worker celery -A app.workers.celery_app inspect scheduled

# View worker stats
docker-compose exec celery_worker celery -A app.workers.celery_app inspect stats

# Purge all queued tasks
docker-compose exec celery_worker celery -A app.workers.celery_app purge
```

---

## 🔧 Troubleshooting

### Backend Won't Start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Port 8000 already in use → Change port in docker-compose.yml
# - DB connection failed → Verify PostgreSQL is running
# - Import error → Rebuild image: docker-compose build backend
```

### Scan Stuck in "pending" Status

```bash
# Verify Celery worker is running
docker-compose ps celery_worker

# Check worker logs
docker-compose logs -f celery_worker

# Verify Redis is working
docker-compose exec redis redis-cli ping
# Should respond: PONG

# Restart worker
docker-compose restart celery_worker
```

### AWS Credentials Validation Failed

```bash
# Test credentials manually with AWS CLI
aws sts get-caller-identity \
  --access-key-id AKIA... \
  --secret-access-key wJalr...

# Check IAM permissions
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:user/cloudwaste-scanner \
  --action-names ec2:DescribeVolumes rds:DescribeDBInstances

# Common errors:
# - "InvalidClientTokenId" → Incorrect Access Key ID
# - "AccessDenied" → Insufficient permissions
```

### Frontend Can't Connect to API

```bash
# Verify API URL environment variable
echo $NEXT_PUBLIC_API_URL
# Should be: http://localhost:8000

# Check CORS configuration
curl -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://localhost:8000/api/v1/auth/login -v

# Should include: Access-Control-Allow-Origin: http://localhost:3000
```

### Database Connection Issues

```bash
# Verify PostgreSQL is running
docker-compose ps postgres

# Test connection
docker-compose exec postgres pg_isready -U cloudwaste

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d
docker-compose exec backend alembic upgrade head
```

---

## 🤝 Contributing

See [CLAUDE.md](CLAUDE.md) for development guidelines.

### Code Standards

**Python:**
- Type hints mandatory
- Docstrings (Google style)
- Line length: 100 chars
- Use async/await for I/O

**TypeScript:**
- Strict mode enabled
- No `any` types
- Props always typed
- API calls centralized

### Git Workflow

- **Branches:** `main`, `develop`, `feature/*`, `fix/*`
- **Commits:** Conventional Commits format

```bash
feat(api): add AWS EBS volume scanner
fix(frontend): resolve dashboard loading state
docs(readme): update setup instructions
```

---

## 📖 Additional Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed AWS setup and API examples
- **[CLAUDE.md](CLAUDE.md)** - AI assistant guidance and project rules

---

## 📄 License

[MIT License](LICENSE)

---

## 📞 Support

For questions or issues:
- Open an issue on GitHub
- See documentation in [SETUP_GUIDE.md](SETUP_GUIDE.md)
- Check [CLAUDE.md](CLAUDE.md) for project specifications

---

**Made with ❤️ for reducing cloud waste**
