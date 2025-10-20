# CloudWaste - Cloud Resource Waste Detection Platform

**CloudWaste** is a SaaS platform that detects and identifies orphaned or unused cloud resources (zombies) to help businesses reduce unnecessary costs. Studies show that 30-35% of cloud spending is wasted.

## 🎯 Project Vision

**Problem:** Businesses waste significant money on orphaned cloud resources that are no longer in use.

**Solution:** Multi-cloud SaaS platform that connects to AWS/Azure/GCP accounts in read-only mode to scan and identify unused resources with cost-saving estimates.

**Current Status:** AWS (25 resource types) + Azure (managed disks) fully implemented with intelligent CloudWatch-based detection.

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
- azure-identity + azure-mgmt-* (Azure)

**Infrastructure:**
- Docker + Docker Compose
- Pre-commit hooks (black, ruff, mypy, prettier, eslint)

---

## 🚀 Quick Start

### ⚠️ CRITICAL - READ BEFORE FIRST STARTUP

**CloudWaste uses `ENCRYPTION_KEY` to encrypt ALL cloud account credentials** (AWS access keys, Azure client secrets, etc.).

**IF THIS KEY IS LOST OR CHANGED:**
- ❌ **ALL cloud accounts become permanently UNRECOVERABLE**
- ❌ **ALL users must re-enter their credentials**
- ❌ **Complete data loss** for encrypted cloud credentials

**CloudWaste now auto-protects against key loss:**
- ✅ Key generated ONCE on first startup (`init_encryption.sh`)
- ✅ Stored in persistent Docker volume (`encryption_key`)
- ✅ Validated on every startup (blocks if key changed)
- ✅ See `ENCRYPTION_KEY_MANAGEMENT.md` for complete details

**⚠️ In production: BACKUP YOUR ENCRYPTION KEY IMMEDIATELY AFTER FIRST STARTUP!**

---

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local development)
- Node.js 20+ (for local development)

### 1. Clone the Repository

```bash
git clone <repository-url>
cd CloudWaste
```

### 2. Start the Application (First Time)

```bash
# Copy environment template
cp .env.example .env

# Start all services
docker-compose up -d
```

**What happens on first startup:**
1. `init_encryption.sh` runs automatically
2. Generates `ENCRYPTION_KEY` (Fernet key) → Saved in `.encryption_key`
3. Generates and saves to persistent Docker volume
4. Updates `.env` with generated key
5. Application validates key and starts

**Check logs to verify:**
```bash
docker-compose logs backend | grep "🔐"
# Should show: ✅ ENCRYPTION_KEY validated
```

### 3. Backup Your Encryption Key (MANDATORY for Production)

```bash
# After first startup, backup the encryption key
docker run --rm \
  -v cloudwaste_encryption_key:/data \
  -v $(pwd):/backup \
  alpine cp /data/.encryption_key /backup/encryption_key.backup

# Store backup in a SECURE location:
# - Password manager (1Password, Bitwarden)
# - Encrypted USB drive
# - Secure cloud storage (encrypted)
```

**See `ENCRYPTION_KEY_MANAGEMENT.md` for complete backup/restore procedures.**

### 4. Access the Application

After startup (`docker-compose up -d`):

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

## 📋 Resource Detection - AWS & Azure

CloudWaste detects **25 types of orphaned AWS resources** + **Azure managed disks** with intelligent CloudWatch-based detection:

### Core AWS Resources (7 types)
1. **EBS Volumes** - Unattached + idle volumes with I/O analysis (~$0.08-0.10/GB/month)
2. **Elastic IPs** - Unassociated IP addresses (~$3.60/month)
3. **EBS Snapshots** - Orphaned, redundant, and unused AMI snapshots (~$0.05/GB/month)
4. **EC2 Instances** - Stopped >30 days + idle running instances (<5% CPU)
5. **Load Balancers** - 7 detection scenarios: no backends, no listeners, never used, etc. (ALB/NLB/CLB/GWLB: $7.50-22/month)
6. **RDS Instances** - 5 scenarios: stopped, idle, zero I/O, never connected, no backups (~$12-560/month)
7. **NAT Gateways** - 4 scenarios: no traffic, no routing, misconfigured (~$32.40/month)

