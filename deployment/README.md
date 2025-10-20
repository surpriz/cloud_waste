# Deployment Scripts

Ce dossier contient tous les scripts et fichiers de configuration pour déployer CloudWaste en production sur votre VPS.

## 📁 Contenu

- **setup-vps.sh** - Script d'initialisation et de sécurisation du VPS
- **deploy.sh** - Script de déploiement/mise à jour de l'application
- **backup.sh** - Script de backup automatisé
- **restore.sh** - Script de restauration depuis un backup
- **docker-compose.production.yml** - Configuration Docker pour la production
- **env.production.template** - Template des variables d'environnement
- **nginx/** - Configuration Nginx pour le reverse proxy

## 🚀 Installation Initiale

### 1. Préparer le VPS (première fois uniquement)

```bash
# Sur votre machine locale
cd /Users/jerome_laval/Desktop/CloudWaste
chmod +x deployment/setup-vps.sh

# Copier le script sur le VPS
scp deployment/setup-vps.sh root@155.117.43.17:/root/

# Se connecter au VPS et exécuter le script
ssh root@155.117.43.17
bash /root/setup-vps.sh
```

Ce script va:
- Créer l'utilisateur `cloudwaste` avec sudo
- Configurer les clés SSH
- Installer Docker, Nginx, Certbot, Portainer, Ollama, Netdata
- Configurer le firewall (UFW) et Fail2Ban
- Créer la structure de répertoires

### 2. Configurer le DNS

Avant de continuer, configurer les enregistrements DNS:
```
Type: A
Nom: @
Valeur: 155.117.43.17

Type: A
Nom: www
Valeur: 155.117.43.17
```

### 3. Déployer l'application

```bash
# Se connecter avec le nouvel utilisateur
ssh cloudwaste@155.117.43.17

# Cloner le repository
cd /opt/cloudwaste
git clone https://github.com/VOTRE_USERNAME/CloudWaste.git .

# Copier et configurer docker-compose
cp deployment/docker-compose.production.yml docker-compose.production.yml

# Créer le fichier .env depuis le template
nano .env
# Copier le contenu de deployment/env.production.template et remplir les valeurs

# Créer/copier la clé de chiffrement
nano encryption_key
# Coller le contenu de votre encryption_key local

# Rendre les scripts exécutables
chmod +x deployment/*.sh

# Copier les scripts à la racine pour faciliter l'accès
cp deployment/deploy.sh deploy.sh
cp deployment/backup.sh backup.sh
cp deployment/restore.sh restore.sh

# Configurer Nginx
sudo cp deployment/nginx/cutcosts.tech.conf /etc/nginx/sites-available/cutcosts.tech
sudo ln -s /etc/nginx/sites-available/cutcosts.tech /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx

# Obtenir le certificat SSL
sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech

# Premier déploiement
bash deploy.sh
```

## 🔄 Déploiement et Mises à Jour

### Déploiement automatique (recommandé)

Le déploiement se fait automatiquement via GitHub Actions lors d'un push sur `main`.

**Configuration requise dans GitHub:**
1. Aller dans Settings → Secrets and variables → Actions
2. Ajouter les secrets:
   - `VPS_SSH_KEY`: Contenu de `~/.ssh/cloudwaste_vps_rsa` (clé privée)
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

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash deploy.sh
```

Le script effectue:
1. Backup pré-déploiement
2. Git pull des dernières modifications
3. Build des images Docker
4. Migrations de base de données
5. Redémarrage des services avec zero-downtime
6. Vérification du déploiement

## 💾 Backup et Restauration

### Backup manuel

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste
bash backup.sh
```

Les backups sont stockés dans `/opt/cloudwaste/backups/` et conservés 7 jours.

### Backup automatique

Un cron job exécute automatiquement le backup tous les jours à 2h du matin.

### Restaurer un backup

```bash
ssh cloudwaste@155.117.43.17
cd /opt/cloudwaste

# Lister les backups disponibles
ls -lh backups/

# Restaurer un backup spécifique
bash restore.sh backups/cloudwaste-backup-20250120-020000.tar.gz
```

## 🔧 Commandes Utiles

### Gestion des services

```bash
cd /opt/cloudwaste

# Voir l'état des conteneurs
docker compose -f docker-compose.production.yml ps

# Voir les logs
docker compose -f docker-compose.production.yml logs -f
docker compose -f docker-compose.production.yml logs -f backend

# Redémarrer un service
docker compose -f docker-compose.production.yml restart backend

# Redémarrer tous les services
docker compose -f docker-compose.production.yml restart

# Arrêter tous les services
docker compose -f docker-compose.production.yml down

# Démarrer tous les services
docker compose -f docker-compose.production.yml up -d
```

### Base de données

```bash
# Accéder à PostgreSQL
docker compose -f docker-compose.production.yml exec postgres psql -U cloudwaste -d cloudwaste

# Exécuter une migration
docker compose -f docker-compose.production.yml exec backend alembic upgrade head

# Créer une nouvelle migration
docker compose -f docker-compose.production.yml exec backend alembic revision --autogenerate -m "Description"
```

### Nginx

```bash
# Vérifier la configuration
sudo nginx -t

# Recharger Nginx
sudo systemctl reload nginx

# Voir les logs
sudo tail -f /var/log/nginx/cutcosts.tech.access.log
sudo tail -f /var/log/nginx/cutcosts.tech.error.log
```

### SSL/TLS

```bash
# Renouveler les certificats
sudo certbot renew

# Tester le renouvellement
sudo certbot renew --dry-run
```

### Monitoring

```bash
# Netdata: https://cutcosts.tech/netdata
# Portainer: https://cutcosts.tech:9443

# Espace disque
df -h

# Utilisation mémoire
free -h

# Processus
htop
```

## 🔒 Sécurité

### Vérifier les tentatives de connexion SSH

```bash
sudo fail2ban-client status sshd
sudo last -a
```

### Firewall

```bash
# État du firewall
sudo ufw status verbose

# Ajouter une règle
sudo ufw allow 8080/tcp

# Supprimer une règle
sudo ufw delete allow 8080/tcp
```

## 🆘 Dépannage

### Le site ne répond pas

```bash
# Vérifier Nginx
sudo systemctl status nginx
sudo nginx -t

# Vérifier les conteneurs
docker ps

# Vérifier les logs
docker compose -f docker-compose.production.yml logs backend
```

### Erreurs 502 Bad Gateway

```bash
# Le backend ne répond probablement pas
docker compose -f docker-compose.production.yml logs backend
docker compose -f docker-compose.production.yml restart backend
```

### Base de données corrompue

```bash
# Restaurer depuis le dernier backup
bash restore.sh backups/[dernier-backup].tar.gz
```

### Espace disque plein

```bash
# Nettoyer Docker
docker system prune -a

# Supprimer les vieux backups
rm backups/cloudwaste-backup-*.tar.gz
```

## 📊 Structure des Fichiers sur le VPS

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
├── deployment/                       # Scripts de déploiement
├── backups/                          # Backups locaux
└── data/                             # Volumes Docker
```

## 🌐 Accès aux Services

- **Site principal**: https://cutcosts.tech
- **API**: https://cutcosts.tech/api/v1
- **API Docs**: https://cutcosts.tech/api/v1/docs
- **Portainer**: https://cutcosts.tech:9443
- **Netdata**: https://cutcosts.tech/netdata

## 📝 Notes

- Les backups sont conservés pendant 7 jours (configurable dans backup.sh)
- Les logs Docker sont limités à 10MB x 3 fichiers par conteneur
- Le firewall autorise uniquement les ports 22, 80, 443, et 9443
- Les mises à jour de sécurité sont automatiques
- Fail2Ban protège contre les attaques SSH brute-force

## 📖 Documentation Complète

Pour plus de détails, consultez le fichier `VPS_PRODUCTION_GUIDE.md` à la racine du projet.

