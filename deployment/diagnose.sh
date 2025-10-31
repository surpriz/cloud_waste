#!/bin/bash

# ============================================================================
# CloudWaste - Diagnostic Script
# ============================================================================
#
# This script diagnoses deployment and application issues
#
# Usage:
#   cd /opt/cloudwaste
#   bash deployment/diagnose.sh
#
# ============================================================================

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

print_section() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC} $1"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_ok() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

# ============================================================================
# Section 1: Git & Deployment Status
# ============================================================================

print_section "1️⃣  Git & Deployment Status"

CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo -e "Current commit: ${CYAN}$CURRENT_COMMIT${NC}"

if [ -f ".last_stable_commit" ]; then
    STABLE_COMMIT=$(cat .last_stable_commit | cut -c1-7)
    echo -e "Stable commit:  ${GREEN}$STABLE_COMMIT${NC}"

    if [ "$CURRENT_COMMIT" = "$STABLE_COMMIT" ]; then
        print_ok "System is on stable version"
    else
        print_warning "System is NOT on stable version (may have rolled back)"
    fi
else
    print_warning "No stable commit file found (.last_stable_commit)"
    print_info "This is normal for first deployment"
fi

git log --oneline -3

# ============================================================================
# Section 2: Docker Containers Status
# ============================================================================

print_section "2️⃣  Docker Containers Status"

docker compose -f deployment/docker-compose.prod.yml ps

echo ""
print_info "Container health status:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}" | grep cloudwaste

# ============================================================================
# Section 3: Health Checks
# ============================================================================

print_section "3️⃣  Health Checks"

# Backend internal health
print_info "Testing backend internal health..."
if docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health 2>/dev/null; then
    print_ok "Backend internal: HEALTHY"
else
    print_error "Backend internal: UNHEALTHY"
fi

# Frontend internal health
print_info "Testing frontend internal health..."
if docker exec cloudwaste_frontend curl -f http://localhost:3000 2>/dev/null; then
    print_ok "Frontend internal: HEALTHY"
else
    print_error "Frontend internal: UNHEALTHY"
fi

# External health checks
print_info "Testing public URLs..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech || echo "000")
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")

if [ "$FRONTEND_STATUS" = "200" ] || [ "$FRONTEND_STATUS" = "304" ]; then
    print_ok "Frontend public: OK (HTTP $FRONTEND_STATUS)"
else
    print_error "Frontend public: FAIL (HTTP $FRONTEND_STATUS)"
fi

if [ "$API_STATUS" = "200" ]; then
    print_ok "Backend API public: OK (HTTP $API_STATUS)"
else
    print_error "Backend API public: FAIL (HTTP $API_STATUS)"
fi

# ============================================================================
# Section 4: Database Status
# ============================================================================

print_section "4️⃣  Database Status"

# PostgreSQL connection
print_info "Testing PostgreSQL connection..."
if docker exec cloudwaste_postgres pg_isready -U cloudwaste 2>/dev/null; then
    print_ok "PostgreSQL: CONNECTED"
else
    print_error "PostgreSQL: NOT CONNECTED"
fi

# Redis connection
print_info "Testing Redis connection..."
if docker exec cloudwaste_redis redis-cli ping 2>/dev/null | grep -q "PONG"; then
    print_ok "Redis: CONNECTED"
else
    print_error "Redis: NOT CONNECTED"
fi

# Database tables
print_info "Checking database tables..."
TABLES=$(docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='public';" 2>/dev/null | tr -d ' ')
if [ ! -z "$TABLES" ] && [ "$TABLES" -gt 0 ]; then
    print_ok "Database has $TABLES tables"
else
    print_error "Database appears empty"
fi

# ============================================================================
# Section 5: User Account Check
# ============================================================================

print_section "5️⃣  User Account Check"

print_info "Checking for user: jerome0laval@gmail.com"

USER_INFO=$(docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -t -c "SELECT id, email, is_active, is_superuser, created_at FROM users WHERE email='jerome0laval@gmail.com';" 2>/dev/null)

if [ ! -z "$USER_INFO" ]; then
    print_ok "User found in database"
    echo "$USER_INFO"

    IS_ACTIVE=$(docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -t -c "SELECT is_active FROM users WHERE email='jerome0laval@gmail.com';" 2>/dev/null | tr -d ' ')

    if [ "$IS_ACTIVE" = "t" ]; then
        print_ok "User is ACTIVE"
    else
        print_error "User is INACTIVE (is_active=false)"
        print_warning "To activate user, run:"
        echo "  bash deployment/activate-user.sh jerome0laval@gmail.com"
    fi
else
    print_error "User NOT FOUND in database"
    print_warning "You may need to create an account first"
fi

# Count total users
USER_COUNT=$(docker exec cloudwaste_postgres psql -U cloudwaste -d cloudwaste -t -c "SELECT COUNT(*) FROM users;" 2>/dev/null | tr -d ' ')
print_info "Total users in database: $USER_COUNT"

# ============================================================================
# Section 6: Recent Backend Logs
# ============================================================================

print_section "6️⃣  Recent Backend Logs (last 50 lines)"

docker logs cloudwaste_backend --tail 50

# ============================================================================
# Section 7: Recent Errors
# ============================================================================

print_section "7️⃣  Recent Errors (all containers)"

echo -e "${CYAN}Backend errors:${NC}"
docker logs cloudwaste_backend --tail 100 2>&1 | grep -i "error\|exception\|fail" | tail -10 || echo "  No errors found"

echo ""
echo -e "${CYAN}Frontend errors:${NC}"
docker logs cloudwaste_frontend --tail 100 2>&1 | grep -i "error\|exception\|fail" | tail -10 || echo "  No errors found"

echo ""
echo -e "${CYAN}Celery worker errors:${NC}"
docker logs cloudwaste_celery_worker --tail 100 2>&1 | grep -i "error\|exception\|fail" | tail -10 || echo "  No errors found"

# ============================================================================
# Section 8: Resource Usage
# ============================================================================

print_section "8️⃣  Resource Usage"

docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}" | grep cloudwaste

# ============================================================================
# Section 9: Disk Space
# ============================================================================

print_section "9️⃣  Disk Space"

df -h /opt/cloudwaste
echo ""
df -h /var/lib/docker

# ============================================================================
# Summary & Recommendations
# ============================================================================

print_section "📊 Summary & Recommendations"

echo -e "${CYAN}Quick Actions:${NC}"
echo ""
echo "View detailed logs:"
echo "  ${YELLOW}docker logs -f cloudwaste_backend${NC}"
echo "  ${YELLOW}docker logs -f cloudwaste_frontend${NC}"
echo ""
echo "Restart a service:"
echo "  ${YELLOW}docker compose -f deployment/docker-compose.prod.yml restart backend${NC}"
echo ""
echo "Access database:"
echo "  ${YELLOW}docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste${NC}"
echo ""
echo "Activate user:"
echo "  ${YELLOW}bash deployment/activate-user.sh jerome0laval@gmail.com${NC}"
echo ""
echo "Re-deploy:"
echo "  ${YELLOW}bash deployment/zero-downtime-deploy.sh${NC}"
echo ""
