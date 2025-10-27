# 🚀 Workflow de Développement et Déploiement

> **📌 Dernière mise à jour** : Workflow simplifié avec scripts automatisés et déploiement GitHub Actions

---

## 🎯 Workflow Ultra-Simple (Recommandé)

### **Sur votre machine locale (Mac)**

```bash
# 1. Démarrer l'environnement de développement
cd /Users/jerome_laval/Desktop/CloudWaste
bash dev-start.sh

# 2. Développer et tester
# → Frontend: http://localhost:3000
# → Backend API: http://localhost:8000
# → Hot-reload activé automatiquement

# 3. Arrêter l'environnement
bash dev-stop.sh

# 4. Pousser vers production
git add .
git commit -m "feat: Nouvelle fonctionnalité"
git push origin master

# → GitHub Actions déploie automatiquement ! 🎉
```

### **Déploiement manuel sur le VPS (si besoin)**

```bash
# Connexion SSH
ssh cloudwaste@155.117.43.17

# Déploiement en une commande
cd /opt/cloudwaste && bash deployment/quick-deploy.sh
```

**C'est tout !** ✨ Le script gère automatiquement :
- ✅ Récupération du code depuis GitHub
- ✅ Rebuild des images Docker
- ✅ Redémarrage des services
- ✅ Tests de santé
- ✅ Rapport de déploiement

---

## 📚 Configuration Initiale (Une Seule Fois)

### **1. Configuration GitHub Actions (Déploiement Automatique)**

Suivez le guide complet : [`GITHUB_ACTIONS_SETUP.md`](./GITHUB_ACTIONS_SETUP.md)

**Résumé rapide** :
1. Générer une clé SSH pour GitHub Actions
2. Ajouter la clé publique sur le VPS
3. Configurer 3 secrets dans GitHub (VPS_SSH_PRIVATE_KEY, VPS_HOST, VPS_USER)
4. Pousser le code → déploiement automatique !

### **2. Configuration des Credentials Azure (Sur le VPS)**

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash deployment/configure-azure-credentials.sh
```

Le script vous guidera interactivement pour :
- ✅ Ajouter vos credentials Azure au fichier `.env`
- ✅ Valider le format des credentials
- ✅ Redémarrer les services automatiquement

### **3. Tester la connexion Azure**

```bash
bash deployment/test-azure-connection.sh
```

Ce script vérifie :
- ✅ Credentials présents dans `.env`
- ✅ Connectivité réseau vers Azure API
- ✅ Authentification réussie avec Azure

---

## 🔧 Commandes Utiles

### **Développement Local**

```bash
bash dev-start.sh              # Démarrer l'environnement
bash dev-stop.sh               # Arrêter l'environnement
bash dev-logs.sh backend       # Voir les logs d'un service
bash dev-logs.sh               # Voir tous les logs (mode suivi)
```

### **Production (VPS)**

```bash
# Déploiement rapide
bash deployment/quick-deploy.sh

# Déploiement de services spécifiques
bash deployment/quick-deploy.sh --services backend,celery_worker

# Déploiement sans rebuild (plus rapide)
bash deployment/quick-deploy.sh --skip-build

# Configuration Azure
bash deployment/configure-azure-credentials.sh

# Test connexion Azure
bash deployment/test-azure-connection.sh

# Rebuild frontend uniquement
bash deployment/rebuild-frontend.sh

# Diagnostic de problèmes
bash deployment/diagnose-issues.sh

# Correction automatique de problèmes connus
bash deployment/fix-issues.sh
```

---

## 🔄 Workflow Complet Détaillé

### **Étape 1 : Développement Local**

```bash
cd /Users/jerome_laval/Desktop/CloudWaste

# Démarrer l'environnement
bash dev-start.sh

# Développer votre code
# - backend/ : Python/FastAPI
# - frontend/ : Next.js/React
# - Hot-reload automatique des deux côtés

