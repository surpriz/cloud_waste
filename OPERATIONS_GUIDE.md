# CloudWaste - Guide d'Opérations Production

Guide complet pour gérer votre serveur CloudWaste en production.

**Serveur:** cutcosts.tech (83.147.36.59)  
**Accès:** `ssh administrator@83.147.36.59`

---

## 🌐 URLs et Accès

| Service | URL | Utilisation |
|---------|-----|-------------|
| **Application principale** | https://cutcosts.tech | Interface web CloudWaste |
| **Documentation API** | https://cutcosts.tech/api/docs | Swagger UI - Tester l'API |
| **Health Check** | https://cutcosts.tech/api/v1/health | Vérifier si le backend fonctionne |
| **Portainer** | http://83.147.36.59:9000 | Gestion Docker via interface web |

---

## 🔌 Se Connecter au Serveur

```bash
# Depuis votre Mac
ssh administrator@83.147.36.59
```

---

## 📊 Monitoring et Status

### Monitoring Complet du Système

```bash
# Vérifier l'état complet du système
sudo cloudwaste-monitor.sh
```

**Affiche :**
- CPU, RAM, Disque
- Status de tous les conteneurs
- Health checks (Frontend, Backend, BDD, Redis)
- Validité SSL
- Erreurs récentes

### Vérifier les Conteneurs Docker

```bash
# Voir tous les conteneurs
cd /var/www/cloudwaste
docker compose ps

# Statistiques en temps réel (CPU, RAM par conteneur)
docker stats

# Vérifier un conteneur spécifique
docker ps | grep cloudwaste
```

### Vérifier les Logs

```bash
cd /var/www/cloudwaste

# TOUS les services en temps réel
docker compose logs -f

# Backend uniquement
docker compose logs -f backend

# Frontend uniquement  
docker compose logs -f frontend

# PostgreSQL
docker compose logs -f postgres

# Redis
docker compose logs -f redis

# Celery Worker (jobs background)
docker compose logs -f celery_worker

# Celery Beat (tâches planifiées)
docker compose logs -f celery_beat

# Dernières 50 lignes du backend
docker compose logs backend --tail 50

# Logs Nginx
tail -f /var/log/nginx/cutcosts.tech-access.log  # Accès
tail -f /var/log/nginx/cutcosts.tech-error.log   # Erreurs
```

### Vérifier l'Espace Disque

```bash
# Espace disque général
df -h

# Espace utilisé par Docker
docker system df

# Espace utilisé par CloudWaste
du -sh /var/www/cloudwaste
```

---

## 🔄 Gestion des Services CloudWaste

**Toujours depuis `/var/www/cloudwaste/` :**

```bash
cd /var/www/cloudwaste
```

### Redémarrer les Services

```bash
# Redémarrer TOUS les services
docker compose restart

# Redémarrer UN service spécifique
docker compose restart backend
docker compose restart frontend
docker compose restart celery_worker
docker compose restart postgres
docker compose restart redis
```

### Arrêter / Démarrer CloudWaste

```bash
# Arrêter TOUT CloudWaste
docker compose down

# Démarrer TOUT CloudWaste
docker compose up -d

# Démarrer en voyant les logs
docker compose up

# Arrêter un service spécifique
docker compose stop backend

# Démarrer un service spécifique
docker compose start backend
```

### Reconstruire une Image

```bash
# Si vous avez modifié le code backend
docker compose build backend --no-cache
docker compose up -d backend

# Si vous avez modifié le code frontend
docker compose build frontend --no-cache
docker compose up -d frontend

# Tout reconstruire (long !)
docker compose build --no-cache
docker compose up -d
```

---

## 💾 Base de Données PostgreSQL

### Se Connecter à PostgreSQL

```bash
# Depuis le serveur
docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste
```

### Commandes SQL Utiles

