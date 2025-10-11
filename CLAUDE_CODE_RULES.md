# CloudWaste - Règles et Spécifications du Projet

## 🎯 Vision du Projet

**Nom du projet :** CloudWaste (nom provisoire)

**Problème résolu :** Détecter et identifier les ressources cloud orphelines ou non utilisées (zombies) qui génèrent des coûts inutiles pour les entreprises. Études montrent que 30-35% des dépenses cloud sont gaspillées.

**Solution :** SaaS multi-cloud permettant de connecter des comptes AWS/Azure/GCP en lecture seule pour scanner et identifier les ressources inutilisées avec estimation des coûts économisables.

**État Actuel :** AWS (25 types de ressources) + Azure (disques managés) entièrement implémentés avec détection intelligente basée sur CloudWatch.

---

## 🏗️ Architecture Technique

### Stack Technologique IMPOSÉE

```yaml
Frontend:
  - Framework: Next.js 14+ (App Router)
  - Language: TypeScript (strict mode)
  - UI Library: React 18+
  - Styling: Tailwind CSS + shadcn/ui
  - State: Zustand (éviter Redux sauf nécessité)
  - Charts: Recharts ou Apache ECharts
  - Forms: React Hook Form + Zod

Backend:
  - Framework: FastAPI 0.110+
  - Language: Python 3.11+
  - Async: asyncio + aiohttp
  - Validation: Pydantic v2
  - Background Jobs: Celery + Redis
  - Task Scheduler: Celery Beat

Database:
  - Primary: PostgreSQL 15+
  - Cache/Queue: Redis 7+
  - ORM: SQLAlchemy 2.0 (async)
  - Migrations: Alembic

Cloud SDKs:
  - AWS: boto3 + aioboto3 (async)
  - Azure: azure-identity + azure-mgmt-* (compute, network, storage)
  - Future: google-cloud-*

Infrastructure:
  - Containerization: Docker + Docker Compose
  - Orchestration: Kubernetes (EKS) - Phase 2
  - CI/CD: GitHub Actions
  - Monitoring: Prometheus + Grafana (Phase 2)

DevOps:
  - Pre-commit hooks: black, ruff, mypy, prettier, eslint
  - Testing: pytest (backend), Jest + React Testing Library (frontend)
  - Coverage minimum: 70% backend, 60% frontend
```

### Architecture Globale

```
┌─────────────────────────────────────────────────────────────┐
│                        FRONTEND                              │
│  Next.js 14 (App Router) + React + TypeScript + Tailwind   │
│                                                              │
│  Pages:                                                      │
│  - /login (auth)                                            │
│  - /dashboard (overview multi-comptes)                      │
│  - /accounts (gestion connexions cloud)                     │
│  - /scans (historique + détails)                            │
│  - /resources (liste ressources orphelines)                 │
│  - /settings (user preferences)                             │
└──────────────────────┬──────────────────────────────────────┘
                       │ REST API (JSON)
                       │ WebSocket (notifications temps réel)
┌──────────────────────▼──────────────────────────────────────┐
│                     BACKEND API                              │
│              FastAPI + Python + Pydantic                     │
│                                                              │
│  Endpoints:                                                  │
│  - /api/v1/auth/*         (JWT authentication)              │
│  - /api/v1/accounts/*     (cloud accounts CRUD)             │
│  - /api/v1/scans/*        (trigger/get scans)               │
│  - /api/v1/resources/*    (orphan resources)                │
│  - /api/v1/costs/*        (cost estimations)                │
│  - /api/v1/health         (health check)                    │
└──────────────────────┬──────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
┌───────▼─────┐ ┌─────▼──────┐ ┌────▼────────┐
│  PostgreSQL │ │   Redis    │ │   Celery    │
│             │ │            │ │   Workers   │
│  - Users    │ │  - Cache   │ │             │
│  - Accounts │ │  - Sessions│ │  Tasks:     │
│  - Scans    │ │  - Queue   │ │  - scan_aws │
│  - Resources│ │            │ │  - cleanup  │
│  - Costs    │ │            │ │  - reports  │
└─────────────┘ └────────────┘ └─────┬───────┘
                                      │
                        ┌─────────────▼────────────────┐
                        │      AWS APIs (boto3)        │
                        │  - EC2, RDS, S3, EBS, ELB... │
                        └──────────────────────────────┘
```

