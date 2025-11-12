#!/bin/bash

# ============================================================================
# CloudWaste - Enable Sentry Testing Mode
# ============================================================================
#
# This script enables DEBUG mode and verifies Sentry configuration
# for testing Sentry integration in production.
#
# Usage (on VPS):
#   cd /opt/cloudwaste
#   bash deployment/enable-sentry-testing.sh
#
# ⚠️ WARNING: DEBUG mode exposes test endpoints. Disable after testing!
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
echo -e "${BLUE}║${NC}         ${GREEN}🧪 ACTIVATION MODE TEST SENTRY${NC}                         ${BLUE}║${NC}"
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
# Step 2: Enable DEBUG mode
# ============================================================================

print_step "Activation du mode DEBUG..."

if grep -q "^DEBUG=False" "$ENV_FILE"; then
    sed -i 's/^DEBUG=False/DEBUG=True/' "$ENV_FILE"
    print_success "DEBUG=True activé"
elif grep -q "^DEBUG=True" "$ENV_FILE"; then
    print_warning "DEBUG était déjà activé"
else
    print_error "Variable DEBUG introuvable dans $ENV_FILE"
    echo "DEBUG=True" >> "$ENV_FILE"
    print_success "DEBUG=True ajouté"
fi

# Verify
DEBUG_VALUE=$(grep "^DEBUG=" "$ENV_FILE")
echo "   • $DEBUG_VALUE"

# ============================================================================
# Step 3: Verify Sentry variables
# ============================================================================

print_step "Vérification des variables Sentry..."
echo ""

echo "=== Variables Sentry Backend ==="
BACKEND_SENTRY_COUNT=$(grep "^SENTRY" "$ENV_FILE" | grep -v "NEXT_PUBLIC" | wc -l | tr -d ' ')
if [ "$BACKEND_SENTRY_COUNT" -eq 4 ]; then
    print_success "4 variables backend trouvées"
    grep "^SENTRY" "$ENV_FILE" | grep -v "NEXT_PUBLIC"
else
    print_warning "Seulement $BACKEND_SENTRY_COUNT variables backend (attendu: 4)"
    grep "^SENTRY" "$ENV_FILE" | grep -v "NEXT_PUBLIC" || echo "Aucune"
fi

echo ""
echo "=== Variables Sentry Frontend ==="
FRONTEND_SENTRY_COUNT=$(grep "^NEXT_PUBLIC_SENTRY" "$ENV_FILE" | wc -l | tr -d ' ')
if [ "$FRONTEND_SENTRY_COUNT" -eq 2 ]; then
    print_success "2 variables frontend trouvées"
    grep "^NEXT_PUBLIC_SENTRY" "$ENV_FILE"
else
    print_warning "Seulement $FRONTEND_SENTRY_COUNT variables frontend (attendu: 2)"
    grep "^NEXT_PUBLIC_SENTRY" "$ENV_FILE" || echo "Aucune"
fi

echo ""

if [ "$BACKEND_SENTRY_COUNT" -ne 4 ] || [ "$FRONTEND_SENTRY_COUNT" -ne 2 ]; then
    print_warning "Variables Sentry manquantes détectées"
    print_step "Exécution du script de synchronisation Sentry..."
    bash deployment/sync-sentry-env.sh --local
fi

# ============================================================================
# Step 4: Pull latest code
# ============================================================================

print_step "Récupération du dernier code..."
git fetch origin master
git reset --hard origin/master
CURRENT_COMMIT=$(git rev-parse --short HEAD)
print_success "Code mis à jour vers commit: $CURRENT_COMMIT"

# ============================================================================
# Step 5: Restart containers with new configuration
# ============================================================================

print_step "Redémarrage des conteneurs avec la nouvelle configuration..."
docker compose -f "$COMPOSE_FILE" restart backend frontend

print_step "Attente du redémarrage complet (30 secondes)..."
sleep 30

# ============================================================================
# Step 6: Verify containers are running
# ============================================================================

print_step "Vérification de l'état des conteneurs..."
docker compose -f "$COMPOSE_FILE" ps | grep -E "(backend|frontend)"

# ============================================================================
# Step 7: Verify DEBUG mode in containers
# ============================================================================