```sql
-- Lister toutes les tables
\dt

-- Voir les utilisateurs CloudWaste
SELECT id, email, full_name, created_at FROM users;

-- Voir les comptes cloud connectés
SELECT id, account_name, provider, is_active FROM cloud_accounts;

-- Voir les scans récents
SELECT id, status, orphan_resources_found, estimated_monthly_waste, created_at 
FROM scans 
ORDER BY created_at DESC 
LIMIT 10;

-- Voir les ressources orphelines détectées
SELECT resource_type, COUNT(*) as count, SUM(estimated_monthly_cost) as total_cost
FROM orphan_resources
WHERE status = 'active'
GROUP BY resource_type
ORDER BY total_cost DESC;

-- Quitter
\q
```

### Accès Distant (depuis votre Mac)

```bash
# Créer un tunnel SSH
ssh -L 5432:localhost:5433 administrator@83.147.36.59

# Puis dans un autre terminal, connectez-vous avec :
# Host: localhost
# Port: 5432
# User: cloudwaste
# Database: cloudwaste
# Password: (voir .env sur le serveur)
```

### Voir le Mot de Passe PostgreSQL

```bash
# Sur le serveur
cd /var/www/cloudwaste
grep POSTGRES_PASSWORD .env
```

---

## 💾 Backups

### Lancer un Backup Manuel

```bash
# Backup complet (BDD + configs)
sudo backup-cloudwaste.sh
```

**Ce qui est sauvegardé :**
- Base de données PostgreSQL (compressée)
- Fichier `.env`
- `docker-compose.yml`
- Configuration Nginx

### Voir les Backups Disponibles

```bash
# Lister les backups de base de données
sudo ls -lh /backups/cloudwaste/database/

# Lister les backups de configuration
sudo ls -lh /backups/cloudwaste/configs/
```

### Restaurer un Backup

```bash
# 1. Voir les backups disponibles
sudo ls -lh /backups/cloudwaste/database/

# 2. Restaurer (remplacer TIMESTAMP par la date du backup)
sudo restore-cloudwaste.sh TIMESTAMP

# Exemple :
sudo restore-cloudwaste.sh 20251020_054427
```

**⚠️ ATTENTION :** La restauration arrête CloudWaste et remplace toutes les données !

### Backups Automatiques

```bash
# Voir les tâches planifiées
sudo crontab -l

# Voir les logs de backup
tail -f /var/log/cloudwaste-backup.log
```

**Par défaut :** Backup quotidien à 2h00 du matin, rétention 7 jours.

---

## 🗄️ Redis (Cache)

### Se Connecter à Redis

```bash
# Ouvrir le CLI Redis
docker exec -it cloudwaste_redis redis-cli
```

### Commandes Redis Utiles

```redis
# Tester la connexion
PING

# Voir toutes les clés
KEYS *

# Nombre total de clés
DBSIZE

# Infos sur le serveur Redis
INFO

# Vider le cache (ATTENTION!)
FLUSHALL

# Quitter
quit
```

---

## 🌐 Nginx (Reverse Proxy)

### Vérifier la Configuration Nginx

```bash
# Tester la config
sudo nginx -t

# Si OK, recharger Nginx
sudo systemctl reload nginx

# Redémarrer Nginx (plus radical)
sudo systemctl restart nginx

# Status de Nginx
sudo systemctl status nginx
```

### Éditer la Configuration Nginx

```bash
# Éditer la config CloudWaste
sudo nano /etc/nginx/sites-available/cutcosts.tech

# Après modification, TOUJOURS tester
sudo nginx -t

# Si OK, recharger
sudo systemctl reload nginx
```

### Voir les Logs Nginx

```bash
# Erreurs
tail -f /var/log/nginx/cutcosts.tech-error.log

# Accès (trafic)
tail -f /var/log/nginx/cutcosts.tech-access.log

# Toutes les erreurs Nginx
tail -f /var/log/nginx/error.log
```

---

## 🔐 SSL / HTTPS

### Vérifier le Certificat SSL

```bash
# Voir les certificats installés
sudo certbot certificates

# Informations détaillées
sudo openssl x509 -in /etc/letsencrypt/live/cutcosts.tech/fullchain.pem -text -noout
```

