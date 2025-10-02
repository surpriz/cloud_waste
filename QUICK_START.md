# CloudWaste - Démarrage Rapide 🚀

## ✅ État du Projet

**Backend** : ✅ Complètement fonctionnel
- API FastAPI : http://localhost:8000
- Swagger UI : http://localhost:8000/api/docs
- PostgreSQL + Redis opérationnels
- Celery + Celery Beat fonctionnels
- 7 détecteurs AWS implémentés

**Frontend** : ✅ Partiellement fonctionnel
- Next.js : http://localhost:3000
- Page d'accueil : ✅
- Login : ✅
- Dashboard : ✅ (structure créée)
- API client : ✅
- Zustand stores : ✅

---

## 🎬 Test Rapide (5 minutes)

### 1. Vérifier les services
```bash
cd /Users/jerome_laval/Desktop/CloudWaste
docker-compose ps

# Tous les services doivent être "Up"
```

### 2. Tester le Frontend

**Page d'accueil** :
```bash
open http://localhost:3000
```
Vous devriez voir :
- Page d'accueil CloudWaste avec hero section
- Boutons "Get Started Free" et "Sign In"
- Features section
- Call-to-action

**Page de Login** :
```bash
open http://localhost:3000/auth/login
```
Vous devriez voir :
- Formulaire de connexion
- Champs Email et Password
- Bouton "Sign in"
- Lien "Sign up"

### 3. Tester l'API Backend

**Health Check** :
```bash
curl http://localhost:8000/api/v1/health
# Réponse : {"status":"healthy","service":"CloudWaste","environment":"development"}
```

**Documentation interactive** :
```bash
open http://localhost:8000/api/docs
```

### 4. Créer un utilisateur (via API)

```bash
# 1. Créer un utilisateur
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "demo@cloudwaste.com",
    "password": "Demo123!",
    "full_name": "Demo User"
  }'

# 2. Se connecter
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=demo@cloudwaste.com&password=Demo123!"

# Copier le access_token de la réponse
```

### 5. Tester un compte AWS (avec credentials de test)

```bash
# Utiliser votre token JWT
export TOKEN="votre_access_token_ici"

# Ajouter un compte AWS
curl -X POST http://localhost:8000/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "provider": "aws",
    "account_name": "Demo AWS",
    "account_identifier": "123456789012",
    "aws_access_key_id": "VOTRE_ACCESS_KEY",
    "aws_secret_access_key": "VOTRE_SECRET_KEY",
    "regions": ["us-east-1", "eu-west-1"]
  }'
```

