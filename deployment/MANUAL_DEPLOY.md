# 🚨 Guide de Déploiement Manuel CloudWaste

Ce guide explique comment déployer manuellement CloudWaste sur le VPS en cas d'échec du déploiement automatique GitHub Actions.

## 📋 Table des matières

1. [Quand utiliser ce guide](#quand-utiliser-ce-guide)
2. [Prérequis](#prérequis)
3. [Synchroniser les variables Sentry](#synchroniser-les-variables-sentry)
4. [Déploiement manuel complet](#déploiement-manuel-complet)
5. [Résolution de problèmes](#résolution-de-problèmes)
6. [Rollback manuel](#rollback-manuel)

---

## Quand utiliser ce guide

Utilisez ce guide dans les situations suivantes :
- ❌ Le déploiement GitHub Actions échoue de manière répétée
- ❌ Build Docker timeout malgré les retries
- ❌ Problèmes réseau entre GitHub Actions et le VPS
- ❌ Vous devez patcher rapidement une variable d'environnement

---

## Prérequis

### 1. Accès SSH au VPS

```bash
# Testez votre connexion SSH
ssh root@YOUR_VPS_IP

# Si vous avez configuré un alias dans ~/.ssh/config :
ssh cloudwaste-vps
```

### 2. Vérifier l'espace disque

```bash
ssh root@YOUR_VPS_IP << 'ENDSSH'
  df -h /opt/cloudwaste
  docker system df
ENDSSH
```

**Si l'espace disque est faible (>85%) :**
```bash
ssh root@YOUR_VPS_IP << 'ENDSSH'
  docker system prune -af --volumes
ENDSSH
```

---

## Synchroniser les variables Sentry

### Méthode 1 : Script automatique (Recommandé)

```bash
# Depuis votre machine locale
export VPS_HOST=YOUR_VPS_IP
export VPS_USER=root
bash deployment/sync-sentry-env.sh
```

### Méthode 2 : Édition manuelle via SSH

```bash
ssh root@YOUR_VPS_IP

cd /opt/cloudwaste

# Créer une sauvegarde
cp .env.prod .env.prod.backup.$(date +%Y%m%d_%H%M%S)

# Éditer le fichier
nano .env.prod
```

**Ajoutez ces lignes à la fin du fichier :**

```bash
# Sentry Error Tracking (Backend)
SENTRY_DSN=https://1e103a6f257e3a1c7f286efb9fa42c75@o4510350814085121.ingest.de.sentry.io/4510350841086032
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1
SENTRY_PROFILES_SAMPLE_RATE=0.1

# Sentry Error Tracking (Frontend)
NEXT_PUBLIC_SENTRY_DSN=https://442a2365755e0b972138478b85fdb5a7@o4510350814085121.ingest.de.sentry.io/4510350846984272
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
```

**Sauvegardez (Ctrl+O, Entrée, Ctrl+X) et redémarrez :**

```bash
docker compose -f deployment/docker-compose.prod.yml restart backend frontend
```

---

## Déploiement manuel complet

### Étape 1 : Se connecter au VPS

```bash
ssh root@YOUR_VPS_IP
cd /opt/cloudwaste
```

### Étape 2 : Mettre à jour le code

```bash
# Récupérer les dernières modifications
git fetch origin master
git reset --hard origin/master

# Vérifier le commit
git log --oneline -1
```

### Étape 3 : Synchroniser les variables Sentry (si nécessaire)

```bash
# Exécuter le script de synchronisation
bash deployment/sync-sentry-env.sh --local
```

### Étape 4 : Vérifier l'espace disque

```bash
df -h /opt/cloudwaste
```

**Si l'espace est faible (>85%) :**
```bash
docker system prune -af --volumes
```

### Étape 5 : Lancer le déploiement sans coupure

```bash
bash deployment/zero-downtime-deploy.sh
```

**Le script va automatiquement :**
1. ✅ Builder les nouvelles images Docker (avec retry si timeout)
2. ✅ Démarrer les nouveaux conteneurs en parallèle des anciens
3. ✅ Effectuer des health checks
4. ✅ Redémarrer Nginx pour rafraîchir le cache DNS
5. ✅ Vérifier que l'application est accessible publiquement
6. ✅ Sauvegarder le commit stable
7. ❌ **Rollback automatique** si une étape échoue

### Étape 6 : Vérifier le déploiement

```bash
# Vérifier les conteneurs
docker ps | grep cloudwaste

# Vérifier les logs backend
docker logs cloudwaste_backend --tail 50

# Vérifier les logs frontend
docker logs cloudwaste_frontend --tail 50

# Tester l'API
curl https://cutcosts.tech/api/v1/health

# Tester le frontend
curl -I https://cutcosts.tech
```

---

## Résolution de problèmes

### Problème 1 : Build Docker timeout

**Symptôme :** `error: RPC failed; curl 28 Timeout was reached`

**Solution :**
```bash
# Option 1 : Augmenter le timeout Docker Buildkit
export DOCKER_BUILDKIT_TIMEOUT=900  # 15 minutes

# Option 2 : Builder sans parallélisation
docker compose -f deployment/docker-compose.prod.yml build

# Option 3 : Builder un service spécifique
docker compose -f deployment/docker-compose.prod.yml build backend
docker compose -f deployment/docker-compose.prod.yml build frontend
docker compose -f deployment/docker-compose.prod.yml build celery_worker
```

### Problème 2 : Erreur "No space left on device"

**Symptôme :** `write /var/lib/docker: no space left on device`

**Solution :**
```bash
# Vérifier l'espace
df -h
docker system df

# Nettoyage agressif
docker system prune -af --volumes

# Supprimer les images non utilisées
docker image prune -a

# Si encore insuffisant - Supprimer toutes les images et rebuild
docker rmi $(docker images -q)
bash deployment/zero-downtime-deploy.sh
```

### Problème 3 : Health check échoue

**Symptôme :** `Le backend n'a pas démarré correctement`

**Solution :**
```bash
# Consulter les logs
docker logs cloudwaste_backend --tail 100

# Vérifier les variables d'environnement
docker exec cloudwaste_backend env | grep SENTRY

# Redémarrer manuellement
docker compose -f deployment/docker-compose.prod.yml restart backend

# Tester le health check directement
docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health
```

### Problème 4 : Frontend ne démarre pas

**Symptôme :** `FRONTEND_HEALTHY != true`

**Solution :**
```bash
# Next.js peut prendre 30-60s à démarrer en production
# Vérifier les logs
docker logs cloudwaste_frontend --tail 100

# Vérifier les variables d'environnement Sentry
docker exec cloudwaste_frontend env | grep NEXT_PUBLIC_SENTRY

# Rebuild le frontend uniquement
docker compose -f deployment/docker-compose.prod.yml build frontend
docker compose -f deployment/docker-compose.prod.yml up -d frontend
```

### Problème 5 : Nginx ne rafraîchit pas le cache DNS

**Symptôme :** `502 Bad Gateway` après le déploiement

**Solution :**
```bash
# Redémarrer Nginx manuellement
docker compose -f deployment/docker-compose.prod.yml restart nginx

# Vérifier les logs Nginx
docker logs cloudwaste_nginx --tail 50

# Vérifier la configuration Nginx
docker exec cloudwaste_nginx nginx -t

# Reload Nginx sans redémarrage
docker exec cloudwaste_nginx nginx -s reload
```

---

## Rollback manuel

### Scénario 1 : Rollback automatique a déjà été déclenché

Le script `zero-downtime-deploy.sh` effectue automatiquement un rollback vers le dernier commit stable en cas d'échec.

**Vérifier le commit actuel :**
```bash
cat /opt/cloudwaste/.last_stable_commit
git log --oneline -5
```

### Scénario 2 : Rollback manuel vers un commit spécifique

```bash
# Se connecter au VPS
ssh root@YOUR_VPS_IP
cd /opt/cloudwaste

# Identifier le commit stable
git log --oneline -10

# Rollback vers un commit spécifique (exemple: abc1234)
git reset --hard abc1234

# Rebuild et redémarrer
bash deployment/zero-downtime-deploy.sh
```

### Scénario 3 : Rollback d'urgence (sans health checks)

**⚠️ Utilisez UNIQUEMENT en cas d'urgence absolue :**

```bash
ssh root@YOUR_VPS_IP
cd /opt/cloudwaste

# Récupérer le dernier commit stable
STABLE_COMMIT=$(cat .last_stable_commit)
git reset --hard "$STABLE_COMMIT"

# Rebuild SANS health checks (rapide mais risqué)
docker compose -f deployment/docker-compose.prod.yml build --parallel
docker compose -f deployment/docker-compose.prod.yml up -d

# Vérifier manuellement après 30 secondes
sleep 30
curl https://cutcosts.tech/api/v1/health
```

---

## Checklist post-déploiement

Après un déploiement manuel, vérifiez :

- [ ] `curl https://cutcosts.tech` renvoie HTTP 200
- [ ] `curl https://cutcosts.tech/api/v1/health` renvoie `{"status":"healthy"}`
- [ ] `docker ps` montre tous les conteneurs UP
- [ ] `docker logs cloudwaste_backend --tail 20` ne montre pas d'erreurs
- [ ] `docker logs cloudwaste_frontend --tail 20` ne montre pas d'erreurs
- [ ] Variables Sentry présentes dans `.env.prod`
- [ ] Commit stable sauvegardé dans `.last_stable_commit`
- [ ] Dashboard Sentry montre des événements de production

---

## Support

En cas de problème persistant :
1. Consultez les logs détaillés : `docker compose -f deployment/docker-compose.prod.yml logs --tail=200`
2. Vérifiez le diagnostic : `bash deployment/diagnose.sh` (si disponible)
3. Contactez l'équipe technique

---

**📌 Note importante :** Ce guide suppose que vous avez accès SSH au VPS. Si ce n'est pas le cas, demandez les credentials VPS à l'administrateur système.