# Tester localement
# → http://localhost:3000 (Frontend)
# → http://localhost:8000 (Backend)
# → http://localhost:8000/docs (API Docs)

# Voir les logs si nécessaire
bash dev-logs.sh backend
bash dev-logs.sh frontend
```

### **Étape 2 : Commit et Push**

```bash
# Ajouter les fichiers modifiés
git add .

# Committer avec un message clair
git commit -m "feat: Description de la fonctionnalité"
# Ou: fix:, docs:, refactor:, etc.

# Pousser vers GitHub
git push origin master
```

### **Étape 3 : Déploiement Automatique (GitHub Actions)**

Une fois que vous faites `git push origin master` :

1. **GitHub Actions se déclenche automatiquement**
2. **Connexion SSH au VPS** avec la clé configurée
3. **Récupération du code** : `git pull origin master`
4. **Déploiement** : Exécute `deployment/quick-deploy.sh`
5. **Tests de santé** : Vérifie que l'application fonctionne
6. **Notification** : ✅ Succès ou ❌ Échec dans l'onglet Actions

**Suivi du déploiement** :
- Allez sur GitHub → Onglet `Actions`
- Cliquez sur le workflow en cours
- Voir les logs en temps réel

### **Étape 4 : Vérification**

```bash
# Tester l'application en production
open https://cutcosts.tech

# Vérifier l'API
open https://cutcosts.tech/api/docs

# Surveiller les logs (optionnel)
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
docker compose -f docker-compose.production.yml logs -f --tail=50
```

---

## 🎯 Workflow Détaillé

### Étape 1 : Développement Local

```bash
# Travailler sur votre Mac
cd /Users/jerome_laval/Desktop/CloudWaste

# Modifier le code (backend, frontend, etc.)
# Tester en local :
docker compose up -d
# Accéder à http://localhost:3000
```

### Étape 2 : Commit et Push

```bash
# Ajouter les fichiers modifiés
git add .

# Committer avec un message clair
git commit -m "feat: Ajout de la fonctionnalité X"

# Pousser sur GitHub
git push origin master
```

### Étape 3 : Déploiement sur le VPS

**Option A : Déploiement Rapide (rebuild uniquement si nécessaire)**

```bash
ssh cloudwaste@155.117.43.17

cd /opt/cloudwaste

# Récupérer les dernières modifications
git pull origin master

# Redémarrer les services (si pas de changement de dépendances)
docker compose -f docker-compose.production.yml restart

# OU rebuild complet (si modifications de dépendances)
docker compose -f docker-compose.production.yml up -d --build
```

**Option B : Utiliser le Script de Déploiement**

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash deployment/deploy.sh
```

---

## 🛠️ Commandes Utiles

### Voir les Logs en Temps Réel

```bash
# Tous les services
docker compose -f docker-compose.production.yml logs -f

# Backend uniquement
docker compose -f docker-compose.production.yml logs -f backend

# Frontend uniquement
docker compose -f docker-compose.production.yml logs -f frontend
```

### Redémarrer un Service Spécifique

```bash
# Redémarrer le backend
docker compose -f docker-compose.production.yml restart backend

# Redémarrer le frontend
docker compose -f docker-compose.production.yml restart frontend
```

### Vérifier l'État des Services

```bash
docker compose -f docker-compose.production.yml ps
```

### Migrations de Base de Données

```bash
# Si vous avez ajouté des modèles ou modifié la DB
docker compose -f docker-compose.production.yml exec backend alembic upgrade head
```

---

## 📦 Types de Modifications et Actions Nécessaires

| Modification | Action Nécessaire | Commande |
|--------------|-------------------|----------|
| **Code Frontend** (composants, pages) | Rebuild frontend | `docker compose -f docker-compose.production.yml up -d --build frontend` |
| **Code Backend** (routes, services) | Restart backend | `docker compose -f docker-compose.production.yml restart backend` |
| **Dépendances** (package.json, requirements.txt) | Rebuild complet | `docker compose -f docker-compose.production.yml up -d --build` |
| **Modèles DB** (nouveaux champs, tables) | Migration + restart | `alembic upgrade head` puis restart |
| **Variables .env** | Restart services | `docker compose -f docker-compose.production.yml restart` |
| **Configuration Nginx** | Reload nginx | `sudo systemctl reload nginx` |

