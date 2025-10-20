# Guide de Production VPS CloudWaste

## 📋 Informations du Serveur

- **IP**: 155.117.43.17
- **Domaine**: cutcosts.tech
- **OS**: Ubuntu (Linux)
- **Utilisateur principal**: cloudwaste (avec sudo)
- **Répertoire de déploiement**: `/opt/cloudwaste/`

## 🔐 Accès SSH

### Première connexion (root)
```bash
ssh root@155.117.43.17
```

### Après configuration (utilisateur cloudwaste)
```bash
ssh cloudwaste@155.117.43.17
# ou avec clé SSH
ssh -i ~/.ssh/cloudwaste_vps_rsa cloudwaste@155.117.43.17
```

## 🚀 Installation Initiale

### 1. Préparer le script sur votre machine locale
```bash
cd /Users/jerome_laval/Desktop/CloudWaste
chmod +x deployment/setup-vps.sh
```

### 2. Copier le script sur le VPS

**Option A: Avec accès root**
```bash
scp deployment/setup-vps.sh root@155.117.43.17:/root/
```

**Option B: Avec utilisateur admin (ex: administrator)**
```bash
scp deployment/setup-vps.sh administrator@155.117.43.17:~/
```

> **Note**: La plupart des providers donnent un utilisateur admin avec sudo plutôt que root direct. C'est une bonne pratique de sécurité.

### 3. Se connecter au VPS et exécuter le script

**Option A: Avec accès root**
```bash
ssh root@155.117.43.17
bash /root/setup-vps.sh
```

**Option B: Avec utilisateur admin**
```bash
ssh administrator@155.117.43.17
sudo bash ~/setup-vps.sh
```

> 📘 **Voir aussi**: `deployment/SETUP_WITH_ADMIN_USER.md` pour un guide détaillé si vous n'avez pas d'accès root direct.

Le script va:
- ✅ Créer l'utilisateur `cloudwaste` avec sudo
- ✅ Configurer les clés SSH
- ✅ Installer Docker, Docker Compose, Nginx, Certbot, Fail2Ban
- ✅ Configurer le firewall (UFW)
- ✅ Installer Portainer sur le port 9443
- ✅ Installer Ollama
- ✅ Installer Netdata pour le monitoring
- ✅ Créer la structure de répertoires
- ✅ Configurer les backups automatiques

### 4. Configurer le DNS

**Avant de continuer, configurez votre DNS:**
```
Type: A
Nom: @
Valeur: 155.117.43.17
TTL: 300

Type: A
Nom: www
Valeur: 155.117.43.17
TTL: 300
```

Attendez la propagation DNS (quelques minutes à quelques heures).

### 5. Premier déploiement

```bash
# Se connecter avec le nouvel utilisateur
ssh cloudwaste@155.117.43.17

# Cloner le repository
cd /opt/cloudwaste
git clone https://github.com/VOTRE_USERNAME/CloudWaste.git .

# Créer le fichier .env
nano .env
# Coller le contenu de .env.production (voir section Variables d'environnement)

# Créer/copier la clé de chiffrement
nano encryption_key
# Coller votre clé de chiffrement

# Lancer le déploiement
bash deploy.sh
```

### 6. Configurer SSL avec Let's Encrypt

```bash
sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech
# Suivre les instructions (email, accepter les conditions)
```

### 7. Vérifications post-installation

```bash
# Vérifier que les services sont actifs
docker ps

# Vérifier les logs
docker compose logs -f

# Tester l'API
curl https://cutcosts.tech/api/v1/health

# Accéder à Portainer
# Ouvrir https://cutcosts.tech:9443

# Accéder au monitoring Netdata
# Ouvrir https://cutcosts.tech/netdata
```

## 🏗️ Architecture Déployée

```
┌─────────────────────────────────────────────────────────┐
│                    Internet (Port 80/443)                │
└──────────────────────┬──────────────────────────────────┘
                       │
                   ┌───▼────┐
                   │ Nginx  │ (Reverse Proxy + SSL)
                   └───┬────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
    ┌───▼────┐    ┌───▼────┐    ┌───▼────┐
    │Frontend│    │Backend │    │Netdata │
    │(Next.js)│    │(FastAPI)│    │Monitor │
    │  :3000 │    │  :8000 │    │  :19999│
    └───┬────┘    └───┬────┘    └────────┘
        │             │
        │         ┌───▼────────────────┐
        │         │  Celery Workers    │
        │         │  (Beat + Worker)   │
        │         └───┬────────────────┘
        │             │
        └─────────────┼─────────────┐
                      │             │
                  ┌───▼───┐    ┌───▼───┐
                  │Postgres│    │ Redis │
                  │  :5432 │    │ :6379 │
                  └────────┘    └───────┘
```

## 📁 Structure des Fichiers sur le VPS

