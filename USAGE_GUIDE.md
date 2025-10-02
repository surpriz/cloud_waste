# CloudWaste - Guide d'Utilisation

## =Ë Table des Matières

1. [Vue d'ensemble](#vue-densemble)
2. [Démarrage rapide](#démarrage-rapide)
3. [Configuration AWS](#configuration-aws)
4. [Utilisation de l'application](#utilisation-de-lapplication)
5. [API Examples](#api-examples)
6. [Commandes utiles](#commandes-utiles)

---

## <¯ Vue d'ensemble

**CloudWaste** détecte automatiquement les ressources AWS orphelines qui génèrent des coûts inutiles. Le système :

-  Scanne vos comptes AWS (read-only)
-  Détecte 7 types de ressources orphelines
-  Calcule les coûts mensuels et annuels
-  Propose des actions via dashboard web

**Architecture actuelle** :
```
Frontend (Next.js) ” Backend API (FastAPI) ” PostgreSQL
                          “
                    Celery Workers ” Redis
                          “
                    AWS (boto3/aioboto3)
```

---

## =€ Démarrage rapide

### 1. Vérifier les services

```bash
cd /Users/jerome_laval/Desktop/CloudWaste

# Vérifier que tous les services sont lancés
docker-compose ps

# Devrait afficher :
#  cloudwaste_postgres       (port 5432)
#  cloudwaste_redis          (port 6379)
#  cloudwaste_backend        (port 8000)
#  cloudwaste_celery_worker
#  cloudwaste_celery_beat
#  cloudwaste_frontend       (port 3000)
```

### 2. Accéder à l'application

**Frontend (Interface Web)** :
- URL : http://localhost:3000
- Première visite : Page d'accueil
- Auth : http://localhost:3000/auth/login

**Backend (API)** :
- URL : http://localhost:8000
- Documentation interactive : http://localhost:8000/api/docs
- Health check : http://localhost:8000/api/v1/health

### 3. Créer un compte utilisateur

**Option A : Via l'interface web**
1. Aller sur http://localhost:3000/auth/register
2. Remplir le formulaire :
   - Email : `test@example.com`
   - Password : `Test123!`
   - Full Name : `Test User` (optionnel)
3. Cliquer sur "Create account"
4. ’ Redirection automatique vers le dashboard

**Option B : Via l'API (cURL)**
```bash
# Créer un utilisateur
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "test@example.com",
    "password": "Test123!",
    "full_name": "Test User"
  }'

# Réponse :
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
4. ’ Dashboard à http://localhost:3000/dashboard

**Option B : Via l'API**
```bash
# Login pour obtenir le token JWT
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=test@example.com&password=Test123!"

# Réponse :
{
  "access_token": "eyJhbGc...",
  "refresh_token": "eyJhbGc...",
  "token_type": "bearer"
}

# Stocker le token pour les requêtes suivantes
export TOKEN="eyJhbGc..."
```

---

##  Configuration AWS

### 1. Créer un utilisateur IAM AWS (Read-Only)

**Important** : CloudWaste nécessite uniquement des permissions **lecture seule**.

**Étapes dans AWS Console** :
1. Aller dans **IAM** ’ **Users** ’ **Create user**
2. Nom : `cloudwaste-scanner`
3. Cocher "Programmatic access"
4. Permissions : Créer une policy custom ou utiliser les policies AWS managées

**Policy JSON recommandée** (copier/coller) :
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
6.   **IMPORTANT** : Vérifier qu'il n'y a AUCUNE permission write/delete

### 2. Ajouter le compte AWS à CloudWaste

**Option A : Via l'interface web**
1. Dashboard ’ "Cloud Accounts" ou http://localhost:3000/dashboard/accounts
2. Cliquer "Add Account"
3. Remplir le formulaire :
   - **Account Name** : `My AWS Production`
   - **Account ID** : Votre AWS Account ID (12 chiffres)
   - **AWS Access Key ID** : `AKIA...`
   - **AWS Secret Access Key** : `wJalr...`
   - **Regions** : Sélectionner `us-east-1, eu-west-1, eu-central-1` (max 3 pour MVP)
   - **Description** : Optionnel
4. Cliquer "Add Account"
5. ’ Validation automatique des credentials

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

**Réponse (succès)** :
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

**Réponse (échec - credentials invalides)** :
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

# Réponse :
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
1. Dashboard ’ "Scans" ou http://localhost:3000/dashboard/scans
2. Cliquer "New Scan"
3. Sélectionner le compte AWS
4. Cliquer "Start Scan"
5. ’ Le scan démarre en arrière-plan (Celery)
6. ’ Voir la progression en temps réel

**Option B : Via l'API**
```bash
# Créer un scan
curl -X POST http://localhost:8000/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "uuid-account",
    "scan_type": "manual"
  }'

# Réponse immédiate (scan queued) :
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
# Récupérer l'état du scan
curl http://localhost:8000/api/v1/scans/{scan_id} \
  -H "Authorization: Bearer $TOKEN"

# Statuts possibles :
# - "pending" : En attente dans la queue Celery
# - "in_progress" : Scan en cours
# - "completed" : Scan terminé avec succès
# - "failed" : Scan échoué (voir error_message)
```

**Scan terminé (exemple)** :
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

### 3. Voir les ressources orphelines détectées

**Via l'interface web** :
1. Dashboard ’ "Resources" ou http://localhost:3000/dashboard/resources
2. Voir la liste avec filtres :
   - Par type de ressource
   - Par région
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

# Filtrer par région
curl "http://localhost:8000/api/v1/resources/?region=us-east-1" \
  -H "Authorization: Bearer $TOKEN"

# Filtrer par statut
curl "http://localhost:8000/api/v1/resources/?status=active" \
  -H "Authorization: Bearer $TOKEN"

# Top 10 ressources les plus coûteuses
curl http://localhost:8000/api/v1/resources/top-cost?limit=10 \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Marquer une ressource (ignore, à supprimer)

**Via l'API** :
```bash
# Marquer comme "ignorée" (faux positif)
curl -X PATCH http://localhost:8000/api/v1/resources/{resource_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "ignored"
  }'

# Marquer comme "à supprimer"
curl -X PATCH http://localhost:8000/api/v1/resources/{resource_id} \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "status": "marked_for_deletion"
  }'
```

  **Important** : CloudWaste ne supprime PAS les ressources AWS automatiquement (read-only). Vous devez supprimer manuellement via AWS Console.

### 5. Voir les statistiques

```bash
# Stats globales
curl http://localhost:8000/api/v1/resources/stats \
  -H "Authorization: Bearer $TOKEN"

# Réponse :
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

# Réponse :
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

**Configuration actuelle** : Scan quotidien à **2:00 AM UTC** pour tous les comptes actifs.

### Vérifier le planning

```bash
# Voir les logs de Celery Beat
docker-compose logs -f celery_beat

# Devrait afficher :
# celery_beat | [2025-10-02 02:00:00,123: INFO] Scheduler: Sending due task daily-scan-all-accounts
```

### Modifier le planning

Éditer [backend/app/workers/celery_app.py](backend/app/workers/celery_app.py:27) :

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

Redémarrer Celery Beat :
```bash
docker-compose restart celery_beat
```

---

## =Ê Types de ressources détectées

### 1. **EBS Volumes non attachés**
- **Critère** : `status = 'available'` (pas attaché à une instance)
- **Coût** : Variable selon type (gp2: $0.10/GB, gp3: $0.08/GB, etc.)
- **Métadonnées** : Taille, type, zone, encryption

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

### 2. **Elastic IPs non assignées**
- **Critère** : Pas d'`AssociationId` (non attachée à une instance/ENI)
- **Coût** : $3.60/mois fixe
- **Action** : Libérer l'IP via AWS Console

### 3. **Snapshots orphelins**
- **Critère** : Snapshot > 90 jours ET volume source supprimé
- **Coût** : $0.05/GB/mois
- **Métadonnées** : Taille, volume_id source, description

### 4. **Instances EC2 arrêtées**
- **Critère** : État = 'stopped' depuis > 30 jours
- **Coût** : Basé sur volumes EBS attachés (compute = $0 quand stopped)
- **Métadonnées** : Type instance, date arrêt, nombre de jours

### 5. **Load Balancers sans backends**
- **Critère** : Zéro target healthy
- **Coût** : ALB/NLB: $22/mois, CLB: $18/mois
- **Types supportés** : ALB, NLB, Classic LB

### 6. **Instances RDS arrêtées**
- **Critère** : `status = 'stopped'`
- **Note** : AWS redémarre automatiquement après 7 jours
- **Coût** : Storage seul (~$0.115/GB pour gp2, compute = $0)

### 7. **NAT Gateways inutilisés**
- **Critère** : `BytesOutToDestination < 1MB` sur 30 jours (CloudWatch)
- **Coût** : $32.40/mois (base cost)
- **Métadonnées** : VPC, subnet, bytes out

---

## =à API Examples

### Workflow complet (bash script)

```bash
#!/bin/bash

API_URL="http://localhost:8000"

# 1. Créer un utilisateur
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

# 6. Récupérer les résultats
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
# Démarrer tous les services
docker-compose up -d

# Arrêter tous les services
docker-compose down

# Voir les logs
docker-compose logs -f                    # Tous les services
docker-compose logs -f backend            # Backend uniquement
docker-compose logs -f celery_worker      # Worker uniquement
docker-compose logs -f frontend           # Frontend uniquement

# Redémarrer un service
docker-compose restart backend
docker-compose restart celery_worker

# Reconstruire les images
docker-compose build backend
docker-compose up -d --build

# Voir les stats
docker-compose ps
docker stats
```

### Base de données

```bash
# Se connecter à PostgreSQL
docker-compose exec postgres psql -U cloudwaste -d cloudwaste

# Requêtes SQL utiles
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
# Créer une nouvelle migration
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
# Installer les dépendances
cd frontend
npm install

# Développement
npm run dev

# Build production
npm run build
npm start

# Linter
npm run lint
```

---

## = Troubleshooting

### Problème : Backend ne démarre pas

```bash
# Vérifier les logs
docker-compose logs backend

# Erreurs communes :
# - Port 8000 déjà utilisé ’ Changer le port dans docker-compose.yml
# - DB connection failed ’ Vérifier PostgreSQL
# - Import error ’ Reconstruire l'image : docker-compose build backend
```

### Problème : Scan reste en "pending"

```bash
# Vérifier que Celery worker tourne
docker-compose ps celery_worker

# Vérifier les logs du worker
docker-compose logs -f celery_worker

# Vérifier Redis
docker-compose exec redis redis-cli ping
# Devrait répondre : PONG

# Redémarrer le worker
docker-compose restart celery_worker
```

### Problème : "AWS credentials validation failed"

```bash
# Tester les credentials AWS manuellement
aws sts get-caller-identity \
  --access-key-id AKIA... \
  --secret-access-key wJalr...

# Vérifier les permissions IAM
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::123456789012:user/cloudwaste-scanner \
  --action-names ec2:DescribeVolumes rds:DescribeDBInstances

# Si erreur "InvalidClientTokenId" ’ Clés incorrectes
# Si erreur "AccessDenied" ’ Permissions insuffisantes
```

### Problème : Frontend ne se connecte pas à l'API

```bash
# Vérifier la variable d'environnement
echo $NEXT_PUBLIC_API_URL
# Devrait être : http://localhost:8000

# Vérifier CORS
curl -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -X OPTIONS http://localhost:8000/api/v1/auth/login -v

# Devrait avoir : Access-Control-Allow-Origin: http://localhost:3000
```

---

## =È Prochaines étapes

### Fonctionnalités à venir (Sprint 5)

1. **Multi-cloud** : Support Azure et GCP
2. **Notifications** : Email/Slack quand scan terminé
3. **Rapports** : Export PDF/Excel des résultats
4. **Scheduling avancé** : Scans custom par user
5. **Suppression assistée** : Génération de scripts Terraform destroy

### Contribuer

Pour ajouter une nouvelle fonctionnalité :

1. Backend : Ajouter endpoint dans `/backend/app/api/v1/`
2. Frontend : Créer page dans `/frontend/src/app/(dashboard)/`
3. Store : Ajouter actions Zustand dans `/frontend/src/stores/`
4. Types : Mettre à jour `/frontend/src/types/index.ts`
5. API Client : Mettre à jour `/frontend/src/lib/api.ts`

---

## =Ú Ressources

- **Documentation API** : http://localhost:8000/api/docs
- **Sprint 3 Implementation** : [SPRINT_3_IMPLEMENTATION.md](SPRINT_3_IMPLEMENTATION.md)
- **Architecture** : [CLAUDE.md](CLAUDE.md)
- **Code Guidelines** : [CLAUDE.md#code-standards](CLAUDE.md#code-standards)

---

**Version** : MVP Sprint 4
**Date** : 2 Octobre 2025
**Auteur** : Claude Code
**Status** :  Production Ready
