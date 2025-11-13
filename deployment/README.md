# CloudWaste - Production Deployment Guide

Complete guide for deploying CloudWaste to production using Docker + GitHub Actions CI/CD.

---

## 🎯 Quick Overview

**Infrastructure:**
- **VPS:** Ubuntu Server 24 LTS
- **Domain:** cutcosts.tech (155.117.43.17)
- **SSL:** Let's Encrypt (auto-renewal)
- **Stack:** Docker Compose + Nginx reverse proxy
- **Monitoring:** Sentry (backend + frontend)

**Deployment:** Zero-downtime Blue-Green with automatic rollback
**Deployment Time:** ~2-3 minutes per push to `master`

---

## 📁 Deployment Files

| File | Purpose |
|------|---------|
| `docker-compose.prod.yml` | Production Docker stack |
| `nginx.conf` | Reverse proxy + SSL configuration |
| `zero-downtime-deploy.sh` | **Main deployment script** (Blue-Green + rollback) |
| `setup-server.sh` | Initial VPS setup (run once) |
| `sync-sentry-env.sh` | Sentry variables synchronization |
| `diagnose.sh` | System health diagnostics |
| `debug-last-deployment.sh` | Deployment debugging |
| `backup-full.sh` | Full system backup (DB + volumes + config) |
| `restore-full.sh` | Interactive restore utility |
| `backup-db.sh` | Legacy database-only backup |
| `setup-backup-cron.sh` | Configure automated daily backups |
| `activate-user.sh` | User management utilities |

---

## 🚀 Initial Setup (One-Time)

### Step 1: Configure GitHub Repository

1. **Update repository URL** in `setup-server.sh` (line 37):
   ```bash
   GITHUB_REPO="https://github.com/YOUR_USERNAME/CloudWaste.git"
   ```

2. **Generate SSH key** for GitHub Actions:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/cloudwaste_deploy -N ""
   cat ~/.ssh/cloudwaste_deploy.pub
   ```

3. **Add SSH public key to VPS:**
   ```bash
   ssh administrator@YOUR_VPS_IP
   mkdir -p ~/.ssh
   echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   exit
   ```

4. **Configure GitHub Secrets:**

   Go to: **GitHub repo → Settings → Secrets and variables → Actions**

   Add these 3 secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `VPS_HOST` | `YOUR_VPS_IP` |
   | `VPS_USER` | `administrator` (or your admin user) |
   | `VPS_SSH_PRIVATE_KEY` | Content of `~/.ssh/cloudwaste_deploy` |

### Step 2: Initial VPS Setup

```bash
# 1. Connect to VPS
ssh administrator@YOUR_VPS_IP

# 2. Download setup script
wget https://raw.githubusercontent.com/YOUR_USERNAME/CloudWaste/master/deployment/setup-server.sh

# 3. Run setup (installs Docker, Nginx, SSL, monitoring)
chmod +x setup-server.sh
sudo ./setup-server.sh
```

**What the setup script does:**
- ✅ Installs Docker & Docker Compose
- ✅ Configures UFW firewall (ports 22, 80, 443)
- ✅ Installs Certbot + generates SSL certificates
- ✅ Clones repository to `/opt/cloudwaste`
- ✅ Generates `.env.prod` with secure secrets
- ✅ Sets up automatic SSL renewal

### Step 3: Configure Environment (Optional)

```bash
nano /opt/cloudwaste/.env.prod

# Update SMTP settings (if using email notifications)
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=YOUR_SENDGRID_API_KEY