```
/opt/cloudwaste/
├── .env                              # Variables d'environnement
├── .git/                             # Repository Git
├── docker-compose.production.yml     # Configuration Docker
├── encryption_key                    # Clé de chiffrement
├── deploy.sh                         # Script de déploiement
├── backup.sh                         # Script de backup
├── restore.sh                        # Script de restauration
├── backend/                          # Code backend
├── frontend/                         # Code frontend
├── backups/                          # Backups locaux
│   ├── cloudwaste-backup-YYYYMMDD-HHMMSS.tar.gz
│   └── ...
└── data/                             # Volumes Docker (géré par Docker)
```

## 🔑 Variables d'Environnement

### Fichier .env de production

Créer `/opt/cloudwaste/.env` avec le contenu suivant (remplacer les valeurs):

```bash
# Application
APP_NAME=CloudWaste
APP_ENV=production
DEBUG=false
SECRET_KEY=GENERER_UNE_CLE_SECRETE_LONGUE_ET_ALEATOIRE
API_V1_PREFIX=/api/v1

# Security
ENCRYPTION_KEY=VOTRE_CLE_DE_CHIFFREMENT_EXISTANTE
JWT_SECRET_KEY=GENERER_UNE_AUTRE_CLE_SECRETE_JWT
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
REFRESH_TOKEN_REMEMBER_ME_EXPIRE_DAYS=30

# Database
DATABASE_URL=postgresql+asyncpg://cloudwaste:MOT_DE_PASSE_SECURISE_DB@postgres:5432/cloudwaste

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# CORS
ALLOWED_ORIGINS=https://cutcosts.tech,https://www.cutcosts.tech

# Email (optionnel)
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
EMAILS_FROM_EMAIL=
EMAILS_FROM_NAME=CloudWaste

# AWS (pour les scans)
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_DEFAULT_REGION=eu-west-1

# Azure (pour les scans)
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=
AZURE_TENANT_ID=

# AI Assistant
ANTHROPIC_API_KEY=VOTRE_CLE_ANTHROPIC
CHAT_MAX_MESSAGES_PER_USER_PER_DAY=50
CHAT_CONTEXT_MAX_RESOURCES=20
CHAT_MODEL=claude-haiku-4-5-20250818

# Frontend
NEXT_PUBLIC_API_URL=https://cutcosts.tech
NEXT_PUBLIC_APP_NAME=CloudWaste

# PostgreSQL (pour docker-compose)
POSTGRES_USER=cloudwaste
POSTGRES_PASSWORD=MOT_DE_PASSE_SECURISE_DB
POSTGRES_DB=cloudwaste
```

### Générer des clés sécurisées

```bash
# Pour SECRET_KEY et JWT_SECRET_KEY
openssl rand -hex 32

# Pour le mot de passe PostgreSQL
openssl rand -base64 32
```

## 🔄 Déploiement et Mises à Jour

### Déploiement automatique via GitHub Actions

Le déploiement se fait automatiquement lors d'un push sur la branche `main`.

**Configuration requise dans GitHub:**
1. Aller dans Settings → Secrets and variables → Actions
2. Ajouter les secrets:
   - `VPS_SSH_KEY`: Contenu de la clé privée SSH (`~/.ssh/cloudwaste_vps_rsa`)
   - `VPS_HOST`: 155.117.43.17
   - `VPS_USER`: cloudwaste

**Workflow:**
```bash
git add .
git commit -m "Nouvelle fonctionnalité"
git push origin main
# Le déploiement se lance automatiquement
```

### Déploiement manuel

Si vous préférez déployer manuellement:

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash deploy.sh
```

Le script `deploy.sh` effectue:
1. Git pull des dernières modifications
2. Rebuild des images Docker
3. Migrations de base de données
4. Redémarrage des services avec zero-downtime

## 🔧 Commandes de Maintenance

### Gestion des conteneurs

```bash
# Se connecter au VPS
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# Voir l'état des conteneurs
docker ps

# Voir les logs
docker compose logs -f
docker compose logs -f backend
docker compose logs -f celery_worker

# Redémarrer un service
docker compose restart backend

# Redémarrer tous les services
docker compose restart

# Arrêter tous les services
docker compose down

# Démarrer tous les services
docker compose up -d

# Rebuild et redémarrer
docker compose up -d --build
```

### Base de données

```bash
# Accéder à PostgreSQL
docker compose exec postgres psql -U cloudwaste -d cloudwaste

# Exécuter une migration
docker compose exec backend alembic upgrade head

# Revenir à une migration précédente
docker compose exec backend alembic downgrade -1

# Créer une nouvelle migration
docker compose exec backend alembic revision --autogenerate -m "Description"
```

### Backups

```bash
# Backup manuel
/opt/cloudwaste/backup.sh

# Lister les backups
ls -lh /opt/cloudwaste/backups/

# Restaurer un backup
/opt/cloudwaste/restore.sh /opt/cloudwaste/backups/cloudwaste-backup-20250120-020000.tar.gz

# Voir les logs du cron de backup
sudo journalctl -u cron | grep backup
```

### Monitoring et logs

```bash
# Netdata (monitoring système)
# Accéder via: https://cutcosts.tech/netdata

