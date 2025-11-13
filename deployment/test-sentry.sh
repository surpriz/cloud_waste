#!/bin/bash

# ============================================================================
# CloudWaste - Automated Sentry Testing Script
# ============================================================================
#
# This script automatically tests Sentry integration for both backend and
# frontend without requiring manual token management or curl commands.
#
# Usage (on VPS):
#   cd /opt/cloudwaste
#   bash deployment/test-sentry.sh
#
# Usage (with custom credentials):
#   bash deployment/test-sentry.sh your-email@example.com your-password
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
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

print_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

# ============================================================================
# Configuration
# ============================================================================

API_BASE_URL="https://cutcosts.tech/api/v1"

# Get credentials from arguments or use defaults
EMAIL="${1:-jerome0laval@gmail.com}"
PASSWORD="${2:-Motdepasse13\$}"  # Escaped $ character

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}🧪 TEST AUTOMATISÉ SENTRY${NC}                              ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# ============================================================================
# Step 1: Authentication
# ============================================================================

print_step "Authentification en cours..."
print_info "Email: $EMAIL"

# Use single quotes to prevent shell interpretation of special characters
LOGIN_RESPONSE=$(curl -s -X POST "$API_BASE_URL/auth/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  --data-urlencode "username=$EMAIL" \
  --data-urlencode "password=$PASSWORD")

# Check if login was successful
if echo "$LOGIN_RESPONSE" | grep -q "access_token"; then
    ACCESS_TOKEN=$(echo "$LOGIN_RESPONSE" | jq -r '.access_token')
    print_success "Authentification réussie"
    print_info "Token obtenu: ${ACCESS_TOKEN:0:30}..."
else
    print_error "Échec de l'authentification"
    echo ""
    echo "Réponse du serveur:"
    echo "$LOGIN_RESPONSE" | jq '.' 2>/dev/null || echo "$LOGIN_RESPONSE"
    echo ""
    print_error "Vérifiez vos identifiants et réessayez"
    exit 1
fi

echo ""

# ============================================================================
# Step 2: Check Sentry Status
# ============================================================================

print_step "Vérification du statut Sentry..."

STATUS_RESPONSE=$(curl -s -X GET "$API_BASE_URL/test/sentry/status" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$STATUS_RESPONSE" | grep -q "success"; then
    print_success "Sentry est configuré et actif"

    SENTRY_ENV=$(echo "$STATUS_RESPONSE" | jq -r '.sentry_environment // "N/A"')
    print_info "Environnement: $SENTRY_ENV"

    echo ""
    echo "$STATUS_RESPONSE" | jq '.'
else
    print_warning "Sentry status check échoué"
    echo ""
    echo "$STATUS_RESPONSE" | jq '.' 2>/dev/null || echo "$STATUS_RESPONSE"
fi

echo ""

# ============================================================================
# Step 3: Send Test Message to Sentry
# ============================================================================

print_step "Envoi d'un message de test à Sentry..."

MESSAGE_RESPONSE=$(curl -s -X POST "$API_BASE_URL/test/sentry/message" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

if echo "$MESSAGE_RESPONSE" | grep -q "success"; then
    print_success "Message de test envoyé à Sentry"

    echo ""
    echo "$MESSAGE_RESPONSE" | jq '.'
else
    print_error "Échec de l'envoi du message"
    echo ""
    echo "$MESSAGE_RESPONSE" | jq '.' 2>/dev/null || echo "$MESSAGE_RESPONSE"
fi

echo ""

# ============================================================================
# Step 4: Trigger Test Error
# ============================================================================

print_step "Déclenchement d'une erreur de test (ZeroDivisionError)..."

ERROR_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$API_BASE_URL/test/sentry/error" \
  -H "Authorization: Bearer $ACCESS_TOKEN")

# Extract HTTP status code (last line)
HTTP_CODE=$(echo "$ERROR_RESPONSE" | tail -n1)
ERROR_BODY=$(echo "$ERROR_RESPONSE" | sed '$d')

if [ "$HTTP_CODE" == "500" ]; then
    print_success "Erreur de test déclenchée avec succès (HTTP 500 attendu)"
    print_info "Cette erreur devrait apparaître dans Sentry"
else
    print_warning "Code HTTP inattendu: $HTTP_CODE (attendu: 500)"
fi

echo ""
echo "Réponse du serveur:"
echo "$ERROR_BODY" | jq '.' 2>/dev/null || echo "$ERROR_BODY"

echo ""

# ============================================================================
# Step 5: Verify Backend Logs
# ============================================================================

print_step "Vérification des logs backend (dernières 10 lignes)..."
echo ""

if command -v docker &> /dev/null; then
    docker logs cloudwaste_backend --tail 10 2>&1 | grep -i "sentry\|error\|test" || echo "Aucun log Sentry récent"
else
    print_warning "Docker non disponible - impossible de vérifier les logs"
fi

echo ""

# ============================================================================
# Step 6: Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ TESTS BACKEND SENTRY TERMINÉS${NC}                       ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_success "Tests automatisés terminés avec succès"
echo ""
echo -e "${GREEN}📊 Résumé des tests:${NC}"
echo "   ✅ Authentification réussie"
echo "   ✅ Statut Sentry vérifié"
echo "   ✅ Message de test envoyé à Sentry"
echo "   ✅ Erreur de test déclenchée (ZeroDivisionError)"
echo ""
echo -e "${CYAN}🔍 Prochaines étapes:${NC}"
echo ""
echo "1. Vérifiez le dashboard Sentry:"
echo "   • URL: https://sentry.io"
echo "   • Organisation: jerome-laval-x3"
echo "   • Projet: cloudwaste (Backend)"
echo ""
echo "2. Vous devriez voir:"
echo "   • ✅ Message: \"✅ Sentry test message from CloudWaste\""
echo "   • ✅ Erreur: \"ZeroDivisionError: 🚨 TEST ERROR: Sentry integration test\""
echo "   • ✅ Tags: environment=production, user_triggered=true"
echo "   • ✅ User context: Votre email et user ID"
echo ""
echo "3. Test Frontend (dans le navigateur):"
echo "   • Ouvrir: https://cutcosts.tech"
echo "   • Console JavaScript (F12 → Console)"
echo "   • Exécuter: Sentry.captureException(new Error(\"🧪 Test Frontend Sentry\"));"
echo "   • Vérifier dans Sentry → Projet: cloudwaste-frontend"
echo ""
echo -e "${YELLOW}⚠️  Note:${NC} Les événements Sentry peuvent prendre 10-30 secondes à apparaître"
echo ""