---

## 📁 Structure des Dossiers IMPOSÉE

```
cloudwaste/
├── frontend/                    # Next.js application
│   ├── src/
│   │   ├── app/                # App Router pages
│   │   │   ├── (auth)/
│   │   │   │   ├── login/
│   │   │   │   └── register/
│   │   │   ├── (dashboard)/
│   │   │   │   ├── layout.tsx
│   │   │   │   ├── page.tsx
│   │   │   │   ├── accounts/
│   │   │   │   ├── scans/
│   │   │   │   ├── resources/
│   │   │   │   └── settings/
│   │   │   ├── layout.tsx
│   │   │   └── page.tsx        # Landing page
│   │   ├── components/
│   │   │   ├── ui/             # shadcn/ui components
│   │   │   ├── layout/         # Header, Sidebar, Footer
│   │   │   ├── dashboard/      # Dashboard-specific
│   │   │   └── charts/         # Chart components
│   │   ├── lib/
│   │   │   ├── api.ts          # API client (fetch wrapper)
│   │   │   ├── auth.ts         # Auth utilities
│   │   │   └── utils.ts        # Helpers
│   │   ├── hooks/              # Custom React hooks
│   │   ├── stores/             # Zustand stores
│   │   ├── types/              # TypeScript types
│   │   └── config/             # App configuration
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   ├── tailwind.config.ts
│   └── next.config.js
│
├── backend/                     # FastAPI application
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py             # FastAPI app entry point
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── deps.py         # Dependencies (auth, db)
│   │   │   └── v1/
│   │   │       ├── __init__.py
│   │   │       ├── auth.py
│   │   │       ├── accounts.py
│   │   │       ├── scans.py
│   │   │       ├── resources.py
│   │   │       └── costs.py
│   │   ├── core/
│   │   │   ├── __init__.py
│   │   │   ├── config.py       # Settings (Pydantic BaseSettings)
│   │   │   ├── security.py     # JWT, password hashing
│   │   │   └── database.py     # SQLAlchemy async engine
│   │   ├── models/             # SQLAlchemy models
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── scan.py
│   │   │   └── resource.py
│   │   ├── schemas/            # Pydantic schemas (request/response)
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   ├── scan.py
│   │   │   └── resource.py
│   │   ├── crud/               # CRUD operations
│   │   │   ├── __init__.py
│   │   │   ├── user.py
│   │   │   ├── account.py
│   │   │   └── scan.py
│   │   ├── providers/          # Cloud provider abstractions
│   │   │   ├── __init__.py
│   │   │   ├── base.py         # Abstract base class
│   │   │   └── aws.py          # AWS implementation
│   │   ├── services/           # Business logic
│   │   │   ├── __init__.py
│   │   │   ├── scanner.py      # Orchestration des scans
│   │   │   └── cost_calculator.py
│   │   └── workers/            # Celery tasks
│   │       ├── __init__.py
│   │       ├── celery_app.py   # Celery configuration
│   │       └── tasks.py        # Celery tasks
│   ├── alembic/                # Database migrations
│   ├── tests/
│   │   ├── api/
│   │   ├── providers/
│   │   └── services/
│   ├── requirements.txt
│   ├── pyproject.toml
│   └── pytest.ini
│
├── docker-compose.yml          # Dev environment
├── .env.example
├── .gitignore
├── README.md
└── CLAUDE_CODE_RULES.md        # Ce fichier
```

---

## 🔐 Sécurité - RÈGLES CRITIQUES

### 1. Credentials Cloud (AWS/Azure/GCP)

**IMPÉRATIF :** Les credentials cloud ne doivent JAMAIS permettre de modifier/supprimer des ressources.