### Renouveler le Certificat SSL

```bash
# Test de renouvellement (sans vraiment renouveler)
sudo certbot renew --dry-run

# Forcer le renouvellement
sudo certbot renew --force-renewal

# Le renouvellement automatique est configuré avec systemd
sudo systemctl status certbot.timer
```

**Note :** Le renouvellement automatique se fait tous les 60 jours.

---

## 🛡️ Sécurité & Firewall

### Vérifier le Firewall (UFW)

```bash
# Voir les règles actives
sudo ufw status verbose

# Voir les règles numérotées
sudo ufw status numbered
```

### Fail2Ban (Protection Brute-Force)

```bash
# Status général
sudo fail2ban-client status

# Status SSH spécifique
sudo fail2ban-client status sshd

# Débannir une IP
sudo fail2ban-client set sshd unbanip IP_ADDRESS
```

### Voir les Tentatives de Connexion SSH

```bash
# Dernières connexions SSH
tail -f /var/log/auth.log

# Dernières connexions réussies
last -n 20

# Tentatives échouées
sudo grep "Failed password" /var/log/auth.log | tail -20
```

---

## 🤖 Ollama (IA Locale)

### Utiliser Ollama

```bash
# Lister les modèles installés
ollama list

# Utiliser un modèle (interactif)
ollama run llama3.2

# Question unique
ollama run llama3.2 "Explique-moi Docker en 3 phrases"

# Status du service Ollama
systemctl status ollama

# Redémarrer Ollama
sudo systemctl restart ollama
```

### Télécharger d'Autres Modèles

```bash
# Télécharger Mistral (plus rapide)
ollama pull mistral

# Télécharger CodeLlama (pour le code)
ollama pull codellama

# Télécharger Llama 3.1 (plus récent)
ollama pull llama3.1

# Voir l'espace utilisé
du -sh ~/.ollama/models/
```

---

## 🔄 Mises à Jour

### Mettre à Jour CloudWaste

```bash
# 1. Aller dans le dossier
cd /var/www/cloudwaste

# 2. Sauvegarder d'abord !
sudo backup-cloudwaste.sh

# 3. Mettre à jour le code (si Git)
git pull origin main

# 4. Reconstruire les images
docker compose build --no-cache

# 5. Redémarrer
docker compose down
docker compose up -d

# 6. Vérifier que tout fonctionne
docker compose ps
docker compose logs -f
```

### Mettre à Jour le Système Ubuntu

```bash
# Mettre à jour la liste des paquets
sudo apt update

# Voir ce qui peut être mis à jour
apt list --upgradable

# Installer les mises à jour
sudo apt upgrade -y

# Si reboot nécessaire
sudo reboot
```

---

## 🧹 Nettoyage & Maintenance

### Nettoyer Docker

```bash
# Voir l'espace utilisé
docker system df

# Supprimer les images non utilisées
docker image prune -a

# Supprimer les volumes non utilisés (ATTENTION!)
docker volume prune

# Supprimer TOUT ce qui n'est pas utilisé (ATTENTION!)
docker system prune -a

# Nettoyer les logs Docker
sudo sh -c 'truncate -s 0 /var/lib/docker/containers/*/*-json.log'
```

### Nettoyer les Logs

```bash
# Nettoyer les logs Nginx anciens
sudo find /var/log/nginx -name "*.gz" -mtime +30 -delete

# Nettoyer les journaux système
sudo journalctl --vacuum-time=7d

# Voir l'espace utilisé par les logs
sudo du -sh /var/log/
```

### Nettoyer l'Espace Disque

```bash
# Nettoyer le cache apt
sudo apt clean
sudo apt autoclean

# Supprimer les paquets inutiles
sudo apt autoremove -y

# Vider la corbeille
rm -rf ~/.local/share/Trash/*
```

---

## 🚨 Dépannage Courant

### CloudWaste ne répond plus

