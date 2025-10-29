# CloudWaste - Production Deployment Guide

Complete guide for deploying CloudWaste to your VPS using Docker + GitHub Actions.

---

## 🎯 Deployment Overview

**Infrastructure:**
- **VPS:** Ubuntu Server 24 LTS
- **Domain:** cutcosts.tech (155.117.43.17)
- **SSL:** Let's Encrypt (auto-renewal)
- **Stack:** Docker Compose with Nginx reverse proxy

**Automated CI/CD:**
```
Local Dev → git push → GitHub Actions → VPS → Production Live
```

**Deployment Time:** ~2-3 minutes per deployment

---

## 📁 Deployment Files

```
deployment/
├── docker-compose.prod.yml    # Production Docker stack
├── nginx.conf                 # Reverse proxy + SSL config
├── setup-server.sh            # Initial VPS setup (run once)
├── quick-deploy.sh            # Fast deployment script
├── backup-db.sh               # Database backup automation
└── README.md                  # This file
```

---

## 🚀 Initial Setup (One-Time)

### Step 1: Prepare Your Local Machine

1. **Update GitHub repository URL** in `deployment/setup-server.sh`:
   ```bash
   # Line 37
   GITHUB_REPO="https://github.com/YOUR_USERNAME/CloudWaste.git"
   ```

2. **Generate SSH key** for GitHub Actions:
   ```bash
   ssh-keygen -t ed25519 -f ~/.ssh/cloudwaste_deploy -N ""
   cat ~/.ssh/cloudwaste_deploy.pub
   ```

3. **Add SSH public key to VPS:**
   ```bash
   ssh administrator@155.117.43.17
   mkdir -p ~/.ssh
   echo "YOUR_PUBLIC_KEY_HERE" >> ~/.ssh/authorized_keys
   chmod 600 ~/.ssh/authorized_keys
   exit
   ```

4. **Configure GitHub Secrets:**

   Go to your GitHub repo → Settings → Secrets and variables → Actions → New repository secret

   Add these secrets:

   | Secret Name | Value |
   |-------------|-------|
   | `VPS_HOST` | `155.117.43.17` |
   | `VPS_USER` | `administrator` |
   | `VPS_SSH_PRIVATE_KEY` | Content of `~/.ssh/cloudwaste_deploy` |

### Step 2: Initial VPS Setup

1. **Connect to your VPS:**
   ```bash
   ssh administrator@155.117.43.17
   ```

2. **Download and run setup script:**
   ```bash
   # Download setup script (adjust URL to your repo)
   wget https://raw.githubusercontent.com/YOUR_USERNAME/CloudWaste/master/deployment/setup-server.sh

   # OR if repo is already cloned locally, use scp:
   # scp deployment/setup-server.sh administrator@155.117.43.17:~/

   # Make executable and run
   chmod +x setup-server.sh
   sudo ./setup-server.sh
   ```

3. **What the setup script does:**
   - ✅ Installs Docker & Docker Compose
   - ✅ Configures firewall (ports 22, 80, 443)
   - ✅ Installs Certbot for SSL
   - ✅ Generates SSL certificates for cutcosts.tech
   - ✅ Clones repository to `/opt/cloudwaste`
   - ✅ Generates `.env.prod` with secure secrets
   - ✅ Sets up automatic SSL renewal

4. **Configure email settings (optional):**
   ```bash
   nano /opt/cloudwaste/.env.prod

   # Update these lines:
   SMTP_HOST=smtp.sendgrid.net
   SMTP_PORT=587
   SMTP_USER=apikey
   SMTP_PASSWORD=YOUR_SENDGRID_API_KEY
   ```

5. **Initial deployment:**
   ```bash
   cd /opt/cloudwaste
   bash deployment/quick-deploy.sh
   ```

6. **Verify deployment:**

   Open in browser:
   - 🌐 https://cutcosts.tech
   - 📚 https://cutcosts.tech/api/docs

---

## 🔄 Automated Deployments (GitHub Actions)

Once initial setup is complete, every `git push` to the `master` branch triggers automatic deployment.

### Workflow:

```bash
# On your local machine
git add .
git commit -m "feat: add new feature"
git push origin master

# GitHub Actions automatically:
# 1. Connects to VPS via SSH
# 2. Pulls latest code
# 3. Runs deployment/quick-deploy.sh
# 4. Performs health checks
# 5. Reports success/failure
```

### Manual Trigger:

You can also trigger deployment manually via GitHub Actions UI:
1. Go to your repo → Actions tab
2. Select "Deploy to Production" workflow
3. Click "Run workflow"

---

## 📦 Manual Deployments

If you need to deploy manually from the VPS:

```bash
ssh administrator@155.117.43.17
cd /opt/cloudwaste
git pull origin master
bash deployment/quick-deploy.sh
```

---

## 🔍 Monitoring & Logs

### 🐳 Portainer (Container Management UI)

CloudWaste VPS includes **Portainer CE** for visual container management and monitoring.

**Access Portainer:**
- 🌐 **HTTPS (recommended):** https://155.117.43.17:9443
- 🌐 **HTTP:** http://155.117.43.17:9000