# Portainer (gestion Docker)
# Accéder via: https://cutcosts.tech:9443

# Voir l'utilisation disque
df -h

# Voir l'utilisation mémoire
free -h

# Voir les processus
top
htop

# Logs Nginx
sudo tail -f /var/log/nginx/cutcosts.tech.access.log
sudo tail -f /var/log/nginx/cutcosts.tech.error.log

# Logs système
sudo journalctl -f
```

### SSL/TLS

```bash
# Renouveler manuellement les certificats
sudo certbot renew

# Tester le renouvellement automatique
sudo certbot renew --dry-run

# Vérifier la configuration Nginx
sudo nginx -t

# Recharger Nginx
sudo systemctl reload nginx
```

### Firewall

```bash
# Voir l'état du firewall
sudo ufw status verbose

# Ajouter une règle
sudo ufw allow 8080/tcp

# Supprimer une règle
sudo ufw delete allow 8080/tcp

# Voir les tentatives bloquées par Fail2Ban
sudo fail2ban-client status sshd
```

## 🆘 Dépannage

### Le site ne répond pas

```bash
# Vérifier que Nginx fonctionne
sudo systemctl status nginx
sudo nginx -t

# Vérifier que les conteneurs tournent
docker ps

# Vérifier les logs
docker compose logs -f backend
```

### Erreurs 502 Bad Gateway

```bash
# Le backend ne répond probablement pas
docker compose logs backend

# Redémarrer le backend
docker compose restart backend
```

### Base de données corrompue

```bash
# Restaurer depuis un backup
/opt/cloudwaste/restore.sh /opt/cloudwaste/backups/[dernier-backup].tar.gz
```

### Espace disque plein

```bash
# Nettoyer les images Docker non utilisées
docker system prune -a

# Nettoyer les logs Docker
sudo sh -c "truncate -s 0 /var/lib/docker/containers/*/*-json.log"

# Supprimer les vieux backups
rm /opt/cloudwaste/backups/cloudwaste-backup-*.tar.gz
```

### Celery workers ne fonctionnent pas

```bash
# Vérifier les logs
docker compose logs celery_worker
docker compose logs celery_beat

# Redémarrer
docker compose restart celery_worker celery_beat

# Vérifier Redis
docker compose exec redis redis-cli ping
```

## 🔒 Sécurité

### Bonnes pratiques

- ✅ Ne jamais se connecter en root (utiliser cloudwaste)
- ✅ Garder le système à jour: `sudo apt update && sudo apt upgrade`
- ✅ Sauvegarder régulièrement les fichiers .env et encryption_key
- ✅ Vérifier les logs de Fail2Ban: `sudo fail2ban-client status sshd`
- ✅ Surveiller les accès: `sudo last -a`
- ✅ Changer les mots de passe régulièrement

### Modifications du firewall

Si vous devez ouvrir d'autres ports:

```bash
sudo ufw allow PORT/tcp
sudo ufw reload
```

## 🌐 Déployer d'autres Applications

Pour déployer d'autres applications sur le même VPS:

1. Créer un nouveau répertoire: `/opt/autre-app/`
2. Créer un nouveau docker-compose.yml
3. Créer une nouvelle configuration Nginx: `/etc/nginx/sites-available/autre-app.conf`
4. Générer un certificat SSL pour le nouveau domaine
5. Utiliser des réseaux Docker isolés pour chaque application

Exemple de configuration Nginx pour une autre app:

```nginx
server {
    listen 80;
    server_name autre-app.com www.autre-app.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name autre-app.com www.autre-app.com;

    ssl_certificate /etc/letsencrypt/live/autre-app.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/autre-app.com/privkey.pem;

    location / {
        proxy_pass http://localhost:PORT;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## 📊 Performances et Optimisation

### Monitorer les performances

```bash
# CPU et mémoire
docker stats

# Espace disque
df -h

# Netdata: https://cutcosts.tech/netdata
```

### Optimiser PostgreSQL

Si la base de données devient lente:

```bash
# Analyser les requêtes lentes
docker compose exec postgres psql -U cloudwaste -d cloudwaste
# Dans psql:
SELECT * FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10;

# Vacuum et analyze
VACUUM ANALYZE;
```

## 🔗 Liens Utiles

- **Site principal**: https://cutcosts.tech
- **API**: https://cutcosts.tech/api/v1/docs
- **Portainer**: https://cutcosts.tech:9443
- **Netdata**: https://cutcosts.tech/netdata
- **Repository GitHub**: https://github.com/VOTRE_USERNAME/CloudWaste

## 📞 Support

En cas de problème, vérifier:
1. Les logs Docker: `docker compose logs -f`
2. Les logs Nginx: `sudo tail -f /var/log/nginx/error.log`
3. L'état des services: `docker ps`
4. Le monitoring Netdata
5. Ce guide de dépannage

---

**Dernière mise à jour**: 2025-01-20