```bash
cd /var/www/cloudwaste

# 1. Vérifier le status
docker compose ps

# 2. Voir les logs pour erreurs
docker compose logs --tail=100

# 3. Redémarrer
docker compose restart

# 4. Si ça ne marche pas, redémarrage complet
docker compose down
docker compose up -d
```

### Un Conteneur est "Exited" ou "Restarting"

```bash
# Voir les logs du conteneur problématique
docker compose logs backend --tail=100

# Redémarrer ce conteneur
docker compose restart backend

# Si erreur persistante, reconstruire
docker compose build backend --no-cache
docker compose up -d backend
```

### Erreur 502 Bad Gateway

```bash
# 1. Vérifier que tous les conteneurs tournent
docker compose ps

# 2. Vérifier les logs backend
docker compose logs backend --tail=50

# 3. Vérifier Nginx
sudo nginx -t
sudo systemctl status nginx

# 4. Redémarrer Nginx
sudo systemctl restart nginx
```

### Erreur "Out of Memory"

```bash
# Vérifier la RAM
free -m

# Vérifier quel conteneur consomme
docker stats

# Redémarrer le conteneur problématique
docker compose restart <nom_service>

# Augmenter le swap si nécessaire
sudo fallocate -l 4G /swapfile2
sudo chmod 600 /swapfile2
sudo mkswap /swapfile2
sudo swapon /swapfile2
```

### SSL "Non Sécurisé" dans le Navigateur

**Causes possibles :**

1. **Certificat récent :** Attendez quelques minutes
2. **Cache navigateur :** Videz le cache (Ctrl+Shift+R)
3. **Certificat expiré :**
   ```bash
   sudo certbot certificates
   # Si expiré :
   sudo certbot renew --force-renewal
   sudo systemctl reload nginx
   ```

---

## 📁 Fichiers Importants

| Fichier | Chemin | Description |
|---------|--------|-------------|
| **Configuration principale** | `/var/www/cloudwaste/.env` | **SECRETS!** Mots de passe, clés |
| **Docker Compose** | `/var/www/cloudwaste/docker-compose.yml` | Configuration des conteneurs |
| **Nginx config** | `/etc/nginx/sites-available/cutcosts.tech` | Configuration Nginx |
| **Certificats SSL** | `/etc/letsencrypt/live/cutcosts.tech/` | Certificats Let's Encrypt |
| **Backups BDD** | `/backups/cloudwaste/database/` | Backups PostgreSQL |
| **Backups configs** | `/backups/cloudwaste/configs/` | Backups .env, nginx, etc. |
| **Clé de chiffrement** | `~/Desktop/encryption_key.backup` | **Sur votre Mac - CRITIQUE!** |

---

## 🔐 Accès aux Secrets

### Voir les Mots de Passe

```bash
cd /var/www/cloudwaste

# Mot de passe PostgreSQL
grep POSTGRES_PASSWORD .env

# Clé de chiffrement
grep ENCRYPTION_KEY .env

# JWT Secret
grep SECRET_KEY .env
```

**⚠️ Ces fichiers contiennent des SECRETS - Ne JAMAIS les partager !**

---

## ⏰ Tâches Planifiées (Cron)

### Voir les Tâches Automatiques

```bash
# Voir les tâches root (backups)
sudo crontab -l

# Voir les tâches utilisateur
crontab -l
```

**Tâches configurées :**
- **Backup quotidien** : 2h00 du matin
- **Health check** : Toutes les 5 minutes
- **Renouvellement SSL** : Automatique (certbot.timer)

### Voir les Logs des Tâches

```bash
# Logs de backup
tail -f /var/log/cloudwaste-backup.log

# Logs de déploiement initial
tail -f /var/log/cloudwaste-deployment.log

# Logs système (cron)
sudo tail -f /var/log/syslog | grep CRON
```

---

## 🎯 Commandes Rapides (Aide-Mémoire)