**AWS IAM Policy (read-only) :**
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
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
    }
  ]
}
```

**Stockage credentials :**
- Chiffrement PostgreSQL : utiliser `pgcrypto` ou chiffrement applicatif (Fernet)
- Variables d'environnement pour master key : `ENCRYPTION_KEY`
- Rotation des credentials tous les 90 jours (alertes)

### 2. Authentication

- JWT tokens (access + refresh pattern)
- Access token expiration : 15 minutes
- Refresh token expiration : 7 jours
- Password hashing : bcrypt (cost factor 12)
- MFA via TOTP (Phase 2)

### 3. API Security

- Rate limiting : 100 req/min par user (FastAPI-limiter + Redis)
- CORS : whitelist des domaines autorisés
- HTTPS uniquement (TLS 1.3)
- Input validation stricte (Pydantic)
- SQL injection protection : ORM uniquement, jamais de raw queries

---

## 📋 Scope Fonctionnel - Ressources Détectées

CloudWaste détecte **25 types de ressources AWS** + **disques Azure** avec détection intelligente :

### Ressources AWS Core (7 types)

1. **EBS Volumes**
   - Détachés + volumes attachés inactifs (analyse CloudWatch I/O)
   - Coût : ~$0.08-0.10/GB/mois (gp3/gp2)

2. **Elastic IPs**
   - IPs non associées
   - Coût : ~$3.60/mois

3. **EBS Snapshots**
   - Orphelins, redondants, snapshots d'AMI non utilisées
   - Coût : ~$0.05/GB/mois

4. **EC2 Instances**
   - Arrêtées >30 jours + instances actives inactives (<5% CPU)
   - Coût variable selon le type d'instance

5. **Load Balancers**
   - 7 scénarios : no backends, no listeners, jamais utilisé, etc.
   - ALB/NLB/CLB/GWLB : $7.50-22/mois

6. **RDS Instances**
   - 5 scénarios : arrêtée, inactive, zero I/O, jamais connectée, sans backups
   - Coût : ~$12-560/mois

7. **NAT Gateways**
   - 4 scénarios : pas de trafic, pas de routing, mal configuré
   - Coût : ~$32.40/mois

### Ressources AWS Avancées (18 types)

8. **FSx File Systems**
   - 8 scénarios : inactif, sur-provisionné, partages non utilisés
   - Lustre/Windows/ONTAP/OpenZFS

9. **Neptune Clusters**
   - Bases de données graphe sans connexions
   - ~$250-500/mois

10. **MSK Clusters**
    - Clusters Kafka sans trafic de données
    - ~$150-300/mois par broker

11. **EKS Clusters**
    - 5 scénarios : pas de nœuds, nœuds dégradés, CPU faible, Fargate mal configuré
    - ~$73/mois (control plane) + nœuds

12. **SageMaker Endpoints**
    - Endpoints ML sans invocations
    - ~$83-165/mois

13. **Redshift Clusters**
    - Entrepôts de données sans connexions
    - ~$180-720/mois

14. **ElastiCache**
    - 4 scénarios : zero hits, hit rate faible, pas de connexions, sur-provisionné
    - ~$12-539/mois

15. **VPN Connections**
    - VPN sans transfert de données
    - ~$36/mois

16. **Transit Gateway Attachments**
    - Attachements sans trafic
    - ~$36/mois

17. **OpenSearch Domains**
    - Domaines sans requêtes de recherche
    - ~$116-164/mois

18. **Global Accelerator**
    - Accelerators sans endpoints
    - ~$18/mois

19. **Kinesis Streams**
    - 6 scénarios : inactif, sous-utilisé, rétention excessive
    - ~$10.80/mois par shard

20. **VPC Endpoints**
    - Endpoints sans interfaces réseau
    - ~$7/mois

21. **DocumentDB Clusters**
    - Bases documentaires sans connexions
    - ~$199/mois

22. **S3 Buckets**
    - 4 scénarios : vide, objets anciens, uploads incomplets, pas de lifecycle
    - Coût variable

23. **Lambda Functions**
    - 4 scénarios : provisioned concurrency non utilisée, jamais invoquée, 100% d'erreurs
    - Coût variable

24. **DynamoDB Tables**
    - 5 scénarios : sur-provisionné, GSI non utilisé, jamais utilisée, tables vides
    - Coût variable

### Ressources Azure (1 type)

25. **Managed Disks**
    - Disques Azure détachés avec calcul de coût basé sur SKU
    - ~$0.048-0.30/GB/mois selon le type

### Fonctionnalités Clés de Détection

- **Analyse CloudWatch Metrics** - Patterns d'utilisation réels, pas juste des vérifications de statut
- **Niveaux de Confiance** - Critical (90+ jours), High (30+ jours), Medium (7-30 jours), Low (<7 jours)
- **Calcul de Coût** - "Future waste" (mensuel) + "Already wasted" (cumulé depuis création)
- **Système Detection Rules** - Seuils personnalisables par type de ressource
- **Détection Multi-Scénarios** - Ressources avancées ont 4-8 scénarios de détection

### ✅ Fonctionnalités Implémentées

**Authentification & Gestion Utilisateurs :**
- ✅ Création compte utilisateur (email/password)
- ✅ Connexion JWT (access + refresh tokens)
- ✅ Gestion multi-comptes cloud

**Intégration Cloud :**
- ✅ Connexion compte AWS (IAM credentials)
- ✅ Connexion compte Azure (Service Principal)
- ✅ Validation credentials AWS/Azure
- ✅ Support multi-régions

**Détection & Analyse :**
- ✅ 25 types de ressources AWS
- ✅ Disques Azure managés
- ✅ Analyse CloudWatch Metrics
- ✅ Niveaux de confiance (Critical/High/Medium/Low)
- ✅ Calcul "Future waste" + "Already wasted"
- ✅ Système Detection Rules personnalisable

**Scans :**
- ✅ Scan manuel déclenché par user
- ✅ Scan automatique quotidien (Celery Beat)
- ✅ Historique des scans
- ✅ Workers Celery pour scans asynchrones

**Interface Utilisateur :**
- ✅ Dashboard avec métriques temps réel
- ✅ Liste détaillée des ressources avec filtres
- ✅ Actions : Voir détails / Ignorer / Marquer pour suppression / Supprimer l'enregistrement
- ✅ Page Settings avec éditeur Detection Rules
- ✅ Page de documentation complète
- ✅ Système de notifications avec alertes audio
- ✅ Toast notifications

**Calcul de Coûts :**
- ✅ Estimation coût mensuel par ressource
- ✅ Calcul coût déjà gaspillé (cumul depuis création)
- ✅ Total gaspillage mensuel par scan
- ✅ Coûts basés sur AWS/Azure pricing

### 🚀 Fonctionnalités Futures

**Phase Suivante :**
- 📅 Export CSV/PDF des résultats
- 📅 Notifications email (scan terminé + résumé)
- 📅 Graphiques tendances de coûts
- 📅 Azure complet (tous les types de ressources)
- 📅 Support GCP
- 📅 Intégrations Slack/Teams
- 📅 SSO (SAML/OIDC)
- 📅 API publique
- 📅 Suppression automatique avec workflows d'approbation

---

## 💻 Standards de Code

### Backend Python

**Linting & Formatting :**
```bash
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py311']

