#!/bin/bash

# ============================================================================
# CloudWaste - Full System Restore Script
# ============================================================================
#
# This script provides an interactive guided restoration from local backups
#
# Features:
#   - Lists available backups
#   - Interactive backup selection
#   - Safety checks before restore
#   - Partial restore options (DB only, config only, etc.)
#   - Automatic container restart
#
# Usage:
#   bash deployment/restore-full.sh
#
#   Or with backup path:
#     bash deployment/restore-full.sh /opt/cloudwaste/backups/daily/backup_20251029_030000
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
COMPOSE_FILE="$APP_DIR/deployment/docker-compose.prod.yml"

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  🔄 CloudWaste System Restore                                      ${BLUE}║${NC}"
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

confirm() {
    local prompt="$1"
    local default="${2:-n}"

    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
        default_response="Y"
    else
        prompt="$prompt [y/N]: "
        default_response="N"
    fi

    echo -ne "${YELLOW}$prompt${NC}"
    read -r response
    response=${response:-$default_response}

    if [[ "$response" =~ ^[Yy]$ ]]; then
        return 0
    else
        return 1
    fi
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

# Check if backup directory exists
if [ ! -d "$BACKUP_ROOT" ]; then
    print_error "Backup directory not found: $BACKUP_ROOT"
    exit 1
fi

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: List Available Backups
# ============================================================================

list_backups() {
    echo ""
    print_step "Available backups:"
    echo ""

    local i=1
    declare -A backup_map

    # List monthly backups
    if [ -d "$BACKUP_ROOT/monthly" ]; then
        local monthly_backups=$(find "$BACKUP_ROOT/monthly" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | sort -r)
        if [ -n "$monthly_backups" ]; then
            echo -e "${GREEN}Monthly Backups:${NC}"
            while IFS= read -r backup_path; do
                if [ -d "$backup_path" ]; then
                    local backup_name=$(basename "$backup_path")
                    local backup_date=$(echo "$backup_name" | sed 's/backup_//' | sed 's/_/ /')
                    local backup_size=$(du -sh "$backup_path" 2>/dev/null | cut -f1)
                    echo -e "  ${CYAN}[$i]${NC} $backup_date (${backup_size})"
                    backup_map[$i]="$backup_path"
                    ((i++))
                fi
            done <<< "$monthly_backups"
            echo ""
        fi
    fi

    # List weekly backups
    if [ -d "$BACKUP_ROOT/weekly" ]; then
        local weekly_backups=$(find "$BACKUP_ROOT/weekly" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | sort -r)
        if [ -n "$weekly_backups" ]; then
            echo -e "${GREEN}Weekly Backups:${NC}"
            while IFS= read -r backup_path; do
                if [ -d "$backup_path" ]; then
                    local backup_name=$(basename "$backup_path")
                    local backup_date=$(echo "$backup_name" | sed 's/backup_//' | sed 's/_/ /')
                    local backup_size=$(du -sh "$backup_path" 2>/dev/null | cut -f1)
                    echo -e "  ${CYAN}[$i]${NC} $backup_date (${backup_size})"
                    backup_map[$i]="$backup_path"
                    ((i++))
                fi
            done <<< "$weekly_backups"
            echo ""
        fi
    fi

    # List daily backups
    if [ -d "$BACKUP_ROOT/daily" ]; then
        local daily_backups=$(find "$BACKUP_ROOT/daily" -maxdepth 1 -type d -name "backup_*" 2>/dev/null | sort -r)
        if [ -n "$daily_backups" ]; then
            echo -e "${GREEN}Daily Backups:${NC}"
            while IFS= read -r backup_path; do
                if [ -d "$backup_path" ]; then
                    local backup_name=$(basename "$backup_path")
                    local backup_date=$(echo "$backup_name" | sed 's/backup_//' | sed 's/_/ /')
                    local backup_size=$(du -sh "$backup_path" 2>/dev/null | cut -f1)
                    echo -e "  ${CYAN}[$i]${NC} $backup_date (${backup_size})"
                    backup_map[$i]="$backup_path"
                    ((i++))
                fi
            done <<< "$daily_backups"
            echo ""
        fi
    fi

    if [ ${#backup_map[@]} -eq 0 ]; then
        print_error "No backups found in $BACKUP_ROOT"
        exit 1
    fi

    # Return backup map as serialized string
    for key in "${!backup_map[@]}"; do
        echo "$key:${backup_map[$key]}"
    done
}

# ============================================================================
# Step 2: Select Backup
# ============================================================================

# Check if backup path was provided as argument
if [ -n "$1" ]; then
    BACKUP_DIR="$1"
    if [ ! -d "$BACKUP_DIR" ]; then
        print_error "Backup directory not found: $BACKUP_DIR"
        exit 1
    fi
    print_info "Using backup: $BACKUP_DIR"
else
    # Interactive selection
    backup_list=$(list_backups)

    declare -A backup_map
    while IFS=: read -r num path; do
        backup_map[$num]="$path"
    done <<< "$backup_list"

    echo -ne "${YELLOW}Select backup number to restore (or 'q' to quit): ${NC}"
    read -r selection

    if [ "$selection" = "q" ] || [ "$selection" = "Q" ]; then
        echo "Restore cancelled."
        exit 0
    fi

    BACKUP_DIR="${backup_map[$selection]}"

    if [ -z "$BACKUP_DIR" ] || [ ! -d "$BACKUP_DIR" ]; then
        print_error "Invalid selection"
        exit 1
    fi
fi

# ============================================================================
# Step 3: Display Backup Information
# ============================================================================

print_step "Backup Information:"
echo ""

if [ -f "$BACKUP_DIR/MANIFEST.txt" ]; then
    # Extract key information from manifest
    grep -E "(Timestamp|Total Size|PostgreSQL|Redis|Encryption)" "$BACKUP_DIR/MANIFEST.txt" | while read -r line; do
        print_info "$line"
    done
else
    print_warning "Manifest file not found"
fi

echo ""

# ============================================================================
# Step 4: Safety Confirmation
# ============================================================================

print_warning "⚠️  WARNING: This will replace your current system data!"
echo ""
print_info "Current running containers will be stopped"
print_info "Existing data will be overwritten"
print_info "This action cannot be undone without another backup"
echo ""

if ! confirm "Are you sure you want to continue with the restore?" "n"; then
    echo "Restore cancelled."
    exit 0
fi

echo ""

# ============================================================================
# Step 5: Restore Options
# ============================================================================

print_step "Restore Options:"
echo ""
echo "  1) Full restore (recommended)"
echo "  2) Database only (PostgreSQL + Redis)"
echo "  3) Configuration only (.env.prod, docker-compose, nginx)"
echo "  4) Encryption key only"
echo ""

echo -ne "${YELLOW}Select restore option [1-4]: ${NC}"
read -r restore_option

case $restore_option in
    1) RESTORE_MODE="full" ;;
    2) RESTORE_MODE="database" ;;
    3) RESTORE_MODE="config" ;;
    4) RESTORE_MODE="encryption" ;;
    *)
        print_error "Invalid option"
        exit 1
        ;;