---

## 🔥 Déploiement Automatique (Futur - GitHub Actions)

**Pour activer le déploiement automatique :**

1. Générer une clé SSH sur votre Mac :
```bash
ssh-keygen -t rsa -b 4096 -f ~/.ssh/cloudwaste_deploy
```

2. Ajouter la clé publique au VPS :
```bash
ssh-copy-id -i ~/.ssh/cloudwaste_deploy.pub cloudwaste@155.117.43.17
```

3. Dans GitHub (Settings → Secrets and variables → Actions), ajouter :
   - `VPS_SSH_KEY` : Contenu de `~/.ssh/cloudwaste_deploy` (clé PRIVÉE)
   - `VPS_HOST` : `155.117.43.17`
   - `VPS_USER` : `cloudwaste`

4. Le workflow `.github/workflows/deploy-production.yml` déploiera automatiquement à chaque push sur `master`.

---

## 🆘 Problèmes Courants

### 🔒 Site affiché comme "Non sécurisé"

**Symptôme**: Le navigateur affiche "Non sécurisé" sur https://cutcosts.tech

**Solution Rapide** : Utilisez `www.cutcosts.tech` au lieu de `cutcosts.tech`.

**Correction Définitive** :

Si `www.cutcosts.tech` fonctionne mais pas `cutcosts.tech`, le certificat SSL ne couvre probablement pas le domaine sans "www".

```bash
# Sur le VPS
ssh cloudwaste@155.117.43.17

# Vérifier les certificats
sudo certbot certificates

# Si cutcosts.tech n'apparaît pas dans les domaines, étendre le certificat
sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech --expand

# Suivre les instructions et accepter de remplacer le certificat existant
```

**OU** Utilisez le script de correction :
```bash
cd /opt/cloudwaste
git pull origin master
bash deployment/fix-ssl-and-docs.sh
```

**Causes possibles**:
- Certificat SSL ne couvre que `www.cutcosts.tech` et pas `cutcosts.tech`
- Configuration Nginx incorrecte
- Redirection HTTP → HTTPS manquante

### 🐳 Portainer: "Connexion non privée" (ERR_CERT_AUTHORITY_INVALID)

**C'est NORMAL !** Portainer utilise un certificat auto-signé.

**Solution**: 
1. Allez sur https://cutcosts.tech:9443
2. Cliquez sur **"Avancé"** ou **"Paramètres avancés"**
3. Cliquez sur **"Continuer vers le site"** ou **"Accéder au site"**
4. Créez votre compte admin

### 📊 Netdata: Redirection automatique vers HTTPS (HSTS)

**Le problème**: Le navigateur redirige automatiquement `http://cutcosts.tech:19999` vers HTTPS à cause du header HSTS.

**Solution 1** (Recommandée): Utilisez Nginx comme proxy :
👉 **https://cutcosts.tech/netdata**

**Solution 2** (Alternative): Accédez via l'IP directement :
👉 **http://155.117.43.17:19999**

**Pour activer le proxy Nginx** (si pas déjà fait):
```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
git pull origin master
bash deployment/fix-issues.sh
```

### 📚 API Docs retourne 404 ou "Not Found"

**Le problème**: FastAPI expose les docs à `/api/docs`, pas à `/docs` ou `/api/v1/docs`.

**✅ Bonnes URLs** :
- Swagger UI : `https://cutcosts.tech/api/docs`
- ReDoc : `https://cutcosts.tech/api/redoc`
- OpenAPI JSON : `https://cutcosts.tech/api/openapi.json`

**Vérification** : Les docs devraient fonctionner immédiatement car Nginx redirige déjà `/api/*` vers le backend.