[tool.ruff]
line-length = 100
select = ["E", "F", "I", "N", "W", "B", "C4", "UP"]

[tool.mypy]
python_version = "3.11"
strict = true
```

**Conventions :**
- Type hints OBLIGATOIRES partout
- Docstrings format Google style
- Naming : `snake_case` pour fonctions/variables, `PascalCase` pour classes
- Async/await : préférer async pour I/O bound operations
- Error handling : custom exceptions dans `app/core/exceptions.py`
- Logging : structlog avec JSON output

**Exemple :**
```python
from typing import List
from app.schemas.resource import OrphanResource

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
    pass
```

### Frontend TypeScript

**Linting & Formatting :**
```json
// .eslintrc.json
{
  "extends": [
    "next/core-web-vitals",
    "plugin:@typescript-eslint/recommended"
  ],
  "rules": {
    "@typescript-eslint/no-unused-vars": "error",
    "@typescript-eslint/no-explicit-any": "error"
  }
}

// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noUncheckedIndexedAccess": true
  }
}
```

**Conventions :**
- Type safety : pas de `any`, utiliser `unknown` si nécessaire
- Naming : `camelCase` pour variables/fonctions, `PascalCase` pour composants
- Components : React Function Components avec TypeScript
- Props : toujours typer avec interface
- Hooks : custom hooks préfixés par `use`
- API calls : centralisés dans `lib/api.ts`

**Exemple :**
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

---

## 🗄️ Modèles de Données

### PostgreSQL Schema

```sql
-- users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    full_name VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_superuser BOOLEAN DEFAULT false,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- cloud_accounts table
CREATE TABLE cloud_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(50) NOT NULL, -- 'aws', 'azure', 'gcp'
    account_name VARCHAR(255) NOT NULL,
    account_identifier VARCHAR(255) NOT NULL, -- AWS Account ID, Azure Subscription ID

    -- Encrypted credentials
    credentials_encrypted BYTEA NOT NULL,

    -- Metadata
    regions JSON, -- ['eu-west-1', 'us-east-1']
    is_active BOOLEAN DEFAULT true,
    last_scan_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, account_identifier)
);