esac

echo ""

# ============================================================================
# Step 6: Stop Containers
# ============================================================================

print_step "Stopping containers..."

docker compose -f "$COMPOSE_FILE" down

print_success "Containers stopped"

# ============================================================================
# Step 7: Restore Encryption Key
# ============================================================================

if [ "$RESTORE_MODE" = "full" ] || [ "$RESTORE_MODE" = "encryption" ]; then
    print_step "Restoring encryption key..."

    if [ -f "$BACKUP_DIR/volumes/encryption_key.txt" ]; then
        docker run --rm \
            -v deployment_encryption_key:/data \
            -v "$BACKUP_DIR/volumes:/backup" \
            alpine \
            sh -c "cp /backup/encryption_key.txt /data/encryption.key && chmod 600 /data/encryption.key"

        print_success "Encryption key restored"
    else
        print_error "Encryption key not found in backup"
        exit 1
    fi
fi

# ============================================================================
# Step 8: Restore Database Volumes
# ============================================================================

if [ "$RESTORE_MODE" = "full" ] || [ "$RESTORE_MODE" = "database" ]; then
    print_step "Restoring PostgreSQL data volume..."

    if [ -f "$BACKUP_DIR/volumes/postgres_data.tar.gz" ]; then
        docker run --rm \
            -v deployment_postgres_data:/data \
            -v "$BACKUP_DIR/volumes:/backup" \
            alpine \
            sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null || true; cd /data && tar xzf /backup/postgres_data.tar.gz"

        print_success "PostgreSQL data volume restored"
    else
        print_warning "PostgreSQL data volume not found in backup"
    fi

    print_step "Restoring Redis data volume..."

    if [ -f "$BACKUP_DIR/volumes/redis_data.tar.gz" ]; then
        docker run --rm \
            -v deployment_redis_data:/data \
            -v "$BACKUP_DIR/volumes:/backup" \
            alpine \
            sh -c "rm -rf /data/* /data/..?* /data/.[!.]* 2>/dev/null || true; cd /data && tar xzf /backup/redis_data.tar.gz"

        print_success "Redis data volume restored"
    else
        print_warning "Redis data volume not found in backup"
    fi