**Note** : Pour tester avec de vraies credentials AWS :
1. Créer un utilisateur IAM avec permissions **READ-ONLY**
2. Policy recommandée : voir [USAGE_GUIDE.md#configuration-aws](USAGE_GUIDE.md#configuration-aws)

### 6. Lancer un scan

```bash
# Récupérer l'ID de votre compte
curl http://localhost:8000/api/v1/accounts/ \
  -H "Authorization: Bearer $TOKEN"

# Lancer un scan (remplacer ACCOUNT_ID)
curl -X POST http://localhost:8000/api/v1/scans/ \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "cloud_account_id": "ACCOUNT_ID",
    "scan_type": "manual"
  }'

# Suivre le scan
curl http://localhost:8000/api/v1/scans/SCAN_ID \
  -H "Authorization: Bearer $TOKEN"
```

---

## 📊 Fonctionnalités Disponibles

### Backend API ✅
- [x] Authentification JWT (access + refresh tokens)
- [x] Multi-utilisateurs
- [x] Gestion comptes cloud (CRUD)
- [x] Validation credentials AWS
- [x] Scans manuels et automatiques (Celery)
- [x] Détection de 7 types de ressources AWS :
  - EBS Volumes non attachés
  - Elastic IPs non assignées
  - Snapshots orphelins (>90j)
  - Instances EC2 arrêtées (>30j)
  - Load Balancers sans backends
  - Instances RDS arrêtées
  - NAT Gateways inutilisés
- [x] Calcul coûts mensuels/annuels
- [x] Filtrage par type/région/statut
- [x] Statistiques agrégées
- [x] Top ressources coûteuses

### Frontend UI ✅ (Partiel)
- [x] Page d'accueil
- [x] Login page
- [x] Dashboard structure
- [x] API client TypeScript
- [x] Zustand state management
- [x] Types TypeScript complets
- [ ] Register page (à compléter)
- [ ] Pages dashboard complètes (structure créée, à tester)

---

## 🛠️ Commandes Utiles

### Docker
```bash
# Démarrer
docker-compose up -d

# Arrêter
docker-compose down

# Logs
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f celery_worker

# Redémarrer un service
docker-compose restart backend
docker-compose restart frontend
```

### Base de Données
```bash
# Se connecter à PostgreSQL
docker-compose exec postgres psql -U cloudwaste -d cloudwaste

# Requêtes utiles
SELECT COUNT(*) FROM users;
SELECT COUNT(*) FROM cloud_accounts;
SELECT COUNT(*) FROM scans WHERE status = 'completed';
SELECT COUNT(*) FROM orphan_resources;

# Voir les ressources par type
SELECT resource_type, COUNT(*), SUM(estimated_monthly_cost)
FROM orphan_resources
GROUP BY resource_type;
```

### Migrations
```bash
# Créer une migration
docker-compose exec backend alembic revision --autogenerate -m "description"

# Appliquer les migrations
docker-compose exec backend alembic upgrade head

# Historique
docker-compose exec backend alembic history
```

### Celery
```bash
# Voir les workers actifs
docker-compose exec celery_worker celery -A app.workers.celery_app inspect active

# Voir les tasks planifiées
docker-compose exec celery_worker celery -A app.workers.celery_app inspect scheduled

# Purger la queue
docker-compose exec celery_worker celery -A app.workers.celery_app purge
```

---

## 📝 Prochaines Étapes

### Pour compléter le Frontend
1. **Page Register** : Compléter `/frontend/src/app/auth/register/page.tsx`
2. **Dashboard Pages** : Tester et ajuster :
   - `/dashboard` - Vue d'ensemble ✅
   - `/dashboard/accounts` - Gestion comptes ✅
   - `/dashboard/scans` - Liste scans ✅
   - `/dashboard/resources` - Liste ressources ✅
3. **Charts** : Ajouter graphiques avec Recharts
4. **Real-time** : Polling auto pour suivre scans en cours

### Pour améliorer le Backend
1. **Notifications** : Email/Slack quand scan terminé
2. **Export** : PDF/CSV des résultats
3. **Multi-cloud** : Azure, GCP providers
4. **Permissions** : IAM permissions check avancé

---

## 🐛 Troubleshooting

### Frontend 404 sur /auth/login
```bash
# Vérifier la structure des dossiers
ls -la /Users/jerome_laval/Desktop/CloudWaste/frontend/src/app/auth/

# Devrait contenir : login/, register/, layout.tsx
# PAS de parenthèses dans les noms (éviter (auth), (dashboard))
```

### Backend connection refused
```bash
# Vérifier que le backend tourne
docker-compose ps backend

# Vérifier les logs
docker-compose logs backend --tail=50

# Redémarrer si nécessaire
docker-compose restart backend
```

### Scans restent en "pending"
```bash
# Vérifier Celery worker
docker-compose ps celery_worker

# Vérifier Redis
docker-compose exec redis redis-cli ping
# Devrait répondre : PONG

# Redémarrer worker
docker-compose restart celery_worker celery_beat
```

### Credentials AWS invalides
```bash
# Tester manuellement avec AWS CLI
aws sts get-caller-identity \
  --access-key-id AKIA... \
  --secret-access-key wJalr...

# Vérifier les permissions IAM
# Policy requise : voir USAGE_GUIDE.md
```

---

## 📚 Documentation Complète

- **[USAGE_GUIDE.md](USAGE_GUIDE.md)** - Guide d'utilisation détaillé
- **[SPRINT_3_IMPLEMENTATION.md](SPRINT_3_IMPLEMENTATION.md)** - Documentation technique Sprint 3
- **[CLAUDE.md](CLAUDE.md)** - Architecture et règles de développement
- **API Docs** : http://localhost:8000/api/docs

---

## ✨ Fonctionnalités Clés

### Détection Automatique
- ✅ Scan multi-régions AWS (max 3 pour MVP)
- ✅ 7 types de ressources orphelines
- ✅ Calcul coûts précis
- ✅ Scans quotidiens automatiques (2:00 AM UTC)

### Sécurité
- ✅ Permissions AWS **read-only uniquement**
- ✅ Credentials encryptés (Fernet)
- ✅ JWT tokens avec refresh
- ✅ Validation inputs (Pydantic)

### Performance
- ✅ Scans asynchrones (Celery)
- ✅ Cache Redis
- ✅ Index PostgreSQL optimisés
- ✅ Pagination API

---

**Version** : MVP Sprint 4
**Date** : 2 Octobre 2025
**Status** : ✅ Backend Production Ready | ⚙️ Frontend en finalisation