```bash
# Monitoring complet
sudo cloudwaste-monitor.sh

# Status services
cd /var/www/cloudwaste && docker compose ps

# Logs temps réel
docker compose logs -f

# Redémarrer tout
docker compose restart

# Backup manuel
sudo backup-cloudwaste.sh

# Espace disque
df -h && docker system df

# Tester SSL
sudo certbot certificates

# Firewall
sudo ufw status

# Fail2Ban
sudo fail2ban-client status
```

---

## 📞 En Cas de Problème Grave

### CloudWaste Complètement Down

```bash
# 1. Vérifier l'état
cd /var/www/cloudwaste
docker compose ps
sudo cloudwaste-monitor.sh

# 2. Voir TOUS les logs
docker compose logs --tail=200 > /tmp/cloudwaste-debug.log
cat /tmp/cloudwaste-debug.log

# 3. Redémarrage complet
docker compose down
docker compose up -d

# 4. Attendre 30 secondes
sleep 30

# 5. Re-vérifier
docker compose ps
curl http://localhost:8000/api/v1/health
```

### Restauration Complète depuis Backup

```bash
# 1. Voir les backups
sudo ls -lh /backups/cloudwaste/database/

# 2. Restaurer
sudo restore-cloudwaste.sh TIMESTAMP

# 3. Vérifier
docker compose ps
sudo cloudwaste-monitor.sh
```

### Perte de la Clé de Chiffrement

**⚠️ SI VOUS AVEZ PERDU LA CLÉ :**

**Vous NE POUVEZ PAS récupérer les credentials cloud stockées !**

**Solution :**
1. Voir si elle est dans le fichier .env : `grep ENCRYPTION_KEY /var/www/cloudwaste/.env`
2. Vérifier votre backup Mac : `~/Desktop/encryption_key.backup`
3. Vérifier 1Password/Bitwarden

**Si vraiment perdue :**
- Tous les comptes cloud devront être re-connectés
- Les utilisateurs devront re-saisir leurs credentials AWS/Azure

---

## 📚 Ressources Supplémentaires

### Documentation CloudWaste

- **README principal** : `/var/www/cloudwaste/README.md`
- **Guide de setup** : `/var/www/cloudwaste/SETUP_GUIDE.md`
- **API Docs (live)** : https://cutcosts.tech/api/docs

### Commandes Docker Compose

```bash
cd /var/www/cloudwaste

docker compose up -d          # Démarrer
docker compose down           # Arrêter
docker compose ps             # Status
docker compose logs -f        # Logs
docker compose restart        # Redémarrer
docker compose build          # Rebuild
docker compose exec backend bash  # Shell dans conteneur
```

### Aide Nginx

```bash
sudo nginx -t                 # Tester config
sudo nginx -s reload          # Recharger
sudo systemctl status nginx   # Status
sudo systemctl restart nginx  # Redémarrer
```

---

## ✅ Checklist Maintenance Hebdomadaire

- [ ] Vérifier monitoring : `sudo cloudwaste-monitor.sh`
- [ ] Vérifier espace disque : `df -h`
- [ ] Vérifier les backups : `sudo ls -lh /backups/cloudwaste/database/`
- [ ] Voir les logs pour erreurs : `docker compose logs --tail=100`
- [ ] Vérifier SSL : `sudo certbot certificates`
- [ ] Mettre à jour système : `sudo apt update && sudo apt upgrade`

---

## 🔧 Scripts de Maintenance (Sur le Serveur)

Ces scripts ont été installés automatiquement lors du déploiement :

### Scripts Disponibles

| Script | Commande | Description |
|--------|----------|-------------|
| **Monitoring** | `sudo cloudwaste-monitor.sh` | Status complet du système |
| **Backup** | `sudo backup-cloudwaste.sh` | Backup manuel complet |
| **Restauration** | `sudo restore-cloudwaste.sh TIMESTAMP` | Restaurer un backup |

### Localisation des Scripts

```bash
# Les scripts sont dans /usr/local/bin/
ls -lh /usr/local/bin/ | grep cloudwaste

# Voir le contenu d'un script
cat /usr/local/bin/cloudwaste-monitor.sh
cat /usr/local/bin/backup-cloudwaste.sh
cat /usr/local/bin/restore-cloudwaste.sh
```