-- scans table
CREATE TABLE scans (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    cloud_account_id UUID REFERENCES cloud_accounts(id) ON DELETE CASCADE,
    status VARCHAR(50) NOT NULL, -- 'pending', 'running', 'completed', 'failed'
    scan_type VARCHAR(50) NOT NULL, -- 'manual', 'scheduled'

    -- Results summary
    total_resources_scanned INT DEFAULT 0,
    orphan_resources_found INT DEFAULT 0,
    estimated_monthly_waste DECIMAL(10, 2) DEFAULT 0.00,

    -- Timing
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INT,

    -- Error handling
    error_message TEXT,

    created_at TIMESTAMP DEFAULT NOW()
);

-- orphan_resources table
CREATE TABLE orphan_resources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scan_id UUID REFERENCES scans(id) ON DELETE CASCADE,
    cloud_account_id UUID REFERENCES cloud_accounts(id) ON DELETE CASCADE,

    -- Resource identification
    resource_type VARCHAR(100) NOT NULL, -- 'ebs_volume', 'elastic_ip', 'managed_disk_unattached', etc.
    resource_id VARCHAR(255) NOT NULL, -- AWS/Azure resource ID
    resource_name VARCHAR(255),
    region VARCHAR(50) NOT NULL,

    -- Cost estimation
    estimated_monthly_cost DECIMAL(10, 2),
    currency VARCHAR(3) DEFAULT 'USD',

    -- Metadata
    resource_metadata JSON, -- Specific attributes per resource type (includes 'orphan_reason', 'confidence_level', 'age_days')
    last_used_at TIMESTAMP,
    created_at_cloud TIMESTAMP, -- When created in cloud provider

    -- User actions
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'ignored', 'marked_for_deletion'
    ignored_at TIMESTAMP,
    ignored_reason TEXT,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(cloud_account_id, resource_id, resource_type)
);

-- detection_rules table
CREATE TABLE detection_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    resource_type VARCHAR(50) NOT NULL, -- 'ebs_volume', 'elastic_ip', etc.

    -- Custom rules (JSONB for flexibility)
    -- Example: {"enabled": true, "min_age_days": 14, "confidence_threshold_days": 45}
    rules JSON NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(user_id, resource_type)
);

-- Create indexes
CREATE INDEX idx_cloud_accounts_user ON cloud_accounts(user_id);
CREATE INDEX idx_scans_account ON scans(cloud_account_id);
CREATE INDEX idx_scans_status ON scans(status);
CREATE INDEX idx_orphan_resources_scan ON orphan_resources(scan_id);
CREATE INDEX idx_orphan_resources_account ON orphan_resources(cloud_account_id);
CREATE INDEX idx_orphan_resources_status ON orphan_resources(status);
```

---

## 🧪 Tests

### Backend Testing

**Requirements :**
- Coverage minimum : 70%
- pytest + pytest-asyncio
- pytest-cov pour coverage
- Fixtures pour database (async)

**Structure :**
```python
# tests/conftest.py
import pytest
from httpx import AsyncClient
from app.main import app