**Si les docs ne fonctionnent toujours pas** :
```bash
# Sur le VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# Tester directement le backend
curl http://localhost:8000/api/docs

# Vérifier que le backend fonctionne
docker compose -f docker-compose.production.yml logs backend --tail=50

# Redémarrer le backend si nécessaire
docker compose -f docker-compose.production.yml restart backend
```

---

### 🎨 Frontend retourne 500 avec "Module parse failed: Unexpected character '@'"

**Le problème**: Le `Dockerfile.production` installait seulement les production dependencies, excluant Tailwind CSS (devDependency nécessaire pour le build).

**Symptômes** :
```
Module parse failed: Unexpected character '@' (1:0)
> @tailwind base;
| @tailwind components;
| @tailwind utilities;
```

**Solution automatique** :
```bash
# Sur le VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# Récupérer le correctif
git pull origin master

# Rebuilder le frontend (prend 2-3 minutes)
bash deployment/rebuild-frontend.sh
```

**Ce qui est corrigé** :
- ✅ Installation de **TOUTES** les dépendances (y compris devDependencies)
- ✅ Tailwind CSS, PostCSS et Autoprefixer installés pour le build
- ✅ Build Next.js en mode production avec output standalone
- ✅ Image optimisée avec seulement les fichiers nécessaires à l'exécution

**Vérification manuelle** :
```bash
# Vérifier que le frontend est en mode production
docker compose -f docker-compose.production.yml logs frontend --tail=30

# Vous devriez voir "Ready in X.Xs" sans erreur Tailwind
# Et le buildId devrait être un hash, pas "development"
```

---

### ☁️ Les Scans Azure ne trouvent aucune ressource (0 ressources)

**Le problème** : Les scans Azure retournent "completed" avec 0 ressources alors que des ressources existent réellement.

**Symptômes dans les logs** :
```
Failed to resolve 'login.microsoftonline.com' ([Errno -3] Temporary failure in name resolution)
ClientSecretCredential.get_token failed: Authentication failed
```

**Causes racines** :
1. ❌ Credentials Azure vides ou manquants dans `.env`
2. ❌ Réseau Docker `backend_network` configuré avec `internal: true` (bloque Internet)

**Solution complète** :

```bash
# 1. Connexion au VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# 2. Récupérer les correctifs (correction réseau Docker)
git pull origin master

# 3. Configurer les credentials Azure (script interactif)
bash deployment/configure-azure-credentials.sh
# → Suivre les instructions pour ajouter AZURE_TENANT_ID, AZURE_CLIENT_ID, etc.

# 4. Tester la connexion Azure
bash deployment/test-azure-connection.sh
# → Vérifie que tout fonctionne (DNS, credentials, authentification)

# 5. Redéployer avec la nouvelle configuration réseau
bash deployment/quick-deploy.sh
```