# Update Sentry DSN (error monitoring)
SENTRY_DSN=https://...@o4510350814085121.ingest.de.sentry.io/...
NEXT_PUBLIC_SENTRY_DSN=https://...@o4510350814085121.ingest.de.sentry.io/...
```

### Step 4: Initial Deployment

```bash
cd /opt/cloudwaste
bash deployment/zero-downtime-deploy.sh
```

**Verify deployment:**
- 🌐 https://cutcosts.tech
- 📚 https://cutcosts.tech/api/docs
- ✅ https://cutcosts.tech/api/v1/health

---

## 🔄 Automated CI/CD Deployments

Once initial setup is complete, every `git push` to `master` triggers **automatic zero-downtime deployment** via GitHub Actions.

### 🔵🟢 Blue-Green Deployment Strategy

CloudWaste uses an advanced deployment strategy ensuring **zero service interruption**:

1. **Build Phase** → New images built while old containers run
2. **Migration Phase** → Database migrations applied
3. **Health Check Phase** → New containers tested before switching
4. **Switch Phase** → Traffic switched to new containers only if healthy
5. **Cleanup Phase** → Old containers removed after success
6. **Rollback Phase** → Automatic rollback to last stable version on failure

### CI/CD Workflow

```bash
# Local machine
git add .
git commit -m "feat: add new feature"
git push origin master

# GitHub Actions automatically:
# 1. SSH to VPS
# 2. Sync Sentry variables (sync-sentry-env.sh)
# 3. Pull latest code (git reset --hard origin/master)
# 4. Run zero-downtime-deploy.sh
# 5. Build new images (site stays online)
# 6. Start new containers alongside old ones
# 7. Perform internal + external health checks
# 8. Switch traffic if healthy
# 9. Save commit as stable version
# 10. OR perform automatic rollback if failure
```

### 🛡️ Safety Features

- ✅ **No downtime** - Site stays online during deployment
- ✅ **Health checks** - Backend, frontend, public URL verification
- ✅ **Auto-rollback** - Automatic restoration to last stable version
- ✅ **Version tracking** - Last stable commit in `.last_stable_commit`
- ✅ **Error handling** - Any script error triggers rollback
- ✅ **Retry logic** - Build retries up to 3 times on network errors

### Manual Trigger

GitHub Actions UI: **Actions tab → Deploy to Production → Run workflow**

---

## 📊 Sentry Error Monitoring

CloudWaste includes **full Sentry integration** for backend (FastAPI) and frontend (Next.js).

### What Sentry Captures

**Backend (Python):**
- ✅ Unhandled exceptions
- ✅ API errors (500, 400, etc.)
- ✅ Database errors
- ✅ Cloud SDK errors (AWS, Azure, GCP)
- ✅ User context (email, user ID)
- ✅ Performance monitoring (10% sample rate)

**Frontend (JavaScript/Next.js):**
- ✅ React errors (component crashes)
- ✅ API request failures
- ✅ Promise rejections
- ✅ Navigation errors
- ✅ Source maps for readable stack traces

### Sentry CI/CD Integration

**Critical:** Frontend Sentry requires variables injected **at build time** (not runtime).

**How it works:**
1. `sync-sentry-env.sh` verifies Sentry variables in `.env.prod`
2. `zero-downtime-deploy.sh` passes variables as `--build-arg` to Docker:
   ```bash
   docker compose build \
     --build-arg NEXT_PUBLIC_SENTRY_DSN="$NEXT_PUBLIC_SENTRY_DSN" \
     --build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT="production" \
     --parallel
   ```
3. Frontend built with Sentry DSN embedded
4. Errors automatically captured in production

**Verify Sentry after deployment:**
```bash
# Backend variables (runtime)
docker exec cloudwaste_backend env | grep "^SENTRY"

# Frontend variables (build-time)
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY"

# Browser console should show:
# [SentryProvider] DSN: https://...
# [SentryProvider] Sentry initialisé avec succès !
```

**Access Sentry Dashboard:**
- 🌐 https://sentry.io
- Organization: jerome-laval-x3
- Projects: `cloudwaste` (backend), `cloudwaste-frontend` (frontend)

---

## 💾 Backups & Disaster Recovery

### Automated Local Backups

CloudWaste includes comprehensive automated backup system (runs nightly at 3 AM).

**What gets backed up:**
- ✅ PostgreSQL database
- ✅ Redis database
- ✅ Encryption key (🔴 CRITICAL)
- ✅ Docker volumes (postgres_data, redis_data)
- ✅ Configuration files (.env.prod, docker-compose, nginx)
- ✅ Git repository state

**Backup rotation:**
- Daily: Last 7 days
- Weekly: Last 4 weeks
- Monthly: Last 3 months

**Storage location:** `/opt/cloudwaste/backups/`

### Setup Automated Backups

```bash
cd /opt/cloudwaste
sudo bash deployment/setup-backup-cron.sh
```

This creates a cron job (daily 3 AM) and runs initial test backup.

### Manual Backup & Restore

```bash
# Manual backup
bash deployment/backup-full.sh