**Installation (Already done on VPS):**
```bash
# Portainer is installed as standalone container
docker ps | grep portainer
```

**Using Portainer:**
1. **Dashboard** → Overview of all containers, images, volumes, networks
2. **Containers** → View status, logs, stats, shell access for each container
3. **Logs** → Real-time logs with search/filter capabilities
4. **Stats** → CPU, Memory, Network I/O per container
5. **Console** → Execute commands inside containers without SSH

**Benefits:**
- ✅ Visual healthcheck status (healthy/unhealthy/starting)
- ✅ One-click access to container logs
- ✅ Restart/stop/start containers with UI
- ✅ Resource usage graphs
- ✅ No need to memorize docker commands

**Common Tasks in Portainer:**

| Task | How to do it |
|------|--------------|
| View logs | Containers → Click container → Logs tab |
| Restart container | Containers → Select container → Restart button |
| Check healthcheck | Containers → Click container → Inspect → Health section |
| Open shell | Containers → Click container → Console tab |
| View resource usage | Containers → Click container → Stats tab |

### View Container Status (CLI):
```bash
cd /opt/cloudwaste
docker compose -f deployment/docker-compose.prod.yml ps
```

### View Logs (CLI):
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

### Container Stats (CPU, Memory):
```bash
docker stats
```

---

## 🛠 Common Operations

### Restart a Service:
```bash
docker compose -f deployment/docker-compose.prod.yml restart backend
```

### Access Container Shell:
```bash
docker exec -it cloudwaste_backend bash
```

### Run Database Migrations:
```bash
docker compose -f deployment/docker-compose.prod.yml run --rm backend alembic upgrade head
```

### Access PostgreSQL:
```bash
# From container
docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste

# Run SQL query
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "SELECT COUNT(*) FROM users;"
```

### Rebuild Single Service:
```bash
docker compose -f deployment/docker-compose.prod.yml up -d --build --no-deps backend
```

---

## 💾 Backups & Disaster Recovery

### 🛡 Automated Local Backups

CloudWaste includes a comprehensive automated backup system that runs nightly on your VPS.

**What gets backed up:**
- ✅ PostgreSQL database (all data)
- ✅ Redis database (cache, celery results)
- ✅ Encryption key (🔴 CRITICAL)
- ✅ Docker volumes (postgres_data, redis_data)
- ✅ Configuration files (.env.prod, docker-compose, nginx)
- ✅ Git repository state

**Backup rotation:**
- Daily: Last 7 days
- Weekly: Last 4 weeks
- Monthly: Last 3 months

### ⚡ Quick Setup

**Initial setup (run once on VPS):**
```bash
cd /opt/cloudwaste
sudo bash deployment/setup-backup-cron.sh
```

This will:
1. Create cron job (runs daily at 3 AM)
2. Set up logging (`/var/log/cloudwaste-backup.log`)
3. Run initial test backup
4. Verify everything works

**Backups are stored in:** `/opt/cloudwaste/backups/`

### 📋 Backup Management

**Manual backup:**
```bash
bash deployment/backup-full.sh
```

**Restore from backup:**
```bash
bash deployment/restore-full.sh
```

**View backups:**
```bash
ls -lh /opt/cloudwaste/backups/daily/
ls -lh /opt/cloudwaste/backups/weekly/
ls -lh /opt/cloudwaste/backups/monthly/
```

**Check backup logs:**
```bash
tail -f /var/log/cloudwaste-backup.log
```

### 🔄 Restore Process

The restore script provides an interactive menu:

1. Lists all available backups (daily/weekly/monthly)
2. Shows backup information (size, date, contents)
3. Offers restore options:
   - Full restore (recommended)
   - Database only
   - Configuration only
   - Encryption key only
4. Safely stops containers
5. Restores selected data
6. Restarts containers
7. Verifies restoration

### 💾 Storage Requirements

- **Per backup:** ~100-500MB (compressed)
- **Total (30 days):** ~2-5GB
- **Check disk space:** `df -h /opt/cloudwaste/backups`

### ⚠️ Important Notes

**For MVP (current setup):**
- ✅ Backups are LOCAL on VPS
- ✅ Protects against data corruption, accidental deletion
- ❌ Does NOT protect against VPS failure/loss

**For Production (recommended upgrade):**
- Add off-site backup to cloud storage:
  - **Restic + Backblaze B2** (~$1-3/month)
  - **rclone + S3** (~$2-5/month)
  - **Hetzner Storage Box** (€3.81/month, EU-based)

📚 **Complete guide:** See [BACKUP_GUIDE.md](BACKUP_GUIDE.md) for detailed documentation

---

## 💾 Legacy Backup Script (Database Only)

### Manual Backup:
```bash
cd /opt/cloudwaste
bash deployment/backup-db.sh
```

Backups are stored in `/opt/cloudwaste/backups/` and include:
- 📦 PostgreSQL database dump (compressed)
- 🔐 Encryption key (CRITICAL for credentials)
- 📋 Backup manifest with restore instructions

### Automated Daily Backups:

