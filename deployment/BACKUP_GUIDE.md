# CloudWaste - Backup & Restore Guide

Complete guide for backing up and restoring your CloudWaste system.

---

## 📋 Table of Contents

1. [Overview](#overview)
2. [Backup Strategy](#backup-strategy)
3. [Setup Automated Backups](#setup-automated-backups)
4. [Manual Backup](#manual-backup)
5. [Restore from Backup](#restore-from-backup)
6. [Disaster Recovery](#disaster-recovery)
7. [Monitoring](#monitoring)
8. [Troubleshooting](#troubleshooting)

---

## 🎯 Overview

CloudWaste uses a **comprehensive local backup system** that protects:

### What Gets Backed Up:

- ✅ **PostgreSQL Database** (all tables, users, accounts, scans, resources)
- ✅ **Redis Database** (cache, celery results)
- ✅ **Encryption Key** (🔴 CRITICAL - required to decrypt cloud credentials)
- ✅ **Docker Volumes** (postgres_data, redis_data)
- ✅ **Configuration Files** (.env.prod, docker-compose.prod.yml, nginx.conf)
- ✅ **Git Repository State** (current branch, commit, changes)

### Backup Rotation:

| Type | Retention | Storage |
|------|-----------|---------|
| **Daily** | 7 days | `/opt/cloudwaste/backups/daily/` |
| **Weekly** | 4 weeks | `/opt/cloudwaste/backups/weekly/` |
| **Monthly** | 3 months | `/opt/cloudwaste/backups/monthly/` |

### Estimated Storage:

- **Per backup:** ~100-500MB (compressed)
- **Total (30 days):** ~2-5GB

---

## 🛡 Backup Strategy

CloudWaste follows the **3-2-1 backup rule** (partially):

```
Current Setup (MVP):
  ✅ 3 copies:  Original data + Daily backup + Weekly backup
  ✅ 2 locations: Live data (Docker volumes) + Backups (/opt/cloudwaste/backups)
  ❌ 1 off-site: Not implemented yet (local VPS only)

Recommended for Production:
  ✅ Add off-site backup: S3, Backblaze B2, Hetzner Storage Box
```

---

## ⚡ Setup Automated Backups

### Initial Setup (Run Once):

```bash
# Connect to VPS
ssh administrator@155.117.43.17

# Navigate to CloudWaste directory
cd /opt/cloudwaste

# Run setup script (requires sudo)
sudo bash deployment/setup-backup-cron.sh
```

### What This Does:

1. ✅ Creates cron job (runs daily at 3 AM)
2. ✅ Sets up log file (`/var/log/cloudwaste-backup.log`)
3. ✅ Configures log rotation (30 days)
4. ✅ Runs initial test backup
5. ✅ Verifies everything works

### Verify Setup:

```bash
# Check cron job is active
crontab -l | grep backup-full

# Check log file exists
ls -lh /var/log/cloudwaste-backup.log

# View recent backups
ls -lh /opt/cloudwaste/backups/daily/
```

---

## 🔧 Manual Backup

### Run Manual Backup:

```bash
cd /opt/cloudwaste
bash deployment/backup-full.sh
```

### What Happens:

1. 📊 **Pre-flight checks** (Docker running, containers up)
2. 💾 **Database dumps** (PostgreSQL custom format + Redis RDB)
3. 📦 **Volume backups** (tar.gz archives)
4. 🔐 **Encryption key** (secured copy)
5. ⚙️ **Configuration files** (env, docker-compose, nginx)
6. 📋 **Git state** (current branch, commit, status)
7. 📝 **Manifest generation** (MANIFEST.txt with restore instructions)
8. 🧹 **Cleanup old backups** (rotation applied)
9. ✅ **Integrity verification** (gzip test, file checks)

### Output:

```
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║  💾 CloudWaste Full System Backup (DAILY)                          ║
║  2025-10-29 03:00:15                                               ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

▶ Running pre-flight checks...
✓ Pre-flight checks passed

▶ Creating backup directory structure...
✓ Directory created: /opt/cloudwaste/backups/daily/backup_20251029_030015

▶ Backing up PostgreSQL database...
✓ PostgreSQL backed up: 45M

▶ Backing up Redis database...
✓ Redis backed up: 2.1M

[... continued ...]

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║         ✅ BACKUP COMPLETED SUCCESSFULLY                           ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

Backup Summary:
  Type:              daily
  Location:          /opt/cloudwaste/backups/daily/backup_20251029_030015
  Total Size:        52M

  📦 PostgreSQL:     45M
  📦 Redis:          2.1M
  🔐 Encryption Key: ✓ Secured
  ⚙️  Config Files:   128K
  📋 Git State:      master @ a3f8c21

  📊 Total Backups:  7 (daily: 7, weekly: 3, monthly: 2)
  💾 Total Space:    412M
```

---

## 🔄 Restore from Backup

### Interactive Restore:

```bash
cd /opt/cloudwaste
bash deployment/restore-full.sh
```

### Restore Process:

1. **List available backups** (daily, weekly, monthly)
2. **Select backup** by number
3. **View backup info** (manifest details)
4. **Safety confirmation** (warns about data overwrite)
5. **Choose restore mode:**
   - Full restore (recommended)
   - Database only
   - Configuration only
   - Encryption key only
6. **Stop containers** (docker compose down)
7. **Restore data** (volumes, configs, encryption key)
8. **Start containers** (docker compose up)
9. **Verify restoration** (health checks)

### Example Session:

```bash
$ bash deployment/restore-full.sh

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║  🔄 CloudWaste System Restore                                      ║
║  2025-10-29 15:30:42                                               ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

▶ Available backups:

Monthly Backups:
  [1] 20251001 030000 (156M)

Weekly Backups:
  [2] 20251027 030000 (148M)
  [3] 20251020 030000 (145M)

Daily Backups:
  [4] 20251029 030000 (52M)
  [5] 20251028 030000 (51M)
  [6] 20251027 030000 (50M)
  [7] 20251026 030000 (49M)

Select backup number to restore (or 'q' to quit): 4

▶ Backup Information:

  Timestamp: 20251029_030000
  Total Size: 52M
  PostgreSQL: 45M
  Redis: 2.1M
  Encryption Key: ✓ Secured

⚠️  WARNING: This will replace your current system data!

  Current running containers will be stopped
  Existing data will be overwritten
  This action cannot be undone without another backup

Are you sure you want to continue with the restore? [y/N]: y

▶ Restore Options:

  1) Full restore (recommended)
  2) Database only (PostgreSQL + Redis)
  3) Configuration only (.env.prod, docker-compose, nginx)
  4) Encryption key only

Select restore option [1-4]: 1

[... restoration process ...]

╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║         ✅ RESTORATION COMPLETED                                   ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝
```

### Restore with Path (Non-Interactive):

```bash
# Restore specific backup directly
bash deployment/restore-full.sh /opt/cloudwaste/backups/daily/backup_20251029_030000
```

---

## 🚨 Disaster Recovery

### Scenario: VPS Crashed / Data Corrupted

**If backups exist on same VPS:**

1. SSH to VPS
2. Run `bash deployment/restore-full.sh`
3. Select most recent backup
4. Choose "Full restore"
5. Verify application works

**If VPS is completely lost:**

⚠️ **Without off-site backup, data is UNRECOVERABLE**

This is why off-site backup is critical for production!

---

## 📊 Monitoring

### Check Backup Logs:

```bash
# View last backup
tail -100 /var/log/cloudwaste-backup.log

# Follow backup in real-time
tail -f /var/log/cloudwaste-backup.log

# Check for errors
grep -i error /var/log/cloudwaste-backup.log
```

### Verify Backups:

```bash
# List all backups with sizes
du -sh /opt/cloudwaste/backups/*/* | sort -h

# Count backups
find /opt/cloudwaste/backups -name "backup_*" -type d | wc -l

# Check backup integrity
cd /opt/cloudwaste/backups/daily/backup_LATEST/
cat MANIFEST.txt
```

### Disk Space Monitoring:

```bash
# Check available space
df -h /opt/cloudwaste/backups

# Check backup directory size
du -sh /opt/cloudwaste/backups
```

### Email Alerts (Optional):

Add email notifications for backup failures:

```bash
# Install mailutils
sudo apt-get install mailutils

# Modify cron job
crontab -e

# Change line to:
0 3 * * * /opt/cloudwaste/deployment/backup-full.sh >> /var/log/cloudwaste-backup.log 2>&1 || echo "CloudWaste backup failed on $(date)" | mail -s "BACKUP FAILED" your@email.com
```

---

## 🔍 Troubleshooting

### Backup Fails with "Docker not running"

**Solution:**
```bash
sudo systemctl start docker
sudo systemctl status docker
```

### Backup Fails with "Permission denied"

**Solution:**
```bash
# Fix backup directory permissions
sudo chown -R administrator:administrator /opt/cloudwaste/backups
sudo chmod 700 /opt/cloudwaste/backups
```

### Disk Space Full

**Solution:**
```bash
# Check disk usage
df -h

# Manually clean old backups
sudo rm -rf /opt/cloudwaste/backups/daily/backup_OLDEST_TIMESTAMP

# Or adjust retention in backup-full.sh (lines 206-218)
```

### Encryption Key Backup Fails

**Critical Issue!**

**Solution:**
```bash
# Manually backup encryption key
docker run --rm \
  -v deployment_encryption_key:/data \
  -v /opt/cloudwaste/backups:/backup \
  alpine \
  sh -c "cp /data/encryption.key /backup/MANUAL_encryption_key_$(date +%Y%m%d).txt"

# Secure the file
chmod 600 /opt/cloudwaste/backups/MANUAL_encryption_key_*.txt
```

### Restore Fails with "Container won't start"

**Solution:**
```bash
# Check container logs
docker logs cloudwaste_backend
docker logs cloudwaste_postgres

# Try starting containers one by one
docker compose -f deployment/docker-compose.prod.yml up -d postgres redis
sleep 10
docker compose -f deployment/docker-compose.prod.yml up -d backend
```

### Cron Job Not Running

**Solution:**
```bash
# Check cron service
sudo systemctl status cron

# Verify cron job exists
crontab -l | grep backup-full

# Check cron logs
sudo grep CRON /var/log/syslog | grep backup

# Test backup manually
sudo bash /opt/cloudwaste/deployment/backup-full.sh
```

---

## 📚 Best Practices

### ✅ DO:

1. **Test restores regularly** - At least monthly
2. **Monitor backup logs** - Check for failures
3. **Keep backups off-site** - For production (S3, Backblaze, etc.)
4. **Secure backup directory** - `chmod 700`, limit access
5. **Document your process** - Update this guide with your changes
6. **Verify backup integrity** - Check MANIFEST.txt
7. **Plan for disasters** - Have a DR runbook

### ❌ DON'T:

1. **Never commit backups to Git** - They contain secrets!
2. **Never delete encryption key backups** - Data is UNRECOVERABLE
3. **Never skip testing restores** - Untested backups = no backups
4. **Never ignore disk space** - Monitor regularly
5. **Never store only on VPS** - Single point of failure

---

## 🚀 Upgrade to Off-Site Backups

### When MVP is validated, upgrade to production-grade backups:

**Option 1: Restic + Backblaze B2** (Recommended)
- Encrypted, deduplicated, incremental
- ~$1-3/month for CloudWaste size
- Setup guide: https://restic.readthedocs.io/

**Option 2: rclone + S3/B2**
- Simple sync to cloud storage
- ~$2-5/month
- Setup guide: https://rclone.org/docs/

**Option 3: Hetzner Storage Box**
- Europe-based, RGPD compliant
- €3.81/month for 1TB
- SSH/rsync/borg access

See main README.md for detailed comparison.

---

## 📞 Support

**Having issues?**

1. Check logs: `tail -f /var/log/cloudwaste-backup.log`
2. Verify disk space: `df -h`
3. Test manually: `bash deployment/backup-full.sh`
4. Check this guide's Troubleshooting section

**Still stuck?**

- Check GitHub Issues: https://github.com/anthropics/claude-code/issues
- Review Docker logs: `docker logs cloudwaste_backend`

---

**Last Updated:** 2025-10-29
**Version:** 1.0.0 (Local Backup System)