# Restore (interactive menu)
bash deployment/restore-full.sh

# View backups
ls -lh /opt/cloudwaste/backups/daily/
ls -lh /opt/cloudwaste/backups/weekly/
ls -lh /opt/cloudwaste/backups/monthly/

# Check backup logs
tail -f /var/log/cloudwaste-backup.log
```

### Storage Requirements

- **Per backup:** ~100-500MB (compressed)
- **Total (30 days):** ~2-5GB
- **Check space:** `df -h /opt/cloudwaste/backups`

### ⚠️ Important Notes

**Current setup (MVP):**
- ✅ Backups are LOCAL on VPS
- ✅ Protects against data corruption, accidental deletion
- ❌ Does NOT protect against VPS failure/loss

**Recommended upgrade for production:**
- Add off-site backup to cloud storage:
  - Restic + Backblaze B2 (~$1-3/month)
  - rclone + S3 (~$2-5/month)
  - Hetzner Storage Box (€3.81/month, EU-based)

---

## 🔍 Monitoring & Logs

### Portainer (Container Management UI)

Visual container management included on VPS.

**Access:**
- 🌐 **HTTPS:** https://YOUR_VPS_IP:9443 (self-signed cert warning is normal)
- 🌐 **HTTP:** http://YOUR_VPS_IP:9000

**Features:**
- Dashboard → Overview of containers, images, volumes
- Containers → Status, logs, stats, shell access
- Logs → Real-time logs with search/filter
- Stats → CPU, Memory, Network I/O per container
- Console → Execute commands inside containers

### View Container Status

```bash
cd /opt/cloudwaste
docker compose -f deployment/docker-compose.prod.yml ps
```

### View Logs

```bash
# Backend
docker logs -f cloudwaste_backend

# Frontend
docker logs -f cloudwaste_frontend

# Celery Worker
docker logs -f cloudwaste_celery_worker

# Nginx
docker logs -f cloudwaste_nginx

# All logs combined
docker compose -f deployment/docker-compose.prod.yml logs -f
```

### Container Resource Usage

```bash
docker stats
```

---

## 🛠 Common Operations

### Restart a Service

```bash
docker compose -f deployment/docker-compose.prod.yml restart backend
```

### Access Container Shell

```bash
docker exec -it cloudwaste_backend bash
```

### Run Database Migrations

```bash
docker compose -f deployment/docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Access PostgreSQL

```bash
# Interactive psql
docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste

# Run SQL query
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM users;"
```

### Rebuild Single Service

```bash
docker compose -f deployment/docker-compose.prod.yml up -d --build --no-deps backend
```

### Manual Deployment

```bash
ssh administrator@YOUR_VPS_IP
cd /opt/cloudwaste
git pull origin master
bash deployment/zero-downtime-deploy.sh
```

---

## 🔄 Rollback to Previous Version

### Automatic Rollback (Recommended)

**Rollback happens automatically** when deployment fails:
- Detects any failure (build error, health check failure, etc.)
- Reads last stable commit from `.last_stable_commit`
- Resets code to that commit
- Rebuilds and restarts with stable version
- Site stays online throughout

**No manual intervention required!**

### Manual Rollback (Edge Cases)

```bash
cd /opt/cloudwaste

# Check last stable commit
cat .last_stable_commit

# View recent commits
git log --oneline -10

# Manual rollback to specific commit
git reset --hard COMMIT_HASH
bash deployment/zero-downtime-deploy.sh
```

### Check Rollback Status

```bash
cd /opt/cloudwaste
echo "Current: $(git rev-parse --short HEAD)"
echo "Stable:  $(cat .last_stable_commit | cut -c1-7)"
```

---

## 🐛 Troubleshooting

### Issue: Containers Keep Restarting