---

## 🚀 Déployer une Mise à Jour du Code

### Méthode Rapide (Depuis Votre Mac)

```bash
# 1. Uploader le code modifié
cd /Users/jerome_laval/Desktop/CloudWaste
rsync -avz \
    --exclude 'node_modules' \
    --exclude 'venv' \
    --exclude '.git' \
    --exclude '__pycache__' \
    --exclude '.next' \
    --exclude 'deployment' \
    /Users/jerome_laval/Desktop/CloudWaste/ \
    administrator@83.147.36.59:/var/www/cloudwaste/

# 2. Se connecter au serveur
ssh administrator@83.147.36.59

# 3. Redéployer (sur le serveur)
cd /var/www/cloudwaste
docker compose build --no-cache
docker compose down
docker compose up -d

# 4. Vérifier
docker compose ps
docker compose logs -f
```

---

## 📦 Architecture Déployée

### Stack Technique

**Infrastructure:**
- Ubuntu 24.04 LTS
- Docker Engine + Docker Compose v2
- Nginx (reverse proxy)
- Let's Encrypt SSL (auto-renouvelé)
- UFW Firewall + Fail2Ban

**CloudWaste Services:**
- PostgreSQL 15 (base de données)
- Redis 7 (cache + queue)
- FastAPI Backend (API REST)
- Celery Worker + Beat (tâches async)
- Next.js Frontend (production build)

**Services Additionnels:**
- Portainer CE (gestion Docker)
- Ollama (LLM local)

**Automatisation:**
- Backups quotidiens (2h00)
- Health checks (5 min)
- Log rotation automatique
- Monitoring système

### Ports Ouverts

```bash
# Vérifier les ports ouverts
sudo ufw status verbose

# Ports exposés :
# - 22 (SSH)
# - 80 (HTTP → redirige vers HTTPS)
# - 443 (HTTPS)
# - 9000 (Portainer)
```

---

## 🎓 Alias Pratiques (Optionnel)

Ajoutez ces alias pour accéder plus rapidement aux commandes courantes :

```bash
# Éditer le fichier de configuration shell
nano ~/.bashrc  # ou ~/.zshrc si vous utilisez zsh

# Ajouter ces lignes à la fin :
alias cw-status='cd /var/www/cloudwaste && docker compose ps'
alias cw-logs='cd /var/www/cloudwaste && docker compose logs -f'
alias cw-monitor='sudo cloudwaste-monitor.sh'
alias cw-backup='sudo backup-cloudwaste.sh'
alias cw-restart='cd /var/www/cloudwaste && docker compose restart'

# Sauvegarder et recharger
source ~/.bashrc  # ou source ~/.zshrc
```

**Utilisation :**
```bash
cw-status    # Voir le status rapidement
cw-logs      # Voir les logs
cw-monitor   # Monitoring complet
cw-backup    # Backup rapide
cw-restart   # Redémarrer tous les services
```

---

**📝 Dernière mise à jour :** 20 octobre 2025  
**Version CloudWaste :** Production v1.0  
**Serveur :** cutcosts.tech (83.147.36.59)

**🔐 N'oubliez pas :** La clé de chiffrement est dans 1Password/Bitwarden !

---

## 📞 Support & Ressources

**Documentation en ligne :**
- API Swagger : https://cutcosts.tech/api/docs
- Portainer : http://83.147.36.59:9000

**Sur le serveur :**
- Logs déploiement : `/var/log/cloudwaste-deployment.log`
- Logs backups : `/var/log/cloudwaste-backup.log`
- Config Nginx : `/etc/nginx/sites-available/cutcosts.tech`
- Données app : `/var/www/cloudwaste/`

**Commande d'urgence complète :**
```bash
# Si tout plante, cette commande redémarre proprement
cd /var/www/cloudwaste && \
docker compose down && \
sleep 5 && \
docker compose up -d && \
sleep 30 && \
docker compose ps && \
sudo cloudwaste-monitor.sh
```