@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.fixture
async def test_user():
    # Create test user
    pass

# tests/api/test_scans.py
@pytest.mark.asyncio
async def test_create_scan(client: AsyncClient, test_user):
    response = await client.post(
        "/api/v1/scans/",
        headers={"Authorization": f"Bearer {test_user.token}"},
        json={"cloud_account_id": "..."}
    )
    assert response.status_code == 201
```

### Frontend Testing

**Requirements :**
- Coverage minimum : 60%
- Jest + React Testing Library
- Tests des composants critiques
- Tests des hooks customs

---

## 🔄 Workflow de Développement

### Git Flow

- `main` : production ready
- `develop` : intégration
- `feature/*` : nouvelles features
- `fix/*` : bug fixes

### Commits

Format : Conventional Commits
```
feat(api): add AWS EBS volume scanner
fix(frontend): resolve dashboard loading state
docs(readme): update setup instructions
```

### Pre-commit Hooks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/psf/black
    hooks:
      - id: black
  - repo: https://github.com/charliermarsh/ruff-pre-commit
    hooks:
      - id: ruff
  - repo: https://github.com/pre-commit/mirrors-prettier
    hooks:
      - id: prettier
```

---

## 🚀 Priorités de Développement MVP

### Sprint 1 : Infrastructure & Auth (2 semaines)
1. Setup projet (monorepo structure)
2. Docker Compose : PostgreSQL + Redis
3. Backend : FastAPI skeleton + database setup
4. Frontend : Next.js skeleton + Tailwind setup
5. Auth system : registration + login + JWT
6. User CRUD

### Sprint 2 : Cloud Accounts Management (2 semaines)
1. Models : CloudAccount
2. API : CRUD cloud accounts
3. AWS credentials validation (test connection)
4. Frontend : page gestion comptes cloud
5. Credentials encryption/decryption

### Sprint 3 : AWS Scanner Core (3 semaines)
1. Provider abstraction (`providers/base.py`)
2. AWS provider implementation
3. Detectors :
   - EBS volumes unattached
   - Elastic IPs unassigned
   - EC2 stopped instances
4. Cost calculator
5. Celery setup + tasks
6. API endpoints : trigger scan, get results

### Sprint 4 : Dashboard & Resources (2 semaines)
1. Dashboard : overview + metrics
2. Resources list page (table + filters)
3. Resource detail modal
4. Actions : ignore / mark for deletion
5. Export CSV

### Sprint 5 : Automated Scans & Polish (1 semaine)
1. Celery Beat : scheduled scans
2. Email notifications
3. Error handling & logging
4. Documentation
5. Tests coverage
6. Beta release

---

## 🎨 UI/UX Guidelines

### Design System

- **Colors :**
  - Primary : Bleu (#3B82F6)
  - Success : Vert (#10B981)
  - Warning : Orange (#F59E0B)
  - Danger : Rouge (#EF4444)
  - Savings : Vert foncé (#047857)

- **Typography :**
  - Font : Inter (from Google Fonts)
  - Headings : font-bold
  - Body : font-normal

- **Components :** shadcn/ui (installation via CLI)
  - Button, Card, Table, Dialog, Badge, Alert
  - Dropdown, Select, Input, Label

### Dashboard Layout

```
┌────────────────────────────────────────────────────────┐
│  Header (Logo, User Menu, Notifications)              │
├────────────────────────────────────────────────────────┤
│  │                                                     │
│ S│  ┌──────────────┬──────────────┬──────────────┐   │
│ i│  │   Card       │   Card       │   Card       │   │
│ d│  │ Total Waste  │  Resources   │  Last Scan   │   │
│ e│  │   $1,234     │     47       │  2h ago      │   │
│ b│  └──────────────┴──────────────┴──────────────┘   │
│ a│                                                     │
│ r│  ┌─────────────────────────────────────────────┐  │
│  │  │        Chart : Waste by Resource Type       │  │
│  │  │         (Bar or Pie Chart)                  │  │
│  │  └─────────────────────────────────────────────┘  │
│  │                                                     │
│  │  ┌─────────────────────────────────────────────┐  │
│  │  │   Recent Orphan Resources (Table)          │  │
│  │  │   Type | Name | Region | Cost | Actions    │  │
│  │  └─────────────────────────────────────────────┘  │
└──┴─────────────────────────────────────────────────────┘
```

---

## 🌍 Environment Variables

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

# AWS (for testing)
AWS_ACCESS_KEY_ID=optional-for-dev
AWS_SECRET_ACCESS_KEY=optional-for-dev

# Email (SendGrid, Mailgun, etc.)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=your-sendgrid-api-key
EMAILS_FROM_EMAIL=noreply@cloudwaste.com

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

### Frontend `.env.local`

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME=CloudWaste
```

---

## 📚 Documentation à Générer

1. **README.md** : Setup instructions, architecture overview
2. **API.md** : API endpoints documentation (OpenAPI/Swagger auto-generated)
3. **DEPLOYMENT.md** : Docker, Kubernetes deployment
4. **CONTRIBUTING.md** : Guidelines pour contributions
5. **SECURITY.md** : Security best practices

---

## ⚠️ Règles Critiques pour Claude Code

### DO ✅

1. **Toujours** typer les variables (Python type hints + TypeScript)
2. **Toujours** valider les inputs (Pydantic backend, Zod frontend)
3. **Toujours** gérer les erreurs avec try/except appropriés
4. **Toujours** utiliser async/await pour I/O operations
5. **Toujours** chiffrer les credentials avant stockage
6. **Toujours** tester les permissions AWS (read-only)
7. **Toujours** logger les erreurs (structlog)
8. **Toujours** respecter la structure de dossiers imposée

### DON'T ❌

1. **Jamais** stocker de credentials en clair
2. **Jamais** utiliser `any` en TypeScript sans raison
3. **Jamais** faire de raw SQL queries (ORM only)
4. **Jamais** commit de secrets (.env dans .gitignore)
5. **Jamais** donner de permissions write/delete aux IAM roles AWS
6. **Jamais** skip la validation d'inputs
7. **Jamais** exposer de stack traces en production
8. **Jamais** utiliser des dépendances non maintenues

---

## 🎯 Objectifs de Performance

- **API Response Time :** < 200ms (P95)
- **Scan Time (AWS account):** < 5 minutes pour 1000 ressources
- **Frontend FCP :** < 1.5s
- **Database queries :** < 50ms (avec indexes)
- **Concurrent scans :** 10 comptes simultanément

---

## 📞 Support & Feedback

**Questions pendant le développement :**
- Toujours privilégier la sécurité et la qualité du code
- Si un choix technique n'est pas clair, demander confirmation
- Documenter les décisions importantes (ADR - Architecture Decision Records)

**Conventions de nommage des branches :**
- `feature/add-ebs-volume-scanner`
- `fix/dashboard-loading-state`
- `refactor/aws-provider-optimization`

---

## 🏁 Définition de "Done" pour le MVP

Une feature est considérée terminée quand :
1. ✅ Code implémenté selon les standards
2. ✅ Tests écrits (coverage >= 70% backend, >= 60% frontend)
3. ✅ Documentation mise à jour (docstrings, README)
4. ✅ Revue de code passée
5. ✅ Tests manuels effectués
6. ✅ Aucun bug bloquant
7. ✅ Logs et error handling en place
8. ✅ Commits pushed sur la branche

---

**Version du document :** 1.0
**Dernière mise à jour :** 2025-10-01
**Auteur :** Équipe CloudWaste

---

## 🚨 Notes Importantes

Ce document est la **source de vérité** pour le développement du MVP CloudWaste.

**Claude Code** doit :
- Lire ce document AVANT de commencer toute implémentation
- Respecter STRICTEMENT l'architecture et la stack imposées
- Poser des questions si quelque chose n'est pas clair
- Ne JAMAIS dévier des règles de sécurité
- Suivre les priorités de développement définies

**Bon développement ! 🚀**
