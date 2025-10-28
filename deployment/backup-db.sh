#!/bin/bash

# ============================================================================
# CloudWaste - Database Backup Script
# ============================================================================
#
# This script creates automated backups of the PostgreSQL database
# It includes:
#   - Full database dump (SQL)
#   - Encryption key backup (CRITICAL for credentials)
#   - Automatic rotation (keeps last 30 days)
#   - Compression to save space
#
# Usage:
#   Manual backup:
#     bash deployment/backup-db.sh
#
#   Automated daily backups (add to crontab):
#     crontab -e
#     0 2 * * * /opt/cloudwaste/deployment/backup-db.sh >> /var/log/cloudwaste-backup.log 2>&1
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
APP_DIR="/opt/cloudwaste"
BACKUP_DIR="$APP_DIR/backups"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
COMPOSE_FILE="$APP_DIR/deployment/docker-compose.prod.yml"

# Backup filenames
DB_BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql.gz"
ENCRYPTION_KEY_BACKUP="$BACKUP_DIR/encryption_key_$TIMESTAMP.txt"
BACKUP_MANIFEST="$BACKUP_DIR/backup_manifest_$TIMESTAMP.txt"

# ============================================================================
# Helper Functions
# ============================================================================

print_step() {
    echo -e "${GREEN}▶${NC} $1"
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

# ============================================================================
# Pre-flight Checks
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         💾 CloudWaste Database Backup                              ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         $(date '+%Y-%m-%d %H:%M:%S')                                          ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    print_error "Docker is not running"
    exit 1
fi

# Check if PostgreSQL container is running
if ! docker ps | grep -q cloudwaste_postgres; then
    print_error "PostgreSQL container is not running"
    exit 1
fi

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Create Backup Directory
# ============================================================================

print_step "Creating backup directory..."

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"  # Secure: only owner can read/write

print_success "Backup directory: $BACKUP_DIR"

# ============================================================================
# Step 2: Backup PostgreSQL Database
# ============================================================================

print_step "Creating database backup..."

# Get database credentials from .env.prod
if [ -f "$APP_DIR/.env.prod" ]; then
    source "$APP_DIR/.env.prod"
else
    print_error "Cannot find .env.prod file"
    exit 1
fi

# Create compressed database dump
docker exec cloudwaste_postgres pg_dump \
    -U "${POSTGRES_USER:-cloudwaste}" \
    -d "${POSTGRES_DB:-cloudwaste}" \
    --clean \
    --if-exists \
    --verbose \
    2>&1 | gzip > "$DB_BACKUP_FILE"

# Verify backup was created
if [ -f "$DB_BACKUP_FILE" ]; then
    BACKUP_SIZE=$(du -h "$DB_BACKUP_FILE" | cut -f1)
    print_success "Database backup created: $DB_BACKUP_FILE ($BACKUP_SIZE)"
else
    print_error "Failed to create database backup"
    exit 1
fi

# ============================================================================
# Step 3: Backup Encryption Key (CRITICAL)
# ============================================================================

print_step "Backing up encryption key..."

# Extract encryption key from Docker volume
ENCRYPTION_KEY_DATA=$(docker volume inspect cloudwaste_encryption_key --format '{{ .Mountpoint }}')

if [ -d "$ENCRYPTION_KEY_DATA" ]; then
    # Copy encryption key file
    sudo cp "$ENCRYPTION_KEY_DATA/.encryption_key" "$ENCRYPTION_KEY_BACKUP" 2>/dev/null || \
    docker run --rm \
        -v cloudwaste_encryption_key:/data \
        -v "$BACKUP_DIR:/backup" \
        alpine \
        sh -c "cp /data/.encryption_key /backup/encryption_key_$TIMESTAMP.txt"

    chmod 600 "$ENCRYPTION_KEY_BACKUP"  # Secure: only owner can read
    print_success "Encryption key backed up: $ENCRYPTION_KEY_BACKUP"
else
    print_warning "Could not backup encryption key (volume not found)"
fi

# ============================================================================
# Step 4: Create Backup Manifest
# ============================================================================

print_step "Creating backup manifest..."

cat > "$BACKUP_MANIFEST" <<EOF
CloudWaste Backup Manifest
==========================
Timestamp: $TIMESTAMP
Date: $(date)

Database Backup:
  File: $(basename "$DB_BACKUP_FILE")
  Size: $BACKUP_SIZE

Encryption Key:
  File: $(basename "$ENCRYPTION_KEY_BACKUP")
  Status: $([ -f "$ENCRYPTION_KEY_BACKUP" ] && echo "OK" || echo "MISSING")

Environment:
  Hostname: $(hostname)
  Docker Version: $(docker --version | head -n1)

Containers Running:
$(docker ps --format "  - {{.Names}} ({{.Status}})")

Database Info:
  PostgreSQL User: ${POSTGRES_USER:-cloudwaste}
  Database Name: ${POSTGRES_DB:-cloudwaste}

Backup Location: $BACKUP_DIR

To restore this backup:
  1. Stop all containers: docker compose -f deployment/docker-compose.prod.yml down
  2. Restore encryption key: docker run --rm -v cloudwaste_encryption_key:/data -v $BACKUP_DIR:/backup alpine sh -c "cp /backup/encryption_key_$TIMESTAMP.txt /data/.encryption_key"
  3. Restore database: gunzip < $DB_BACKUP_FILE | docker exec -i cloudwaste_postgres psql -U ${POSTGRES_USER:-cloudwaste} -d ${POSTGRES_DB:-cloudwaste}
  4. Start containers: docker compose -f deployment/docker-compose.prod.yml up -d
EOF

chmod 600 "$BACKUP_MANIFEST"
print_success "Backup manifest created: $BACKUP_MANIFEST"

# ============================================================================
# Step 5: Cleanup Old Backups
# ============================================================================

print_step "Cleaning up old backups (keeping last $RETENTION_DAYS days)..."

OLD_BACKUPS_COUNT=$(find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +$RETENTION_DAYS 2>/dev/null | wc -l)

if [ "$OLD_BACKUPS_COUNT" -gt 0 ]; then
    find "$BACKUP_DIR" -name "db_backup_*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "encryption_key_*.txt" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "backup_manifest_*.txt" -mtime +$RETENTION_DAYS -delete
    print_success "Removed $OLD_BACKUPS_COUNT old backup(s)"
else
    print_success "No old backups to remove"
fi

# ============================================================================
# Step 6: Backup Summary
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
echo "  📦 Database backup:    $BACKUP_SIZE"
echo "  🔐 Encryption key:     $([ -f "$ENCRYPTION_KEY_BACKUP" ] && echo "✓ Backed up" || echo "✗ Missing")"
echo "  📋 Manifest:           ✓ Created"
echo "  📁 Location:           $BACKUP_DIR"
echo ""

TOTAL_BACKUPS=$(ls -1 "$BACKUP_DIR"/db_backup_*.sql.gz 2>/dev/null | wc -l)
TOTAL_SIZE=$(du -sh "$BACKUP_DIR" 2>/dev/null | cut -f1)

echo "  📊 Total backups:      $TOTAL_BACKUPS"
echo "  💾 Total disk usage:   $TOTAL_SIZE"
echo ""

print_success "To restore this backup, see: $BACKUP_MANIFEST"

echo ""
echo -e "${YELLOW}⚠️  IMPORTANT: Store backups off-site for disaster recovery${NC}"
echo "   Consider using: S3, Google Drive, Backblaze, or rsync to remote server"
echo ""