### Advanced AWS Resources (18 types)
8. **FSx File Systems** - 8 scenarios: inactive, over-provisioned, unused shares (Lustre/Windows/ONTAP/OpenZFS)
9. **Neptune Clusters** - Graph databases with no connections (~$250-500/month)
10. **MSK Clusters** - Kafka clusters with no data traffic (~$150-300/month per broker)
11. **EKS Clusters** - 5 scenarios: no nodes, unhealthy, low CPU, misconfigured Fargate (~$73/month + nodes)
12. **SageMaker Endpoints** - ML endpoints with no invocations (~$83-165/month)
13. **Redshift Clusters** - Data warehouses with no connections (~$180-720/month)
14. **ElastiCache** - 4 scenarios: zero hits, low hit rate, no connections, over-provisioned (~$12-539/month)
15. **VPN Connections** - VPN with no data transfer (~$36/month)
16. **Transit Gateway Attachments** - Attachments with no traffic (~$36/month)
17. **OpenSearch Domains** - Domains with no search requests (~$116-164/month)
18. **Global Accelerator** - Accelerators with no endpoints (~$18/month)
19. **Kinesis Streams** - 6 scenarios: inactive, under-utilized, excessive retention (~$10.80/month per shard)
20. **VPC Endpoints** - Endpoints with no network interfaces (~$7/month)
21. **DocumentDB Clusters** - Document databases with no connections (~$199/month)
22. **S3 Buckets** - 4 scenarios: empty, old objects, incomplete uploads, no lifecycle policy
23. **Lambda Functions** - 4 scenarios: unused provisioned concurrency, never invoked, zero invocations, 100% failures
24. **DynamoDB Tables** - 5 scenarios: over-provisioned, unused GSI, never used, empty tables

### Azure Resources (1 type)
25. **Managed Disks** - Unattached Azure disks with SKU-based cost calculation (~$0.048-0.30/GB/month)

### Key Detection Features
- **Intelligent CloudWatch Metrics Analysis** - Not just status checks, but actual usage patterns
- **Confidence Levels** - Critical (90+ days), High (30+ days), Medium (7-30 days), Low (<7 days)
- **Cost Calculation** - "Future waste" (monthly) + "Already wasted" (cumulative)
- **Customizable Detection Rules** - Per-resource type thresholds and criteria

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
      "fsx:Describe*",
      "neptune:Describe*",
      "kafka:Describe*",
      "kafka:List*",
      "eks:Describe*",
      "eks:List*",
      "sagemaker:Describe*",
      "redshift:Describe*",
      "elasticache:Describe*",
      "ec2:DescribeVpnConnections",
      "ec2:DescribeTransitGatewayAttachments",
      "es:Describe*",
      "globalaccelerator:Describe*",
      "kinesis:Describe*",
      "kinesis:List*",
      "ec2:DescribeVpcEndpoints",
      "docdb:Describe*",
      "lambda:List*",
      "lambda:Get*",
      "dynamodb:Describe*",
      "dynamodb:List*",
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

CloudWaste requires a **Service Principal** with the following permissions:
- **Reader** role on subscription (for listing resources)
- **Monitoring Reader** role (for Azure Monitor metrics)

```bash
# Create Service Principal with Reader role
az ad sp create-for-rbac --name "CloudWaste-Scanner" \
  --role "Reader" \
  --scopes "/subscriptions/{subscription-id}"
```

---

## 📊 Database Schema

### Core Tables

- **users** - User accounts
- **cloud_accounts** - Cloud provider accounts (credentials encrypted, supports AWS + Azure)
- **scans** - Scan jobs and results
- **orphan_resources** - Detected orphaned resources (25 AWS types + Azure)
- **detection_rules** - User-customizable detection rules per resource type

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

## 🗓️ Development Progress

### ✅ Completed Features

**Phase 1: Core Infrastructure**
- ✅ FastAPI + Next.js monorepo setup
- ✅ Docker Compose (PostgreSQL + Redis + Celery)
- ✅ JWT Authentication (registration, login)
- ✅ User management

**Phase 2: Cloud Provider Integration**
- ✅ AWS provider (25 resource types)
- ✅ Azure provider (managed disks)
- ✅ Credentials encryption (Fernet)
- ✅ Multi-account support
- ✅ Credentials validation

**Phase 3: Intelligent Detection**
- ✅ CloudWatch metrics analysis
- ✅ Confidence levels (Critical/High/Medium/Low)
- ✅ Cost calculation (future + already wasted)
- ✅ Detection Rules system (customizable per resource)
- ✅ 25 AWS resource types
- ✅ Azure managed disks

**Phase 4: UI/UX**
- ✅ Dashboard with real-time metrics
- ✅ Scans page with history
- ✅ Resources page with filtering
- ✅ Account management
- ✅ Settings with Detection Rules editor
- ✅ Comprehensive documentation page
- ✅ Notifications system with audio alerts
- ✅ Toast notifications

**Phase 5: Automation**
- ✅ Celery workers for background scans
- ✅ Celery Beat for scheduled scans
- ✅ Manual scan triggering

### 🚀 Upcoming Features

**Phase 6: Advanced Analytics**
- 📅 Cost trends and forecasting
- 📅 Resource usage history graphs
- 📅 Email notifications
- 📅 Export to CSV/PDF reports

**Phase 7: Multi-Cloud Expansion**
- 📅 Complete Azure implementation (all resource types)
- 📅 GCP provider integration
- 📅 Cross-cloud cost comparison

**Phase 8: Enterprise Features**
- 📅 SSO (SAML/OIDC)
- 📅 Role-based access control (RBAC)
- 📅 Audit logs
- 📅 Slack/Teams integrations
- 📅 Automated remediation (with approval workflows)

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

