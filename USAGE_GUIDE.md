# CloudWaste - Guide d'Utilisation

## =� Table des Mati�res

1. [Vue d'ensemble](#vue-densemble)
2. [D�marrage rapide](#d�marrage-rapide)
3. [Configuration AWS](#configuration-aws)
4. [Utilisation de l'application](#utilisation-de-lapplication)
5. [API Examples](#api-examples)
6. [Commandes utiles](#commandes-utiles)

---

## <� Vue d'ensemble

**CloudWaste** d�tecte automatiquement les ressources AWS orphelines qui g�n�rent des co�ts inutiles. Le syst�me :

-  Scanne vos comptes AWS (read-only)
-  D�tecte 7 types de ressources orphelines
-  Calcule les co�ts mensuels et annuels
-  Propose des actions via dashboard web

**Architecture actuelle** :
```
Frontend (Next.js) � Backend API (FastAPI) � PostgreSQL
                          �
                    Celery Workers � Redis
                          �
                    AWS (boto3/aioboto3)
```

---

## =� D�marrage rapide

### 1. V�rifier les services

```bash
cd /Users/jerome_laval/Desktop/CloudWaste

# V�rifier que tous les services sont lanc�s
docker-compose ps

# Devrait afficher :
#  cloudwaste_postgres       (port 5432)
#  cloudwaste_redis          (port 6379)
#  cloudwaste_backend        (port 8000)
#  cloudwaste_celery_worker
#  cloudwaste_celery_beat
#  cloudwaste_frontend       (port 3000)
```

### 2. Acc�der � l'application

**Frontend (Interface Web)** :
- URL : http://localhost:3000
- Premi�re visite : Page d'accueil
- Auth : http://localhost:3000/auth/login

**Backend (API)** :
- URL : http://localhost:8000
- Documentation interactive : http://localhost:8000/api/docs
- Health check : http://localhost:8000/api/v1/health

### 3. Cr�er un compte utilisateur

**Option A : Via l'interface web**
1. Aller sur http://localhost:3000/auth/register
2. Remplir le formulaire :
   - Email : `test@example.com`
   - Password : `Test123!`
   - Full Name : `Test User` (optionnel)
3. Cliquer sur "Create account"
4. � Redirection automatique vers le dashboard

**Option B : Via l'API (cURL)**
```bash
# Cr�er un utilisateur
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!",
    "full_name": "Test User"
  }'

# R�ponse :
{
  "id": "uuid-here",
  "email": "test@example.com",
  "full_name": "Test User",
  "is_active": true,
  "created_at": "2025-10-02T..."
}
```

### 4. Se connecter

**Option A : Via l'interface web**
1. Aller sur http://localhost:3000/auth/login
2. Email : `test@example.com`
3. Password : `Test123!`
4. � Dashboard � http://localhost:3000/dashboard

**Option B : Via l'API**
```bash
# Login pour obtenir le token JWT
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=Test123!"

# R�ponse :
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}

# Stocker le token pour les requ�tes suivantes
export TOKEN="eyJhbGc..."
```

---

##  Configuration AWS

### 1. Cr�er un utilisateur IAM AWS (Read-Only)

**Important** : CloudWaste n�cessite uniquement des permissions **lecture seule**.

**�tapes dans AWS Console** :
1. Aller dans **IAM** � **Users** � **Create user**
2. Nom : `cloudwaste-scanner`
3. Cocher "Programmatic access"
4. Permissions : Cr�er une policy custom ou utiliser les policies AWS manag�es

**Policy JSON recommand�e** (copier/coller) :
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
        "s3:GetBucket*",
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

5. **Copier** : Access Key ID + Secret Access Key
6. � **IMPORTANT** : V�rifier qu'il n'y a AUCUNE permission write/delete

### 2. Ajouter le compte AWS � CloudWaste

**Option A : Via l'interface web**
1. Dashboard � "Cloud Accounts" ou http://localhost:3000/dashboard/accounts
2. Cliquer "Add Account"
3. Remplir le formulaire :
   - **Account Name** : `My AWS Production`
   - **Account ID** : Votre AWS Account ID (12 chiffres)
   - **AWS Access Key ID** : `AKIA...`
   - **AWS Secret Access Key** : `wJalr...`
   - **Regions** : S�lectionner `us-east-1, eu-west-1, eu-central-1` (max 3 pour MVP)
   - **Description** : Optionnel
4. Cliquer "Add Account"
5. � Validation automatique des credentials

**Option B : Via l'API**
```bash
curl -X POST http://localhost:8000/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "account_name": "My AWS Production",
    "account_identifier": "123456789012",
    "aws_access_key_id": "AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "regions": ["us-east-1", "eu-west-1", "eu-central-1"],
    "description": "Production AWS account"
  }'
```

**R�ponse (succ�s)** :
```json
{
  "id": "uuid-account",
  "user_id": "uuid-user",
  "provider": "aws",
  "account_name": "My AWS Production",
  "account_identifier": "123456789012",
  "regions": {
    "regions": ["us-east-1", "eu-west-1", "eu-central-1"]
  },
  "is_active": true,
  "last_scan_at": null,
  "created_at": "2025-10-02T..."
}
```

**R�ponse (�chec - credentials invalides)** :
```json
{
  "detail": "AWS credentials validation failed: Invalid AWS Access Key ID"
}
```

### 3. Valider les permissions AWS

```bash
# Valider qu'on a bien les bonnes permissions
curl -X POST http://localhost:8000/api/v1/accounts/{account_id}/validate \
  -H "Authorization: Bearer $TOKEN"

# R�ponse :
{
  "valid": true,
  "account_info": {
    "account_id": "123456789012",
    "arn": "arn:aws:iam::123456789012:user/cloudwaste-scanner"
  },
  "permissions": {
    "ec2": true,
    "rds": true,
    "s3": true,
    "elb": true,
    "cloudwatch": true
  }
}
```

---

## = Utilisation de l'application

### 1. Lancer un scan

**Option A : Via l'interface web**
1. Dashboard � "Scans" ou http://localhost:3000/dashboard/scans
2. Cliquer "New Scan"
3. S�lectionner le compte AWS
4. Cliquer "Start Scan"
5. � Le scan d�marre en arri�re-plan (Celery)
6. � Voir la progression en temps r�el

**Option B : Via l'API**
```bash
# Cr�er un scan
curl -X POST http://localhost:8000/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "uuid-account",
    "scan_type": "manual"
  }'

# R�ponse imm�diate (scan queued) :
{
  "id": "uuid-scan",
  "cloud_account_id": "uuid-account",
  "status": "pending",
  "scan_type": "manual",
  "total_resources_scanned": 0,
  "orphan_resources_found": 0,
  "estimated_monthly_waste": 0.0,
  "created_at": "2025-10-02T..."
}
```

### 2. Suivre le scan

```bash
# R�cup�rer l'�tat du scan
curl http://localhost:8000/api/v1/scans/{scan_id} \
  -H "Authorization: Bearer $TOKEN"

# Statuts possibles :
# - "pending" : En attente dans la queue Celery
# - "in_progress" : Scan en cours
# - "completed" : Scan termin� avec succ�s
# - "failed" : Scan �chou� (voir error_message)
```

**Scan termin� (exemple)** :
```json
{
  "id": "uuid-scan",
  "status": "completed",
  "total_resources_scanned": 147,
  "orphan_resources_found": 23,
  "estimated_monthly_waste": 342.50,
  "started_at": "2025-10-02T14:00:00Z",
  "completed_at": "2025-10-02T14:03:45Z",
  "orphan_resources": [
    {
      "id": "uuid-resource-1",
      "resource_type": "ebs_volume",
      "resource_id": "vol-0abc123def456",
      "resource_name": "old-backup-volume",
      "region": "us-east-1",
      "estimated_monthly_cost": 80.0,
      "status": "active",
      "resource_metadata": {
        "size_gb": 800,
        "volume_type": "gp2",
        "created_at": "2024-01-15T10:30:00Z"
      }
    }
    // ... 22 autres ressources
  ]
}
```

### 3. Voir les ressources orphelines d�tect�es

**Via l'interface web** :
1. Dashboard � "Resources" ou http://localhost:3000/dashboard/resources
2. Voir la liste avec filtres :
   - Par type de ressource
   - Par r�gion
   - Par statut
   - Par compte cloud

**Via l'API** :
```bash
# Lister toutes les ressources
curl http://localhost:8000/api/v1/resources/ \
  -H "Authorization: Bearer $TOKEN"

# Filtrer par type
curl "http://localhost:8000/api/v1/resources/?resource_type=ebs_volume" \
  -H "Authorization: Bearer $TOKEN"

# Filtrer par r�gion
curl "http://localhost:8000/api/v1/resources/?region=us-east-1" \
  -H "Authorization: Bearer $TOKEN"

# Filtrer par statut
curl "http://localhost:8000/api/v1/resources/?status=active" \
  -H "Authorization: Bearer $TOKEN"

# Top 10 ressources les plus co�teuses
curl http://localhost:8000/api/v1/resources/top-cost?limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Marquer une ressource (ignore, � supprimer)

**Via l'API** :
```bash
# Marquer comme "ignor�e" (faux positif)
curl -X PATCH http://localhost:8000/api/v1/resources/{resource_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ignored"
  }'

# Marquer comme "� supprimer"
curl -X PATCH http://localhost:8000/api/v1/resources/{resource_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "marked_for_deletion"
  }'
```

� **Important** : CloudWaste ne supprime PAS les ressources AWS automatiquement (read-only). Vous devez supprimer manuellement via AWS Console.

### 5. Voir les statistiques

```bash
# Stats globales
curl http://localhost:8000/api/v1/resources/stats \
  -H "Authorization: Bearer $TOKEN"

# R�ponse :
{
  "total_resources": 23,
  "by_type": {
    "ebs_volume": 8,
    "elastic_ip": 5,
    "ebs_snapshot": 6,
    "nat_gateway": 2,
    "load_balancer": 2
  },
  "by_region": {
    "us-east-1": 12,
    "eu-west-1": 8,
    "eu-central-1": 3
  },
  "by_status": {
    "active": 18,
    "ignored": 3,
    "marked_for_deletion": 2
  },
  "total_monthly_cost": 342.50,
  "total_annual_cost": 4110.00
}

# Stats par compte
curl "http://localhost:8000/api/v1/resources/stats?cloud_account_id=uuid" \
  -H "Authorization: Bearer $TOKEN"

# Stats des scans
curl http://localhost:8000/api/v1/scans/summary \
  -H "Authorization: Bearer $TOKEN"

# R�ponse :
{
  "total_scans": 5,
  "completed_scans": 4,
  "failed_scans": 1,
  "total_orphan_resources": 23,
  "total_monthly_waste": 342.50,
  "last_scan_at": "2025-10-02T14:03:45Z"
}
```

---

## > Scans automatiques (Celery Beat)

**Configuration actuelle** : Scan quotidien � **2:00 AM UTC** pour tous les comptes actifs.

### V�rifier le planning

```bash
# Voir les logs de Celery Beat
docker-compose logs -f celery_beat

# Devrait afficher :
# celery_beat | [2025-10-02 02:00:00,123: INFO] Scheduler: Sending due task daily-scan-all-accounts
```

### Modifier le planning

�diter [backend/app/workers/celery_app.py](backend/app/workers/celery_app.py:27) :

```python
celery_app.conf.beat_schedule = {
    "daily-scan-all-accounts": {
        "task": "app.workers.tasks.scheduled_scan_all_accounts",
        "schedule": crontab(hour=2, minute=0),  # 2:00 AM UTC
        # Exemples :
        # crontab(hour=8, minute=30)          # 8:30 AM
        # crontab(day_of_week=1, hour=9)      # Lundi 9:00 AM
        # crontab(hour='*/6')                 # Toutes les 6 heures
    },
}
```

Red�marrer Celery Beat :
```bash
docker-compose restart celery_beat
```

---

## =� Types de ressources d�tect�es

### 1. **EBS Volumes non attach�s**
- **Crit�re** : `status = 'available'` (pas attach� � une instance)
- **Co�t** : Variable selon type (gp2: $0.10/GB, gp3: $0.08/GB, etc.)
- **M�tadonn�es** : Taille, type, zone, encryption

**Exemple** :
```json
{
  "resource_type": "ebs_volume",
  "resource_id": "vol-0abc123",
  "resource_name": "backup-volume",
  "region": "us-east-1",
  "estimated_monthly_cost": 80.0,
  "resource_metadata": {
    "size_gb": 800,
    "volume_type": "gp2",
    "created_at": "2024-01-15T10:30:00Z",
    "availability_zone": "us-east-1a",
    "encrypted": false
  }
}
```

### 2. **Elastic IPs non assign�es**
- **Crit�re** : Pas d'`AssociationId` (non attach�e � une instance/ENI)
- **Co�t** : $3.60/mois fixe
- **Action** : Lib�rer l'IP via AWS Console

### 3. **Snapshots orphelins**
- **Crit�re** : Snapshot > 90 jours ET volume source supprim�
- **Co�t** : $0.05/GB/mois
- **M�tadonn�es** : Taille, volume_id source, description

### 4. **Instances EC2 arr�t�es**
- **Crit�re** : �tat = 'stopped' depuis > 30 jours
- **Co�t** : Bas� sur volumes EBS attach�s (compute = $0 quand stopped)
- **M�tadonn�es** : Type instance, date arr�t, nombre de jours

### 5. **Load Balancers sans backends**
- **Crit�re** : Z�ro target healthy
- **Co�t** : ALB/NLB: $22/mois, CLB: $18/mois
- **Types support�s** : ALB, NLB, Classic LB

### 6. **Instances RDS arr�t�es**
- **Crit�re** : `status = 'stopped'`
- **Note** : AWS red�marre automatiquement apr�s 7 jours
- **Co�t** : Storage seul (~$0.115/GB pour gp2, compute = $0)

### 7. **NAT Gateways inutilis�s**
- **Crit�re** : `BytesOutToDestination < 1MB` sur 30 jours (CloudWatch)
- **Co�t** : $32.40/mois (base cost)
- **M�tadonn�es** : VPC, subnet, bytes out

---

## =� API Examples

### Workflow complet (bash script)

```bash
#!/bin/bash

API_URL="http://localhost:8000"

# 1. Cr�er un utilisateur
echo "1. Creating user..."
curl -X POST $API_URL/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@cloudwaste.com","password":"Demo123!","full_name":"Demo User"}'

# 2. Login
echo -e "\n2. Logging in..."
LOGIN_RESPONSE=$(curl -s -X POST $API_URL/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@cloudwaste.com&password=Demo123!")

TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
echo "Token: $TOKEN"

# 3. Ajouter un compte AWS
echo -e "\n3. Adding AWS account..."
ACCOUNT_RESPONSE=$(curl -s -X POST $API_URL/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider":"aws",
    "account_name":"Demo AWS",
    "account_identifier":"123456789012",
    "aws_access_key_id":"AKIAIOSFODNN7EXAMPLE",
    "aws_secret_access_key":"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
    "regions":["us-east-1","eu-west-1"]
  }')

ACCOUNT_ID=$(echo $ACCOUNT_RESPONSE | jq -r '.id')
echo "Account ID: $ACCOUNT_ID"

# 4. Lancer un scan
echo -e "\n4. Starting scan..."
SCAN_RESPONSE=$(curl -s -X POST $API_URL/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"cloud_account_id\":\"$ACCOUNT_ID\",\"scan_type\":\"manual\"}")

SCAN_ID=$(echo $SCAN_RESPONSE | jq -r '.id')
echo "Scan ID: $SCAN_ID"

# 5. Attendre la fin du scan (polling)
echo -e "\n5. Waiting for scan completion..."
while true; do
  SCAN_STATUS=$(curl -s $API_URL/api/v1/scans/$SCAN_ID \
    -H "Authorization: Bearer $TOKEN" | jq -r '.status')

  echo "Status: $SCAN_STATUS"

  if [ "$SCAN_STATUS" == "completed" ] || [ "$SCAN_STATUS" == "failed" ]; then
    break
  fi

  sleep 5
done

# 6. R�cup�rer les r�sultats
echo -e "\n6. Fetching results..."
curl -s $API_URL/api/v1/scans/$SCAN_ID \
  -H "Authorization: Bearer $TOKEN" | jq '.orphan_resources_found, .estimated_monthly_waste'

# 7. Lister les ressources
echo -e "\n7. Listing orphan resources..."
curl -s "$API_URL/api/v1/resources/?cloud_account_id=$ACCOUNT_ID" \
  -H "Authorization: Bearer $TOKEN" | jq '.[].resource_type' | sort | uniq -c

# 8. Stats globales
echo -e "\n8. Global stats..."
curl -s $API_URL/api/v1/resources/stats \
  -H "Authorization: Bearer $TOKEN" | jq '.total_resources, .total_monthly_cost, .total_annual_cost'

echo -e "\n Workflow completed!"
```

---

## =' Commandes utiles

### Docker

```bash
# D�marrer tous les services
docker-compose up -d

# Arr�ter tous les services
docker-compose down

# Voir les logs
docker-compose logs -f                    # Tous les services
docker-compose logs -f backend            # Backend uniquement
docker-compose logs -f celery_worker      # Worker uniquement
docker-compose logs -f frontend           # Frontend uniquement

# Red�marrer un service
docker-compose restart backend
docker-compose restart celery_worker

# Reconstruire les images
docker-compose build backend
docker-compose up -d --build

# Voir les stats
docker-compose ps
docker stats
```

### Base de donn�es

```bash
# Se connecter � PostgreSQL
docker-compose exec postgres psql -U cloudwaste -d cloudwaste

# Requ�tes SQL utiles
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM cloud_accounts;
SELECT COUNT(*) FROM scans WHERE status = 'completed';
SELECT COUNT(*) FROM orphan_resources;

SELECT resource_type, COUNT(*), SUM(estimated_monthly_cost)
FROM orphan_resources
GROUP BY resource_type;

SELECT region, COUNT(*)
FROM orphan_resources
GROUP BY region;

# Voir le dernier scan
SELECT id, status, orphan_resources_found, estimated_monthly_waste, completed_at
FROM scans
ORDER BY created_at DESC
LIMIT 1;
```

### Migrations

```bash
# Cr�er une nouvelle migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Appliquer les migrations
docker-compose exec backend alembic upgrade head

# Rollback
docker-compose exec backend alembic downgrade -1

# Voir l'historique
docker-compose exec backend alembic history
```

### Celery

```bash
# Voir les workers actifs
docker-compose exec celery_worker celery -A app.workers.celery_app inspect active

# Voir les tasks en queue
docker-compose exec celery_worker celery -A app.workers.celery_app inspect scheduled

# Voir les stats
docker-compose exec celery_worker celery -A app.workers.celery_app inspect stats

# Purger la queue
docker-compose exec celery_worker celery -A app.workers.celery_app purge
```

### Frontend

```bash
# Installer les d�pendances
cd frontend
npm install

# D�veloppement
npm run dev

# Build production
npm run build
npm start

# Linter
npm run lint
```

---

## = Troubleshooting

### Probl�me : Backend ne d�marre pas

```bash
# V�rifier les logs
docker-compose logs backend

# Erreurs communes :
# - Port 8000 d�j� utilis� � Changer le port dans docker-compose.yml
# - DB connection failed � V�rifier PostgreSQL
# - Import error � Reconstruire l'image : docker-compose build backend
```

### Probl�me : Scan reste en "pending"

```bash
# V�rifier que Celery worker tourne
docker-compose ps celery_worker

# V�rifier les logs du worker
docker-compose logs -f celery_worker

# V�rifier Redis
docker-compose exec redis redis-cli ping
# Devrait r�pondre : PONG

# Red�marrer le worker
docker-compose restart celery_worker
```

### Probl�me : "AWS credentials validation failed"

```bash
# Tester les credentials AWS manuellement
aws sts get-caller-identity \
  --access-key-id AKIA... \
  --secret-access-key wJalr...

# V�rifier les permissions IAM
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:user/cloudwaste-scanner \
  --action-names ec2:DescribeVolumes rds:DescribeDBInstances

# Si erreur "InvalidClientTokenId" � Cl�s incorrectes
# Si erreur "AccessDenied" � Permissions insuffisantes
```

### Probl�me : Frontend ne se connecte pas � l'API

```bash
# V�rifier la variable d'environnement
echo $NEXT_PUBLIC_API_URL
# Devrait �tre : http://localhost:8000

# V�rifier CORS
curl -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://localhost:8000/api/v1/auth/login -v

# Devrait avoir : Access-Control-Allow-Origin: http://localhost:3000
```

---

## =� Prochaines �tapes

### Fonctionnalit�s � venir (Sprint 5)

1. **Multi-cloud** : Support Azure et GCP
2. **Notifications** : Email/Slack quand scan termin�
3. **Rapports** : Export PDF/Excel des r�sultats
4. **Scheduling avanc�** : Scans custom par user
5. **Suppression assist�e** : G�n�ration de scripts Terraform destroy

### Contribuer

Pour ajouter une nouvelle fonctionnalit� :

1. Backend : Ajouter endpoint dans `/backend/app/api/v1/`
2. Frontend : Cr�er page dans `/frontend/src/app/(dashboard)/`
3. Store : Ajouter actions Zustand dans `/frontend/src/stores/`
4. Types : Mettre � jour `/frontend/src/types/index.ts`
5. API Client : Mettre � jour `/frontend/src/lib/api.ts`

---

## =� Ressources

- **Documentation API** : http://localhost:8000/api/docs
- **Sprint 3 Implementation** : [SPRINT_3_IMPLEMENTATION.md](SPRINT_3_IMPLEMENTATION.md)
- **Architecture** : [CLAUDE.md](CLAUDE.md)
- **Code Guidelines** : [CLAUDE.md#code-standards](CLAUDE.md#code-standards)

---

**Version** : MVP Sprint 4
**Date** : 2 Octobre 2025
**Auteur** : Claude Code
**Status** :  Production Ready
