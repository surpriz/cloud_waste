#!/bin/bash

# ============================================================================
# CloudWaste - Full System Backup Script (Local)
# ============================================================================
#
# This script creates comprehensive automated backups of the entire CloudWaste
# system locally on the VPS. Perfect for MVP/development environments.
#
# What gets backed up:
#   - PostgreSQL database (compressed SQL dump)
#   - Redis database (RDB snapshot)
#   - Docker volumes (postgres_data, redis_data, encryption_key)
#   - Configuration files (.env.prod, docker-compose.prod.yml, nginx.conf)
#   - Git repository state
#
# Backup rotation:
#   - Daily: Last 7 days
#   - Weekly: Last 4 weeks (Sunday backups)
#   - Monthly: Last 3 months (1st of month backups)
#
# Usage:
#   Manual backup:
#     bash deployment/backup-full.sh
#
#   Automated daily backups (add to crontab):
#     0 3 * * * /opt/cloudwaste/deployment/backup-full.sh >> /var/log/cloudwaste-backup.log 2>&1
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/cloudwaste"
BACKUP_ROOT="$APP_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE_DAILY=$(date +%Y-%m-%d)
DAY_OF_WEEK=$(date +%u)  # 1=Monday, 7=Sunday
DAY_OF_MONTH=$(date +%d)

# Determine backup type
BACKUP_TYPE="daily"
if [ "$DAY_OF_WEEK" = "7" ]; then
    BACKUP_TYPE="weekly"
fi
if [ "$DAY_OF_MONTH" = "01" ]; then
    BACKUP_TYPE="monthly"
fi