# Resources by type (top 10)
SELECT resource_type, COUNT(*) as count, SUM(estimated_monthly_cost) as total_cost
FROM orphan_resources
WHERE status = 'active'
GROUP BY resource_type
ORDER BY total_cost DESC
LIMIT 10;

# Resources by cloud provider
SELECT
  CASE
    WHEN resource_type LIKE '%managed_disk%' THEN 'Azure'
    ELSE 'AWS'
  END as provider,
  COUNT(*) as count,
  SUM(estimated_monthly_cost) as total_monthly_waste
FROM orphan_resources
WHERE status = 'active'
GROUP BY provider;

# Resources by region
SELECT region, COUNT(*), SUM(estimated_monthly_cost)
FROM orphan_resources
WHERE status = 'active'
GROUP BY region
ORDER BY SUM(estimated_monthly_cost) DESC;

# Latest scan
SELECT id, status, orphan_resources_found, estimated_monthly_waste, completed_at
FROM scans
ORDER BY created_at DESC
LIMIT 1;

# User detection rules
SELECT resource_type, rules
FROM detection_rules
WHERE user_id = 'your-user-id'
ORDER BY resource_type;
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

## 🚀 Production Deployment

CloudWaste is production-ready with full VPS deployment automation.

### Quick Production Setup (30 minutes)

Deploy CloudWaste on your Ubuntu VPS with automated scripts:

```bash
# 1. Copy setup script to VPS
scp deployment/setup-vps.sh administrator@YOUR_VPS_IP:~/
# Note: Replace 'administrator' with your admin user (root, ubuntu, admin, etc.)

# 2. Run initialization script (installs Docker, Nginx, SSL, monitoring)
ssh administrator@YOUR_VPS_IP
sudo bash ~/setup-vps.sh

# 3. Clone and deploy
ssh cloudwaste@YOUR_VPS_IP
cd /opt/cloudwaste
git clone https://github.com/YOUR_USERNAME/CloudWaste.git .
bash deployment/deploy.sh
```

**Complete documentation:**
- **[deployment/QUICKSTART.md](deployment/QUICKSTART.md)** - 30-minute production setup guide
- **[VPS_PRODUCTION_GUIDE.md](VPS_PRODUCTION_GUIDE.md)** - Complete production manual
- **[deployment/README.md](deployment/README.md)** - Deployment scripts documentation
- **[deployment/DEPLOYMENT_CHECKLIST.md](deployment/DEPLOYMENT_CHECKLIST.md)** - Pre-flight checklist

### Production Features

✅ **Security Hardened**
- UFW firewall configured
- Fail2Ban SSH protection
- SSL/TLS with Let's Encrypt
- Non-root user with sudo
- Automatic security updates

✅ **Monitoring & Observability**
- Netdata for system metrics
- Portainer for Docker management
- Health check scripts
- Centralized logging

✅ **Automated Deployments**
- GitHub Actions CI/CD
- Zero-downtime deployments
- Automatic database migrations
- Docker Compose orchestration

✅ **Backup & Recovery**
- Automated daily backups
- PostgreSQL dumps
- Docker volumes backup
- 7-day retention policy
- One-command restore

✅ **Production Stack**
- Nginx reverse proxy
- Docker containers with health checks
- PostgreSQL with persistent volumes
- Redis for caching/queuing
- Celery for background jobs
- Ollama for AI (optional)

### Available Scripts

```bash
# Deployment
bash deploy.sh              # Deploy/update application
bash backup.sh              # Manual backup
bash restore.sh backup.tar.gz  # Restore from backup
bash health-check.sh        # Full system health check

# Configuration
bash setup-vps.sh           # Initial VPS setup
bash install-nginx-config.sh  # Install Nginx config
```

### Deployment Architecture

```
Internet (80/443)
    ↓
Nginx (SSL termination + reverse proxy)
    ↓
┌──────────────┬──────────────┬──────────────┐
│   Frontend   │   Backend    │  Monitoring  │
│  (Next.js)   │  (FastAPI)   │  (Netdata)   │
│    :3000     │    :8000     │   :19999     │
└──────┬───────┴──────┬───────┴──────────────┘
       │              │
   ┌───▼────┐    ┌───▼────────┐
   │Postgres│    │Celery+Redis│
   │ :5432  │    │  :6379     │
   └────────┘    └────────────┘
```

---

## 📖 Additional Documentation

- **[SETUP_GUIDE.md](SETUP_GUIDE.md)** - Detailed AWS setup and API examples
- **[CLAUDE.md](CLAUDE.md)** - AI assistant guidance and project rules
- **[VPS_PRODUCTION_GUIDE.md](VPS_PRODUCTION_GUIDE.md)** - Complete VPS production guide
- **[deployment/QUICKSTART.md](deployment/QUICKSTART.md)** - Quick production deployment
- **[ENCRYPTION_KEY_MANAGEMENT.md](ENCRYPTION_KEY_MANAGEMENT.md)** - Encryption key security

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
