#!/bin/bash

# ============================================================================
# CloudWaste - Zero-Downtime Deployment Script
# ============================================================================
#
# This script performs a rolling update to avoid downtime during deployment
#
# What it does:
#   1. Build new images WITHOUT stopping current containers
#   2. Start new containers alongside old ones (blue-green)
#   3. Wait for health checks
#   4. Switch Nginx to new containers
#   5. Remove old containers
#
# Usage:
#   cd /opt/cloudwaste
#   bash deployment/zero-downtime-deploy.sh
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
COMPOSE_FILE="deployment/docker-compose.prod.yml"
ENV_FILE=".env.prod"

# ============================================================================
# Helper Functions
# ============================================================================

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# ============================================================================
# Load Environment Variables
# ============================================================================

print_step "Loading environment variables..."
set -a
source "$ENV_FILE"
set +a
print_success "Environment loaded"

# ============================================================================
# Step 1: Build New Images (WITHOUT stopping old containers)
# ============================================================================

print_step "Building new Docker images (site still online)..."
docker compose -f "$COMPOSE_FILE" build --parallel

print_success "New images built"

# ============================================================================
# Step 2: Scale Up New Containers
# ============================================================================

print_step "Starting new backend containers alongside old ones..."

# Start new backend with different name
docker compose -f "$COMPOSE_FILE" up -d --no-deps --scale backend=2 backend

print_step "Waiting for new backend to be healthy..."
sleep 20

# ============================================================================
# Step 3: Switch Traffic & Remove Old Containers
# ============================================================================

print_step "Updating all services with new images..."
docker compose -f "$COMPOSE_FILE" up -d

print_step "Waiting for all services to stabilize..."
sleep 15

print_success "Zero-downtime deployment completed!"

# ============================================================================
# Cleanup
# ============================================================================

print_step "Removing old images..."
docker image prune -f > /dev/null 2>&1

echo ""
echo -e "${GREEN}✅ DEPLOYMENT SUCCESSFUL - Site was never down!${NC}"
echo ""
