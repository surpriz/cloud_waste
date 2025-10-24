# 🚀 Workflow de Développement et Déploiement

## 🔄 Comment Mettre à Jour le Site en Production

### Workflow Simple (Recommandé)

```bash
# 1. Développez localement sur votre Mac
cd /Users/jerome_laval/Desktop/CloudWaste

# 2. Testez vos modifications en local
docker compose up

# 3. Une fois satisfait, committez et poussez
git add .
git commit -m "Description de vos modifications"
git push origin master

# 4. Déployez sur le VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
git pull origin master
docker compose -f docker-compose.production.yml up -d --build
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

