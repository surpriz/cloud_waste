#!/bin/bash

# ============================================================================
# CloudWaste - Debug Last Deployment Script
# ============================================================================
#
# This script helps diagnose why the last deployment failed
#
# Usage:
#   ssh administrator@155.117.43.17
#   cd /opt/cloudwaste
#   bash deployment/debug-last-deployment.sh
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
# Section 1: Deployment History
# ============================================================================

print_section "1️⃣  Deployment History"

echo -e "${CYAN}Last 5 commits:${NC}"
git log --oneline -5

echo ""
echo -e "${CYAN}Current vs Stable:${NC}"
CURRENT_COMMIT=$(git rev-parse --short HEAD)
echo "Current commit: $CURRENT_COMMIT"

if [ -f ".last_stable_commit" ]; then
    STABLE_COMMIT=$(cat .last_stable_commit | cut -c1-7)
    echo "Stable commit:  $STABLE_COMMIT"

    if [ "$CURRENT_COMMIT" != "$STABLE_COMMIT" ]; then
        print_warning "System was ROLLED BACK from $CURRENT_COMMIT to $STABLE_COMMIT"
        echo ""
        echo "Commits that failed to deploy:"
        git log --oneline $STABLE_COMMIT..$CURRENT_COMMIT
    else
        print_ok "System is on stable version"
    fi
else
    print_warning "No .last_stable_commit file found"
fi

# ============================================================================
# Section 2: Container Status
# ============================================================================

print_section "2️⃣  Container Status"

docker compose -f deployment/docker-compose.prod.yml ps

echo ""
echo -e "${CYAN}Container IPs:${NC}"
docker inspect cloudwaste_backend | grep -A 5 '"Networks"' | grep '"IPAddress"' | head -1
docker inspect cloudwaste_nginx | grep -A 5 '"Networks"' | grep '"IPAddress"' | head -1

# ============================================================================
# Section 3: Nginx Configuration & DNS Cache
# ============================================================================

print_section "3️⃣  Nginx DNS Resolution"

echo -e "${CYAN}Testing Nginx → Backend connection:${NC}"

# Test from Nginx container
if docker exec cloudwaste_nginx wget -O- -q http://cloudwaste_backend:8000/api/v1/health 2>/dev/null; then
    print_ok "Nginx CAN reach backend via DNS name"
else
    print_error "Nginx CANNOT reach backend via DNS name"
fi

# Get backend IP from Docker
BACKEND_IP=$(docker inspect cloudwaste_backend | grep '"IPAddress"' | head -1 | awk '{print $2}' | tr -d '",')
echo ""
echo -e "${CYAN}Backend IP from Docker: $BACKEND_IP${NC}"

# Test from Nginx using IP directly
if docker exec cloudwaste_nginx wget -O- -q http://$BACKEND_IP:8000/api/v1/health 2>/dev/null; then
    print_ok "Nginx CAN reach backend via IP ($BACKEND_IP)"
else
    print_error "Nginx CANNOT reach backend via IP ($BACKEND_IP)"
fi

# ============================================================================
# Section 4: Public Health Checks
# ============================================================================

print_section "4️⃣  Public Health Checks"

echo -e "${CYAN}Testing from VPS host:${NC}"

# Frontend
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech || echo "000")
if [ "$FRONTEND_STATUS" = "200" ] || [ "$FRONTEND_STATUS" = "304" ]; then
    print_ok "Frontend: HTTP $FRONTEND_STATUS"
else
    print_error "Frontend: HTTP $FRONTEND_STATUS"
fi

# Backend API
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")
if [ "$API_STATUS" = "200" ]; then
    print_ok "Backend API: HTTP $API_STATUS"
else
    print_error "Backend API: HTTP $API_STATUS"
fi

# ============================================================================
# Section 5: Recent Nginx Logs
# ============================================================================

print_section "5️⃣  Recent Nginx Logs (errors only)"

echo -e "${CYAN}Nginx errors in last 100 lines:${NC}"
docker logs cloudwaste_nginx --tail 100 2>&1 | grep -i "error\|refused\|upstream" | tail -20 || echo "  No errors found"

# ============================================================================
# Section 6: Recent Backend Logs
# ============================================================================

print_section "6️⃣  Recent Backend Logs (last 30 lines)"

docker logs cloudwaste_backend --tail 30

# ============================================================================
# Section 7: Timing Analysis
# ============================================================================

print_section "7️⃣  Container Uptime"

echo -e "${CYAN}Container start times:${NC}"
docker ps --filter "name=cloudwaste" --format "table {{.Names}}\t{{.Status}}"

# ============================================================================
# Section 8: Recommendations
# ============================================================================

print_section "8️⃣  Recommendations"

echo -e "${CYAN}Based on the diagnostics above:${NC}"
echo ""

# Check if Nginx can reach backend
NGINX_CAN_REACH=$(docker exec cloudwaste_nginx wget -O- -q http://cloudwaste_backend:8000/api/v1/health 2>/dev/null && echo "yes" || echo "no")

if [ "$NGINX_CAN_REACH" = "no" ]; then
    echo "🔴 Problem: Nginx cannot reach backend"
    echo ""
    echo "Solutions:"
    echo "  1. Restart Nginx:"
    echo "     ${YELLOW}docker compose -f deployment/docker-compose.prod.yml restart nginx${NC}"
    echo ""
    echo "  2. Or restart all services:"
    echo "     ${YELLOW}docker compose -f deployment/docker-compose.prod.yml restart${NC}"
else
    if [ "$API_STATUS" != "200" ]; then
        echo "🟡 Problem: Nginx can reach backend internally, but public API fails"
        echo ""
        echo "This might be a timing issue. The health check might be running too early."
        echo ""
        echo "Solution: Increase timeout in zero-downtime-deploy.sh"
        echo "  Change: sleep 5  →  sleep 15"
    else
        echo "🟢 Everything looks healthy now!"
        echo ""
        echo "The issue might have been temporary or resolved automatically."
        echo "You can try deploying again."
    fi
fi

echo ""