Add to crontab:
```bash
crontab -e

# Add this line (runs daily at 2 AM)
0 2 * * * /opt/cloudwaste/deployment/backup-db.sh >> /var/log/cloudwaste-backup.log 2>&1
```

### Restore from Backup:

See backup manifest file for specific restore instructions:
```bash
cat /opt/cloudwaste/backups/backup_manifest_TIMESTAMP.txt
```

**General restore process:**
```bash
# 1. Stop containers
docker compose -f deployment/docker-compose.prod.yml down

# 2. Restore encryption key
docker run --rm \
  -v cloudwaste_encryption_key:/data \
  -v /opt/cloudwaste/backups:/backup \
  alpine sh -c "cp /backup/encryption_key_TIMESTAMP.txt /data/.encryption_key"

# 3. Restore database
gunzip < /opt/cloudwaste/backups/db_backup_TIMESTAMP.sql.gz | \
  docker exec -i cloudwaste_postgres psql -U cloudwaste -d cloudwaste

# 4. Start containers
docker compose -f deployment/docker-compose.prod.yml up -d
```

---

## 🔐 Security Best Practices

### 1. Keep .env.prod Secure:
```bash
# Never commit to Git
chmod 600 /opt/cloudwaste/.env.prod

# Verify it's in .gitignore
grep "\.env\.prod" /opt/cloudwaste/.gitignore
```

### 2. Rotate Secrets Regularly:

Generate new secrets:
```bash
# Generate new secret
openssl rand -hex 32

# Update .env.prod
nano /opt/cloudwaste/.env.prod

# Restart services
docker compose -f deployment/docker-compose.prod.yml restart
```

### 3. Monitor Failed Login Attempts:
```bash
# Backend logs
docker logs cloudwaste_backend | grep "401\|403"
```

### 4. Update SSL Certificates:

Certificates auto-renew via cron, but you can manually renew:
```bash
sudo certbot renew
docker exec cloudwaste_nginx nginx -s reload
```

---

## 🐛 Troubleshooting

### Issue: Containers Keep Restarting

**Solution:**
```bash
# Check logs
docker logs cloudwaste_backend

# Common causes:
# - Missing .env.prod
# - Database connection failed
# - Port already in use
```

### Issue: SSL Certificate Error

**Solution:**
```bash
# Verify certificates exist
sudo ls -la /etc/letsencrypt/live/cutcosts.tech/

# Regenerate if missing
sudo certbot certonly --standalone -d cutcosts.tech -d www.cutcosts.tech
```

### Issue: Frontend Shows 502 Bad Gateway

**Solution:**
```bash
# Check if backend is healthy
docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health

# Restart nginx
docker compose -f deployment/docker-compose.prod.yml restart nginx
```

### Issue: Database Connection Error

**Solution:**
```bash
# Verify PostgreSQL is running
docker exec cloudwaste_postgres pg_isready -U cloudwaste

# Check credentials in .env.prod
cat /opt/cloudwaste/.env.prod | grep POSTGRES

# Restart database
docker compose -f deployment/docker-compose.prod.yml restart postgres
```

---

## 🔄 Rollback to Previous Version

If deployment fails, rollback to previous commit:

```bash
# On VPS
cd /opt/cloudwaste
git log --oneline  # Find previous commit hash
git reset --hard COMMIT_HASH
bash deployment/quick-deploy.sh
```

---

## 📊 Performance Optimization

### Monitor Container Resources:
```bash
docker stats --no-stream
```

### Scale Services (if needed):
```bash
# Edit docker-compose.prod.yml
# Change --workers 4 to --workers 8 for backend

docker compose -f deployment/docker-compose.prod.yml up -d --no-deps --build backend
```

### Database Optimization:
```bash
# Run VACUUM and ANALYZE
docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c "VACUUM ANALYZE;"
```

---

## 📝 Maintenance Checklist

**Daily:**
- ✅ Check application uptime: `curl https://cutcosts.tech/api/v1/health`
- ✅ Verify backups completed: `ls -lh /opt/cloudwaste/backups/`

**Weekly:**
- ✅ Review logs for errors: `docker logs cloudwaste_backend | grep ERROR`
- ✅ Check disk space: `df -h`
- ✅ Update Docker images: `docker compose -f deployment/docker-compose.prod.yml pull`

**Monthly:**
- ✅ Rotate secrets (JWT_SECRET, POSTGRES_PASSWORD)
- ✅ Review SSL certificate expiration: `sudo certbot certificates`
- ✅ Test backup restoration process

---

## 🆘 Emergency Contacts

**VPS Provider:** [Your VPS provider support]
**Domain Registrar:** [Your domain registrar]
**SSL Issues:** Let's Encrypt Community: https://community.letsencrypt.org/

---

## 📚 Additional Resources

- **Docker Compose Docs:** https://docs.docker.com/compose/
- **Nginx Docs:** https://nginx.org/en/docs/
- **Let's Encrypt:** https://letsencrypt.org/docs/
- **PostgreSQL Backups:** https://www.postgresql.org/docs/current/backup.html

---

**Last Updated:** 2025-10-29
**Deployment Version:** 1.2.0 (Added Portainer + Automated Backups)
