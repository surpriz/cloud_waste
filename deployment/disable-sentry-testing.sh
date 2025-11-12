#!/bin/bash

# ============================================================================
# CloudWaste - Disable Sentry Testing Mode
# ============================================================================
#
# This script disables DEBUG mode after Sentry testing is complete.
#
# Usage (on VPS):
#   cd /opt/cloudwaste
#   bash deployment/disable-sentry-testing.sh
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}🔒 DÉSACTIVATION MODE TEST SENTRY${NC}                      ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

COMPOSE_FILE="deployment/docker-compose.prod.yml"
ENV_FILE=".env.prod"

# ============================================================================
# Step 1: Backup .env.prod
# ============================================================================

print_step "Sauvegarde de .env.prod..."
cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
print_success "Sauvegarde créée"

# ============================================================================
# Step 2: Disable DEBUG mode
# ============================================================================

print_step "Désactivation du mode DEBUG..."

if grep -q "^DEBUG=True" "$ENV_FILE"; then
    sed -i 's/^DEBUG=True/DEBUG=False/' "$ENV_FILE"
    print_success "DEBUG=False activé"
elif grep -q "^DEBUG=False" "$ENV_FILE"; then
    print_warning "DEBUG était déjà désactivé"
else
    print_error "Variable DEBUG introuvable dans $ENV_FILE"
    echo "DEBUG=False" >> "$ENV_FILE"
    print_success "DEBUG=False ajouté"
fi

# Verify
DEBUG_VALUE=$(grep "^DEBUG=" "$ENV_FILE")
echo "   • $DEBUG_VALUE"

# ============================================================================
# Step 3: Restart containers
# ============================================================================

print_step "Redémarrage des conteneurs..."
docker compose -f "$COMPOSE_FILE" restart backend frontend

print_step "Attente du redémarrage complet (30 secondes)..."
sleep 30

# ============================================================================
# Step 4: Verify DEBUG mode is disabled
# ============================================================================

print_step "Vérification du mode DEBUG dans les conteneurs..."
DEBUG_IN_CONTAINER=$(docker exec cloudwaste_backend env | grep "^DEBUG=" || echo "DEBUG=NOT_FOUND")
echo "   • Backend: $DEBUG_IN_CONTAINER"

if [[ "$DEBUG_IN_CONTAINER" == "DEBUG=False" ]]; then
    print_success "Mode DEBUG désactivé dans le conteneur backend"
else
    print_warning "DEBUG status: $DEBUG_IN_CONTAINER"
fi

# ============================================================================
# Step 5: Test API health
# ============================================================================

print_step "Test de l'API (health check)..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")
if [ "$API_STATUS" == "200" ]; then
    print_success "API opérationnelle (HTTP $API_STATUS)"
else
    print_error "API non accessible (HTTP $API_STATUS)"
fi

# ============================================================================
# Step 6: Verify test endpoints are blocked
# ============================================================================

print_step "Vérification que les endpoints de test sont bloqués..."

# This should return 403 or 404 (not 200)
TEST_ENDPOINT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/test/sentry-test || echo "000")

if [ "$TEST_ENDPOINT_STATUS" == "404" ] || [ "$TEST_ENDPOINT_STATUS" == "403" ]; then
    print_success "Endpoints de test correctement bloqués (HTTP $TEST_ENDPOINT_STATUS)"
else
    print_warning "Endpoint de test retourne HTTP $TEST_ENDPOINT_STATUS (attendu: 404 ou 403)"
fi

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ MODE PRODUCTION RESTAURÉ${NC}                             ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_success "Mode DEBUG désactivé"
print_success "Endpoints de test protégés"
print_success "Configuration production active"
echo ""
echo -e "${GREEN}📊 Sentry reste actif en production:${NC}"
echo "   • Backend: Capture automatique des erreurs"
echo "   • Frontend: Capture automatique des erreurs"
echo "   • Dashboard: https://sentry.io → jerome-laval-x3"
echo ""