BACKUP_DIR="$BACKUP_ROOT/$BACKUP_TYPE/backup_$TIMESTAMP"
COMPOSE_FILE="$APP_DIR/deployment/docker-compose.prod.yml"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  💾 CloudWaste Full System Backup (${BACKUP_TYPE^^})                     ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  $(date '+%Y-%m-%d %H:%M:%S')                                          ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}▶${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_info() {
    echo -e "  ${NC}$1${NC}"
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header

print_step "Running pre-flight checks..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running"
    exit 1
fi

# Check if containers are running
if ! docker ps | grep -q cloudwaste_postgres; then
    print_error "PostgreSQL container is not running"
    exit 1
fi

if ! docker ps | grep -q cloudwaste_redis; then
    print_warning "Redis container is not running (will skip Redis backup)"
fi

# Check available disk space (need at least 2GB free)
AVAILABLE_SPACE=$(df "$APP_DIR" 2>/dev/null | awk 'NR==2 {print $4}' || echo "0")
# Validate AVAILABLE_SPACE is a number
if [[ "$AVAILABLE_SPACE" =~ ^[0-9]+$ ]] && [ "$AVAILABLE_SPACE" -lt 2097152 ]; then  # 2GB in KB
    print_warning "Low disk space: $(df -h "$APP_DIR" | awk 'NR==2 {print $4}') available"
fi

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Create Backup Directory Structure
# ============================================================================

print_step "Creating backup directory structure..."

mkdir -p "$BACKUP_DIR"/{database,volumes,config,git}
chmod 700 "$BACKUP_DIR"  # Secure: only owner can read/write
chmod 700 "$BACKUP_ROOT"

print_success "Directory created: $BACKUP_DIR"

# ============================================================================
# Step 2: Load Environment Variables
# ============================================================================

print_step "Loading environment variables..."

if [ -f "$APP_DIR/.env.prod" ]; then
    source "$APP_DIR/.env.prod"
    print_success "Environment loaded"
else
    print_error "Cannot find .env.prod file"
    exit 1
fi

# ============================================================================
# Step 3: Backup PostgreSQL Database
# ============================================================================

print_step "Backing up PostgreSQL database..."

docker exec cloudwaste_postgres pg_dump \
    -U "${POSTGRES_USER:-cloudwaste}" \
    -d "${POSTGRES_DB:-cloudwaste}" \
    --clean \
    --if-exists \
    --format=custom \
    --verbose \
    > "$BACKUP_DIR/database/postgres_dump.pgdump" 2>&1

# Compress the dump
gzip "$BACKUP_DIR/database/postgres_dump.pgdump"

if [ -f "$BACKUP_DIR/database/postgres_dump.pgdump.gz" ]; then
    POSTGRES_SIZE=$(du -h "$BACKUP_DIR/database/postgres_dump.pgdump.gz" | cut -f1)
    print_success "PostgreSQL backed up: $POSTGRES_SIZE"
else
    print_error "Failed to backup PostgreSQL"
    exit 1
fi

# ============================================================================
# Step 4: Backup Redis Database
# ============================================================================

print_step "Backing up Redis database..."

if docker ps | grep -q cloudwaste_redis; then
    # Trigger Redis BGSAVE
    docker exec cloudwaste_redis redis-cli BGSAVE > /dev/null 2>&1
    sleep 2  # Wait for BGSAVE to complete

    # Copy RDB file
    docker cp cloudwaste_redis:/data/dump.rdb "$BACKUP_DIR/database/redis_dump.rdb" 2>/dev/null || \
    docker run --rm \
        -v deployment_redis_data:/data \
        -v "$BACKUP_DIR/database:/backup" \
        alpine \
        sh -c "cp /data/dump.rdb /backup/redis_dump.rdb 2>/dev/null || echo 'No Redis dump file found'" > /dev/null

    if [ -f "$BACKUP_DIR/database/redis_dump.rdb" ]; then
        gzip "$BACKUP_DIR/database/redis_dump.rdb"
        REDIS_SIZE=$(du -h "$BACKUP_DIR/database/redis_dump.rdb.gz" | cut -f1)
        print_success "Redis backed up: $REDIS_SIZE"
    else
        print_warning "Redis backup skipped (no data file)"
    fi
else
    print_warning "Redis container not running, skipping"
fi

# ============================================================================
# Step 5: Backup Encryption Key (CRITICAL)
# ============================================================================

print_step "Backing up encryption key..."

docker run --rm \
    -v deployment_encryption_key:/data \
    -v "$BACKUP_DIR/volumes:/backup" \
    alpine \
    sh -c "cp /data/encryption.key /backup/encryption_key.txt 2>/dev/null || exit 1"

if [ -f "$BACKUP_DIR/volumes/encryption_key.txt" ]; then
    chmod 600 "$BACKUP_DIR/volumes/encryption_key.txt"
    print_success "Encryption key backed up"
else
    print_error "CRITICAL: Failed to backup encryption key"
    exit 1
fi

# ============================================================================
# Step 6: Backup Docker Volumes
# ============================================================================

print_step "Backing up Docker volumes..."

# Backup postgres_data volume
docker run --rm \
    -v deployment_postgres_data:/data \
    -v "$BACKUP_DIR/volumes:/backup" \
    alpine \
    tar czf /backup/postgres_data.tar.gz -C /data . 2>/dev/null

if [ -f "$BACKUP_DIR/volumes/postgres_data.tar.gz" ]; then
    PGDATA_SIZE=$(du -h "$BACKUP_DIR/volumes/postgres_data.tar.gz" | cut -f1)
    print_success "PostgreSQL data volume backed up: $PGDATA_SIZE"
fi

# Backup redis_data volume
docker run --rm \
    -v deployment_redis_data:/data \
    -v "$BACKUP_DIR/volumes:/backup" \
    alpine \
    tar czf /backup/redis_data.tar.gz -C /data . 2>/dev/null

if [ -f "$BACKUP_DIR/volumes/redis_data.tar.gz" ]; then
    REDISDATA_SIZE=$(du -h "$BACKUP_DIR/volumes/redis_data.tar.gz" | cut -f1)
    print_success "Redis data volume backed up: $REDISDATA_SIZE"
fi

# ============================================================================
# Step 7: Backup Configuration Files
# ============================================================================

print_step "Backing up configuration files..."

# Backup .env.prod (sensitive!)
if [ -f "$APP_DIR/.env.prod" ]; then
    cp "$APP_DIR/.env.prod" "$BACKUP_DIR/config/env.prod"
    chmod 600 "$BACKUP_DIR/config/env.prod"
    print_success "Environment file backed up"
fi

# Backup docker-compose
if [ -f "$COMPOSE_FILE" ]; then
    cp "$COMPOSE_FILE" "$BACKUP_DIR/config/docker-compose.prod.yml"
    print_success "Docker Compose file backed up"
fi

# Backup nginx config
if [ -f "$APP_DIR/deployment/nginx.conf" ]; then
    cp "$APP_DIR/deployment/nginx.conf" "$BACKUP_DIR/config/nginx.conf"
    print_success "Nginx config backed up"
fi

# Create tarball of all configs
tar czf "$BACKUP_DIR/config/all_configs.tar.gz" -C "$BACKUP_DIR/config" . 2>/dev/null
CONFIG_SIZE=$(du -h "$BACKUP_DIR/config/all_configs.tar.gz" | cut -f1)

# ============================================================================
# Step 8: Backup Git Repository State
# ============================================================================

print_step "Backing up Git repository state..."

cd "$APP_DIR"

# Get current git info
GIT_BRANCH=$(git branch --show-current 2>/dev/null || echo "unknown")
GIT_COMMIT=$(git rev-parse HEAD 2>/dev/null || echo "unknown")
GIT_DIRTY=$(git diff --quiet 2>/dev/null || echo "dirty")

# Save git info
cat > "$BACKUP_DIR/git/git_info.txt" <<EOF
Branch: $GIT_BRANCH
Commit: $GIT_COMMIT
Status: $GIT_DIRTY
Date: $(date)

Last 5 commits:
$(git log --oneline -5 2>/dev/null || echo "Git log unavailable")

Remote URL:
$(git remote get-url origin 2>/dev/null || echo "No remote")
EOF

print_success "Git state saved: $GIT_BRANCH @ $GIT_COMMIT"

# ============================================================================
# Step 9: Create Backup Manifest
# ============================================================================

print_step "Creating backup manifest..."

# Calculate total backup size
TOTAL_BACKUP_SIZE=$(du -sh "$BACKUP_DIR" | cut -f1)

cat > "$BACKUP_DIR/MANIFEST.txt" <<EOF
╔════════════════════════════════════════════════════════════════════╗
║                                                                    ║
║              CloudWaste Backup Manifest                            ║
║              Type: $BACKUP_TYPE                                           ║
║                                                                    ║
╚════════════════════════════════════════════════════════════════════╝

Backup Information:
==================
Timestamp: $TIMESTAMP
Date: $(date)
Type: $BACKUP_TYPE
Location: $BACKUP_DIR
Total Size: $TOTAL_BACKUP_SIZE

System Information:
==================
Hostname: $(hostname)
Docker Version: $(docker --version | head -n1)
OS: $(uname -a)

Database Backups:
================
✓ PostgreSQL dump: $POSTGRES_SIZE (database/postgres_dump.pgdump.gz)
$([ -f "$BACKUP_DIR/database/redis_dump.rdb.gz" ] && echo "✓ Redis dump: $REDIS_SIZE (database/redis_dump.rdb.gz)" || echo "⚠ Redis: Skipped")

Docker Volumes:
==============
✓ PostgreSQL data: $PGDATA_SIZE (volumes/postgres_data.tar.gz)
$([ -f "$BACKUP_DIR/volumes/redis_data.tar.gz" ] && echo "✓ Redis data: $REDISDATA_SIZE (volumes/redis_data.tar.gz)" || echo "⚠ Redis data: Skipped")
✓ Encryption key: CRITICAL (volumes/encryption_key.txt)

Configuration Files:
===================
✓ Environment: env.prod
✓ Docker Compose: docker-compose.prod.yml
✓ Nginx: nginx.conf
✓ All configs tarball: $CONFIG_SIZE

Git Repository:
==============
Branch: $GIT_BRANCH
Commit: $GIT_COMMIT
Status: $GIT_DIRTY

Database Configuration:
======================
PostgreSQL User: ${POSTGRES_USER:-cloudwaste}
Database Name: ${POSTGRES_DB:-cloudwaste}

Running Containers:
==================
$(docker ps --format "  - {{.Names}} ({{.Status}})")

═══════════════════════════════════════════════════════════════════

RESTORE INSTRUCTIONS:
====================

To restore this backup, use the restore script:

  bash deployment/restore-full.sh

Or manually:

1. Stop all containers:
   docker compose -f deployment/docker-compose.prod.yml down

2. Restore encryption key:
   docker run --rm -v deployment_encryption_key:/data \\
     -v $BACKUP_DIR/volumes:/backup alpine \\
     sh -c "cp /backup/encryption_key.txt /data/encryption.key"

3. Restore PostgreSQL data volume:
   docker run --rm -v deployment_postgres_data:/data \\
     -v $BACKUP_DIR/volumes:/backup alpine \\
     sh -c "cd /data && tar xzf /backup/postgres_data.tar.gz"

4. Restore Redis data volume (optional):
   docker run --rm -v deployment_redis_data:/data \\
     -v $BACKUP_DIR/volumes:/backup alpine \\
     sh -c "cd /data && tar xzf /backup/redis_data.tar.gz"

5. Start containers:
   docker compose -f deployment/docker-compose.prod.yml up -d

═══════════════════════════════════════════════════════════════════

⚠️  IMPORTANT SECURITY NOTES:
   - This backup contains SENSITIVE DATA (passwords, encryption keys)
   - Protect this directory with chmod 700
   - Never commit backups to Git
   - Consider off-site backup for production

═══════════════════════════════════════════════════════════════════
EOF

chmod 600 "$BACKUP_DIR/MANIFEST.txt"
print_success "Manifest created: MANIFEST.txt"

# ============================================================================
# Step 10: Cleanup Old Backups
# ============================================================================

print_step "Cleaning up old backups..."

cleanup_old_backups() {
    local backup_type=$1
    local retention_days=$2
    local backup_path="$BACKUP_ROOT/$backup_type"

    if [ -d "$backup_path" ]; then
        local old_count=$(find "$backup_path" -maxdepth 1 -type d -name "backup_*" -mtime +$retention_days 2>/dev/null | wc -l)
        if [ "$old_count" -gt 0 ]; then
            find "$backup_path" -maxdepth 1 -type d -name "backup_*" -mtime +$retention_days -exec rm -rf {} \; 2>/dev/null
            print_info "Removed $old_count old $backup_type backup(s)"
        else
            print_info "No old $backup_type backups to remove"
        fi
    fi
}

# Cleanup with different retention periods
cleanup_old_backups "daily" 7      # Keep 7 days
cleanup_old_backups "weekly" 28    # Keep 4 weeks
cleanup_old_backups "monthly" 90   # Keep 3 months

print_success "Cleanup completed"

# ============================================================================
# Step 11: Verify Backup Integrity
# ============================================================================

print_step "Verifying backup integrity..."

INTEGRITY_OK=true

# Check critical files exist
if [ ! -f "$BACKUP_DIR/database/postgres_dump.pgdump.gz" ]; then
    print_error "PostgreSQL dump missing"
    INTEGRITY_OK=false
fi

if [ ! -f "$BACKUP_DIR/volumes/encryption_key.txt" ]; then
    print_error "Encryption key missing (CRITICAL)"
    INTEGRITY_OK=false
fi

if [ ! -f "$BACKUP_DIR/config/env.prod" ]; then
    print_error "Environment file missing"
    INTEGRITY_OK=false
fi

# Test gzip files integrity
for gzfile in $(find "$BACKUP_DIR" -name "*.gz"); do
    if ! gzip -t "$gzfile" 2>/dev/null; then
        print_error "Corrupted: $(basename $gzfile)"
        INTEGRITY_OK=false
    fi
done

if [ "$INTEGRITY_OK" = true ]; then
    print_success "Backup integrity verified"
else
    print_error "Backup integrity check failed!"
    exit 1
fi

# ============================================================================
# Step 12: Backup Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ BACKUP COMPLETED SUCCESSFULLY${NC}                          ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step "Backup Summary:"
echo ""
print_info "Type:              $BACKUP_TYPE"
print_info "Location:          $BACKUP_DIR"
print_info "Total Size:        $TOTAL_BACKUP_SIZE"
echo ""
print_info "📦 PostgreSQL:     $POSTGRES_SIZE"
$([ -f "$BACKUP_DIR/database/redis_dump.rdb.gz" ] && echo "print_info \"📦 Redis:          $REDIS_SIZE\"" || echo "print_warning \"  Redis:          Skipped\"")
print_info "🔐 Encryption Key: ✓ Secured"
print_info "⚙️  Config Files:   $CONFIG_SIZE"
print_info "📋 Git State:      $GIT_BRANCH @ ${GIT_COMMIT:0:7}"
echo ""

# Count backups
DAILY_COUNT=$(find "$BACKUP_ROOT/daily" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | wc -l)
WEEKLY_COUNT=$(find "$BACKUP_ROOT/weekly" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | wc -l)
MONTHLY_COUNT=$(find "$BACKUP_ROOT/monthly" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | wc -l)
TOTAL_BACKUPS=$((DAILY_COUNT + WEEKLY_COUNT + MONTHLY_COUNT))
TOTAL_BACKUP_SPACE=$(du -sh "$BACKUP_ROOT" 2>/dev/null | cut -f1)

print_info "📊 Total Backups:  $TOTAL_BACKUPS (daily: $DAILY_COUNT, weekly: $WEEKLY_COUNT, monthly: $MONTHLY_COUNT)"
print_info "💾 Total Space:    $TOTAL_BACKUP_SPACE"
echo ""

print_success "Backup manifest: $BACKUP_DIR/MANIFEST.txt"
print_success "To restore: bash deployment/restore-full.sh"

echo ""