**Ce qui est corrigé** :
- ✅ Retrait de `internal: true` du réseau Docker (permet l'accès à Internet)
- ✅ Sécurité maintenue (pas d'exposition publique des ports)
- ✅ Celery workers peuvent accéder aux API Azure/AWS
- ✅ Credentials Azure configurés et validés

**Vérification** :
```bash
# Vérifier que les workers Celery peuvent accéder à Internet
docker compose -f docker-compose.production.yml exec celery_worker curl -s https://login.microsoftonline.com

# Vérifier les credentials dans le conteneur
docker compose -f docker-compose.production.yml exec backend env | grep AZURE

# Lancer un nouveau scan depuis l'interface web
# → https://cutcosts.tech
```

**Où trouver les credentials Azure ?**

1. Allez sur [Azure Portal](https://portal.azure.com)
2. `Azure Active Directory` → `App registrations` → Créer ou sélectionner une app
3. Notez :
   - **AZURE_TENANT_ID** : Directory (tenant) ID
   - **AZURE_CLIENT_ID** : Application (client) ID
   - **AZURE_SUBSCRIPTION_ID** : ID de votre subscription
4. `Certificates & secrets` → `Client secrets` → Créer un nouveau secret
   - **AZURE_CLIENT_SECRET** : Valeur du secret (copiez immédiatement !)
5. Attribuez le rôle **Reader** à l'application sur votre subscription

---

### Le site ne se met pas à jour

```bash
# Vérifier que les modifications sont bien sur le VPS
cd /opt/cloudwaste
git log --oneline -5

# Forcer un rebuild complet
docker compose -f docker-compose.production.yml down
docker compose -f docker-compose.production.yml up -d --build
```

### Erreur 502 Bad Gateway

```bash
# Le backend a probablement crashé
docker compose -f docker-compose.production.yml logs backend --tail=50
docker compose -f docker-compose.production.yml restart backend
```

### Base de données corrompue

```bash
# Restaurer depuis un backup
cd /opt/cloudwaste
ls -lh backups/
bash deployment/restore.sh backups/[fichier-backup].tar.gz
```

### 💾 Vérifier les Backups

```bash
ssh cloudwaste@155.117.43.17

# Vérifier le cron job
cat /etc/cron.d/cloudwaste-backup

# Voir les backups existants
ls -lh /opt/cloudwaste/backups/

# Voir les logs de backup
tail -50 /var/log/cloudwaste-backup.log

# Tester un backup manuel
cd /opt/cloudwaste
bash deployment/backup.sh
```

---

## 📊 Monitoring et Outils de Gestion

### **Portainer** (Gestion Docker)
**URL** : https://cutcosts.tech:9443

**⚠️ IMPORTANT - Premier Accès** :
1. Le navigateur affichera "Connexion non privée" → **C'est normal**
2. Cliquez sur **"Avancé"** puis **"Continuer vers le site"**
3. **Créez votre compte admin dans les 5 minutes** sinon timeout
4. Si message "timed out" : 
   ```bash
   ssh cloudwaste@155.117.43.17
   docker restart portainer
   ```
   Puis reconnectez-vous **immédiatement**

### **Netdata** (Monitoring Système)
**URL** : **https://cutcosts.tech/netdata** *(via Nginx reverse proxy)*

**💡 ASTUCE** :
- ✅ Recommandé : `https://cutcosts.tech/netdata` (sécurisé via Nginx)
- ✅ Alternative : `http://155.117.43.17:19999` (accès direct via IP)
- ❌ Ne fonctionne pas : `http://cutcosts.tech:19999` (redirigé vers HTTPS par HSTS)

Netdata est accessible via Nginx en HTTPS pour éviter les problèmes de HSTS du navigateur.

### **API Documentation**

FastAPI expose automatiquement la documentation à plusieurs URLs :

- **Swagger UI** : https://cutcosts.tech/api/docs *(interface interactive)*
- **ReDoc** : https://cutcosts.tech/api/redoc *(documentation alternative)*
- **OpenAPI JSON** : https://cutcosts.tech/api/openapi.json *(schéma brut)*

⚠️ **Note** : Les docs sont à `/api/docs` et `/api/redoc` (configuré dans `backend/app/main.py`).

### **Logs en Temps Réel**
```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# Tous les services
docker compose -f docker-compose.production.yml logs -f

# Service spécifique
docker compose -f docker-compose.production.yml logs -f backend
```

---

## 💾 Backups

Les backups automatiques s'exécutent **tous les jours à 2h du matin**.

**Backup manuel :**
```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash deployment/backup.sh
```

**Restaurer un backup :**
```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
ls backups/
bash deployment/restore.sh backups/cloudwaste-backup-YYYYMMDD-HHMMSS.tar.gz
```

---

## 🎯 Résumé : Workflow Quotidien

```bash
# Sur votre Mac
cd /Users/jerome_laval/Desktop/CloudWaste
# ... modifier le code ...
git add .
git commit -m "Votre message"
git push origin master

# Sur le VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
git pull origin master
docker compose -f docker-compose.production.yml up -d --build
```

**C'est tout ! 🎉**