```bash
# Check logs
docker logs cloudwaste_backend

# Common causes:
# - Missing .env.prod
# - Database connection failed
# - Port already in use
```

### Issue: SSL Certificate Error

```bash
# Verify certificates exist
sudo ls -la /etc/letsencrypt/live/cutcosts.tech/

# Regenerate if missing
sudo certbot certonly --standalone -d cutcosts.tech -d www.cutcosts.tech

# Restart nginx
docker compose -f deployment/docker-compose.prod.yml restart nginx
```

### Issue: Frontend Shows 502 Bad Gateway

```bash
# Check if backend is healthy
docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health

# Restart nginx
docker compose -f deployment/docker-compose.prod.yml restart nginx

# Check nginx logs
docker logs cloudwaste_nginx --tail 100
```

### Issue: Database Connection Error

```bash
# Verify PostgreSQL is running
docker exec cloudwaste_postgres pg_isready -U cloudwaste

# Check credentials in .env.prod
cat /opt/cloudwaste/.env.prod | grep POSTGRES

# Restart database
docker compose -f deployment/docker-compose.prod.yml restart postgres
```

### Issue: Frontend Sentry DSN Undefined

```bash
# Verify variables in container
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY"

# If empty, rebuild with variables
cd /opt/cloudwaste
set -a
source .env.prod
set +a
docker compose -f deployment/docker-compose.prod.yml up -d --build frontend
```

### Use Diagnostic Script

```bash
bash deployment/diagnose.sh
```

This script checks:
- ✅ Container status and health
- ✅ Environment variables
- ✅ Database connectivity
- ✅ Nginx configuration
- ✅ SSL certificates
- ✅ Disk space

---

## 🔐 Security Best Practices

### 1. Keep .env.prod Secure

```bash
# Never commit to Git
chmod 600 /opt/cloudwaste/.env.prod

# Verify in .gitignore
grep "\.env\.prod" /opt/cloudwaste/.gitignore
```

### 2. Rotate Secrets Regularly

```bash
# Generate new secret
openssl rand -hex 32

# Update .env.prod
nano /opt/cloudwaste/.env.prod

# Restart services
docker compose -f deployment/docker-compose.prod.yml restart
```

### 3. Monitor Failed Login Attempts

```bash
docker logs cloudwaste_backend | grep "401\|403"
```

### 4. Update SSL Certificates

```bash
# Auto-renewal via cron, or manually:
sudo certbot renew
docker exec cloudwaste_nginx nginx -s reload
```

---

## 📊 Performance Optimization

### Monitor Container Resources

```bash
docker stats --no-stream
```

### Scale Services

```bash
# Edit docker-compose.prod.yml
# Change --workers 4 to --workers 8 for backend

docker compose -f deployment/docker-compose.prod.yml up -d --no-deps --build backend
```

### Database Optimization

```bash
# Run VACUUM and ANALYZE
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "VACUUM ANALYZE;"
```

---

## 📝 Maintenance Checklist

**Daily:**
- ✅ Check uptime: `curl https://cutcosts.tech/api/v1/health`
- ✅ Verify backups: `ls -lh /opt/cloudwaste/backups/daily/`

**Weekly:**
- ✅ Review error logs: `docker logs cloudwaste_backend | grep ERROR`
- ✅ Check disk space: `df -h`
- ✅ Update images: `docker compose -f deployment/docker-compose.prod.yml pull`

**Monthly:**
- ✅ Rotate secrets (JWT_SECRET, POSTGRES_PASSWORD)
- ✅ Review SSL expiration: `sudo certbot certificates`
- ✅ Test backup restoration

---

## 📚 Additional Resources

- **Docker Compose:** https://docs.docker.com/compose/
- **Nginx:** https://nginx.org/en/docs/
- **Let's Encrypt:** https://letsencrypt.org/docs/
- **Sentry:** https://docs.sentry.io/
- **PostgreSQL Backups:** https://www.postgresql.org/docs/current/backup.html

---

**Last Updated:** 2025-01-13
**Version:** 3.0.0 (Zero-Downtime + Auto-Rollback + Sentry Integration)
