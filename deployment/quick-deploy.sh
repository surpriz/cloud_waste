#!/bin/bash

# ============================================================================
# CloudWaste - Quick Deploy Script
# ============================================================================
#
# This script performs a fast deployment of CloudWaste to production
# It's called by:
#   - GitHub Actions (automated on git push)
#   - Manual deployments on the VPS
#
# What it does:
#   1. Stop running containers
#   2. Rebuild images with latest code
#   3. Run database migrations
#   4. Start containers
#   5. Health checks
#
# Usage:
#   cd /opt/cloudwaste
#   bash deployment/quick-deploy.sh
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

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

# Check if we're in the right directory
if [ ! -f "$COMPOSE_FILE" ]; then
    print_error "Cannot find $COMPOSE_FILE"
    print_error "Make sure you're running this from $APP_DIR"
    exit 1
fi

# Check if .env.prod exists
if [ ! -f "$ENV_FILE" ]; then
    print_error "Cannot find $ENV_FILE"
    print_error "Run deployment/setup-server.sh first to generate environment file"
    exit 1
fi

print_success "Pre-flight checks passed"

# ============================================================================
# Step 1: Stop Running Containers
# ============================================================================

print_step "Stopping running containers..."

if docker compose -f "$COMPOSE_FILE" ps -q 2>/dev/null | grep -q .; then
    docker compose -f "$COMPOSE_FILE" down
    print_success "Containers stopped"
else
    print_warning "No running containers found"
fi

# ============================================================================
# Step 2: Rebuild Images
# ============================================================================

print_step "Building Docker images with latest code..."

# Build with no cache to ensure fresh build
docker compose -f "$COMPOSE_FILE" build --no-cache --parallel

print_success "Images built successfully"

# ============================================================================
# Step 3: Start Database Services
# ============================================================================

print_step "Starting database services..."

docker compose -f "$COMPOSE_FILE" up -d postgres redis

print_step "Waiting for databases to be ready..."
sleep 10

print_success "Database services started"

# ============================================================================
# Step 4: Run Database Migrations
# ============================================================================

print_step "Running database migrations..."

docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

print_success "Database migrations completed"

# ============================================================================
# Step 5: Start All Services
# ============================================================================

print_step "Starting all services..."

docker compose -f "$COMPOSE_FILE" up -d

print_step "Waiting for services to start..."
sleep 15

print_success "All services started"

# ============================================================================
# Step 6: Health Checks
# ============================================================================

print_step "Running health checks..."

MAX_RETRIES=30
RETRY_COUNT=0
BACKEND_HEALTHY=false
FRONTEND_HEALTHY=false

# Check backend health
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health 2>/dev/null; then
        BACKEND_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ "$BACKEND_HEALTHY" = true ]; then
    print_success "Backend is healthy"
else
    print_error "Backend health check failed"
    print_warning "Check logs: docker logs cloudwaste_backend"
fi

# Reset retry count
RETRY_COUNT=0

# Check frontend health
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec cloudwaste_frontend curl -f http://localhost:3000 2>/dev/null; then
        FRONTEND_HEALTHY=true
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ "$FRONTEND_HEALTHY" = true ]; then
    print_success "Frontend is healthy"
else
    print_error "Frontend health check failed"
    print_warning "Check logs: docker logs cloudwaste_frontend"
fi

# ============================================================================
# Step 7: Cleanup Old Images
# ============================================================================

print_step "Cleaning up old Docker images..."

docker image prune -f > /dev/null 2>&1

print_success "Cleanup completed"

# ============================================================================
# Deployment Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
if [ "$BACKEND_HEALTHY" = true ] && [ "$FRONTEND_HEALTHY" = true ]; then
    echo -e "${BLUE}║${NC}         ${GREEN}✅ DEPLOYMENT SUCCESSFUL${NC}                                  ${BLUE}║${NC}"
else
    echo -e "${BLUE}║${NC}         ${YELLOW}⚠️  DEPLOYMENT COMPLETED WITH WARNINGS${NC}                    ${BLUE}║${NC}"
fi
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Show running containers
print_step "Running containers:"
docker compose -f "$COMPOSE_FILE" ps

echo ""
echo -e "${GREEN}Quick commands:${NC}"
echo ""
echo "  View logs:"
echo "    ${YELLOW}docker logs -f cloudwaste_backend${NC}"
echo "    ${YELLOW}docker logs -f cloudwaste_frontend${NC}"
echo "    ${YELLOW}docker logs -f cloudwaste_celery_worker${NC}"
echo ""
echo "  Restart service:"
echo "    ${YELLOW}docker compose -f $COMPOSE_FILE restart backend${NC}"
echo ""
echo "  Open shell in container:"
echo "    ${YELLOW}docker exec -it cloudwaste_backend bash${NC}"
echo ""
echo "  View container stats:"
echo "    ${YELLOW}docker stats${NC}"
echo ""
echo -e "${GREEN}Your application is live at:${NC}"
echo "  🌐 https://cutcosts.tech"
echo "  📚 https://cutcosts.tech/api/docs"
echo ""

# Exit with appropriate code
if [ "$BACKEND_HEALTHY" = true ] && [ "$FRONTEND_HEALTHY" = true ]; then
    exit 0
else
    exit 1
fi