print_step "Vérification du mode DEBUG dans les conteneurs..."
DEBUG_IN_CONTAINER=$(docker exec cloudwaste_backend env | grep "^DEBUG=" || echo "DEBUG=NOT_FOUND")
echo "   • Backend: $DEBUG_IN_CONTAINER"

if [[ "$DEBUG_IN_CONTAINER" == "DEBUG=True" ]]; then
    print_success "Mode DEBUG activé dans le conteneur backend"
else
    print_error "DEBUG n'est pas activé dans le conteneur (valeur: $DEBUG_IN_CONTAINER)"
    print_warning "Les conteneurs doivent être redémarrés pour charger les nouvelles variables"
fi

# ============================================================================
# Step 8: Verify Sentry variables in containers
# ============================================================================

print_step "Vérification des variables Sentry dans les conteneurs..."
echo ""

echo "=== Backend Sentry Variables ==="
docker exec cloudwaste_backend env | grep "^SENTRY" | grep -v "NEXT_PUBLIC" || echo "Aucune variable backend"

echo ""
echo "=== Frontend Sentry Variables ==="
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY" || echo "Aucune variable frontend"

# ============================================================================
# Step 9: Check Sentry initialization in logs
# ============================================================================

print_step "Vérification de l'initialisation Sentry dans les logs..."
echo ""

echo "=== Backend Logs (Sentry) ==="
BACKEND_SENTRY_INIT=$(docker logs cloudwaste_backend --tail 100 2>&1 | grep -i "sentry" | tail -5)
if [ -n "$BACKEND_SENTRY_INIT" ]; then
    echo "$BACKEND_SENTRY_INIT"
    print_success "Logs Sentry trouvés dans backend"
else
    print_warning "Aucun log Sentry trouvé dans backend (peut être normal si pas de log au démarrage)"
fi

echo ""
echo "=== Frontend Logs (Sentry) ==="
FRONTEND_SENTRY_INIT=$(docker logs cloudwaste_frontend --tail 100 2>&1 | grep -i "sentry" | tail -5)
if [ -n "$FRONTEND_SENTRY_INIT" ]; then
    echo "$FRONTEND_SENTRY_INIT"
    print_success "Logs Sentry trouvés dans frontend"
else
    print_warning "Aucun log Sentry trouvé dans frontend (peut être normal)"
fi

# ============================================================================
# Step 10: Test API health
# ============================================================================

print_step "Test de l'API (health check)..."
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")
if [ "$API_STATUS" == "200" ]; then
    print_success "API opérationnelle (HTTP $API_STATUS)"
else
    print_error "API non accessible (HTTP $API_STATUS)"
fi

# ============================================================================
# Step 11: Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ CONFIGURATION SENTRY TERMINÉE${NC}                        ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_success "Mode DEBUG activé pour les tests Sentry"
echo ""
echo -e "${GREEN}📋 Prochaines étapes:${NC}"
echo ""
echo "1. Vérifier que tu as un compte superuser:"
echo "   docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \"SELECT email, is_superuser FROM users WHERE email = 'jerome0laval@gmail.com';\""
echo ""
echo "2. Si is_superuser = false, activer:"
echo "   docker exec -it cloudwaste_postgres psql -U cloudwaste -d cloudwaste -c \"UPDATE users SET is_superuser = true WHERE email = 'jerome0laval@gmail.com';\""
echo ""
echo "3. Obtenir un token d'authentification:"
echo "   ACCESS_TOKEN=\$(curl -s -X POST \"https://cutcosts.tech/api/v1/auth/login\" \\"
echo "     -H \"Content-Type: application/x-www-form-urlencoded\" \\"
echo "     -d \"username=jerome0laval@gmail.com&password=VOTRE_MOT_DE_PASSE\" | jq -r '.access_token')"
echo ""
echo "4. Tester l'endpoint Sentry:"
echo "   curl -X GET \"https://cutcosts.tech/api/v1/test/sentry-test\" \\"
echo "     -H \"Authorization: Bearer \$ACCESS_TOKEN\" | jq"
echo ""
echo "5. Vérifier dans le dashboard Sentry:"
echo "   https://sentry.io → jerome-laval-x3 → cloudwaste"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT:${NC}"
echo "   • Le mode DEBUG expose des endpoints de test"
echo "   • Désactiver DEBUG après les tests:"
echo "     bash deployment/disable-sentry-testing.sh"
echo ""