fi

# ============================================================================
# Step 9: Restore Configuration Files
# ============================================================================

if [ "$RESTORE_MODE" = "full" ] || [ "$RESTORE_MODE" = "config" ]; then
    print_step "Restoring configuration files..."

    # Restore .env.prod
    if [ -f "$BACKUP_DIR/config/env.prod" ]; then
        cp "$BACKUP_DIR/config/env.prod" "$APP_DIR/.env.prod"
        chmod 600 "$APP_DIR/.env.prod"
        print_success "Environment file restored"
    else
        print_warning ".env.prod not found in backup"
    fi

    # Restore docker-compose.prod.yml
    if [ -f "$BACKUP_DIR/config/docker-compose.prod.yml" ]; then
        cp "$BACKUP_DIR/config/docker-compose.prod.yml" "$APP_DIR/deployment/docker-compose.prod.yml"
        print_success "Docker Compose file restored"
    else
        print_warning "docker-compose.prod.yml not found in backup"
    fi

    # Restore nginx.conf
    if [ -f "$BACKUP_DIR/config/nginx.conf" ]; then
        cp "$BACKUP_DIR/config/nginx.conf" "$APP_DIR/deployment/nginx.conf"
        print_success "Nginx config restored"
    else
        print_warning "nginx.conf not found in backup"
    fi
fi

# ============================================================================
# Step 10: Start Containers
# ============================================================================

print_step "Starting containers..."

docker compose -f "$COMPOSE_FILE" up -d

print_step "Waiting for services to start..."
sleep 10

# ============================================================================
# Step 11: Verify Restoration
# ============================================================================

print_step "Verifying restoration..."

VERIFY_OK=true

# Check if containers are running
if ! docker ps | grep -q cloudwaste_backend; then
    print_error "Backend container not running"
    VERIFY_OK=false
fi

if ! docker ps | grep -q cloudwaste_postgres; then
    print_error "PostgreSQL container not running"
    VERIFY_OK=false
fi

if ! docker ps | grep -q cloudwaste_frontend; then
    print_error "Frontend container not running"
    VERIFY_OK=false
fi

# Check backend health
sleep 5
if docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
    print_success "Backend health check passed"
else
    print_warning "Backend health check failed (may need more time to start)"
fi

if [ "$VERIFY_OK" = true ]; then
    print_success "Restoration verified successfully"
else
    print_warning "Some verification checks failed"
fi

# ============================================================================
# Step 12: Restoration Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ RESTORATION COMPLETED${NC}                                   ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step "Restoration Summary:"
echo ""
print_info "Mode:           $RESTORE_MODE"
print_info "Backup Source:  $BACKUP_DIR"
print_info "Date:           $(date)"
echo ""

print_step "Running containers:"
docker ps --format "  - {{.Names}} ({{.Status}})" | grep cloudwaste

echo ""
print_success "Your CloudWaste system has been restored from backup"
echo ""
print_info "Next steps:"
print_info "  1. Verify your application: https://cutcosts.tech"
print_info "  2. Check logs: docker logs -f cloudwaste_backend"
print_info "  3. Test functionality thoroughly"
echo ""
