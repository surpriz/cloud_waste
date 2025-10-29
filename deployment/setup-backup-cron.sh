#!/bin/bash

# ============================================================================
# CloudWaste - Setup Automated Backup Cron Job
# ============================================================================
#
# This script configures automatic nightly backups via cron
#
# What it does:
#   - Creates cron job for daily backup at 3 AM
#   - Sets up logging
#   - Runs initial test backup
#   - Verifies everything works
#
# Usage:
#   bash deployment/setup-backup-cron.sh
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_DIR="/opt/cloudwaste"
BACKUP_SCRIPT="$APP_DIR/deployment/backup-full.sh"
LOG_FILE="/var/log/cloudwaste-backup.log"
CRON_SCHEDULE="0 3 * * *"  # 3 AM daily

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  ⏰ CloudWaste - Setup Automated Backups                           ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

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

print_info() {
    echo -e "  ${NC}$1${NC}"
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header

print_step "Running pre-flight checks..."

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root or with sudo"
    echo ""
    echo "Usage: sudo bash deployment/setup-backup-cron.sh"
    exit 1
fi

# Check if backup script exists
if [ ! -f "$BACKUP_SCRIPT" ]; then
    print_error "Backup script not found: $BACKUP_SCRIPT"
    exit 1
fi

# Make backup script executable
chmod +x "$BACKUP_SCRIPT"

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Setup Log File
# ============================================================================

print_step "Setting up log file..."

# Create log file if it doesn't exist
touch "$LOG_FILE"
chmod 644 "$LOG_FILE"

# Set ownership to root
chown root:root "$LOG_FILE"

print_success "Log file created: $LOG_FILE"

# ============================================================================
# Step 2: Configure Logrotate
# ============================================================================

print_step "Configuring log rotation..."

# Create logrotate config
cat > /etc/logrotate.d/cloudwaste-backup <<EOF
$LOG_FILE {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 644 root root
}
EOF

print_success "Logrotate configured (30 days retention)"

# ============================================================================
# Step 3: Setup Cron Job
# ============================================================================

print_step "Setting up cron job..."

# Remove existing CloudWaste backup cron jobs
crontab -l 2>/dev/null | grep -v "cloudwaste.*backup-full.sh" | crontab - || true

# Add new cron job
(crontab -l 2>/dev/null; echo "$CRON_SCHEDULE $BACKUP_SCRIPT >> $LOG_FILE 2>&1") | crontab -

print_success "Cron job added: Daily backup at 3:00 AM"

# ============================================================================
# Step 4: Verify Cron Job
# ============================================================================

print_step "Verifying cron configuration..."

if crontab -l | grep -q "backup-full.sh"; then
    print_success "Cron job verified"
else
    print_error "Failed to add cron job"
    exit 1
fi

# ============================================================================
# Step 5: Test Backup
# ============================================================================

print_step "Running initial test backup..."
echo ""

print_info "This may take a few minutes..."
echo ""

# Run backup script
if bash "$BACKUP_SCRIPT"; then
    echo ""
    print_success "Test backup completed successfully"
else
    echo ""
    print_error "Test backup failed"
    print_warning "Check logs: tail -f $LOG_FILE"
    exit 1
fi

# ============================================================================
# Step 6: Setup Complete
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ AUTOMATED BACKUPS CONFIGURED${NC}                            ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step "Configuration Summary:"
echo ""
print_info "📅 Schedule:        Daily at 3:00 AM"
print_info "📁 Backup Script:   $BACKUP_SCRIPT"
print_info "📋 Log File:        $LOG_FILE"
print_info "🔄 Log Rotation:    30 days"
echo ""

print_step "Backup Rotation:"
echo ""
print_info "• Daily backups:    Last 7 days"
print_info "• Weekly backups:   Last 4 weeks"
print_info "• Monthly backups:  Last 3 months"
echo ""

print_step "Useful Commands:"
echo ""
print_info "View cron jobs:     crontab -l"
print_info "View backup logs:   tail -f $LOG_FILE"
print_info "Manual backup:      bash $BACKUP_SCRIPT"
print_info "Restore backup:     bash $APP_DIR/deployment/restore-full.sh"
echo ""

print_step "Next Steps:"
echo ""
print_info "1. Backups will run automatically every night at 3 AM"
print_info "2. Monitor logs regularly: tail -f $LOG_FILE"
print_info "3. Test restore process: bash deployment/restore-full.sh"
print_info "4. Check backup directory: ls -lh $APP_DIR/backups/"
echo ""

print_warning "⚠️  IMPORTANT: Local backups only protect against data loss"
print_warning "   For production, consider off-site backups (S3, Backblaze, etc.)"
echo ""

print_success "Automated backups are now active!"
echo ""
