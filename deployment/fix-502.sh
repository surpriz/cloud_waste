#!/bin/bash

# ============================================================================
# CloudWaste - Fix 502 Bad Gateway Error
# ============================================================================
#
# This script diagnoses and fixes the common 502 Bad Gateway error
# that can occur after deployment or rollback
#
# Usage (on VPS):
#   cd /opt/cloudwaste
#   bash deployment/fix-502.sh
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
echo -e "${BLUE}║${NC}         ${GREEN}🔧 CORRECTION ERREUR 502 BAD GATEWAY${NC}                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

COMPOSE_FILE="deployment/docker-compose.prod.yml"

# ============================================================================
# Step 1: Check Container Status
# ============================================================================

print_step "Vérification de l'état des conteneurs..."
echo ""

docker compose -f "$COMPOSE_FILE" ps

echo ""

# Check if backend is running
if ! docker ps | grep -q "cloudwaste_backend"; then
    print_error "Le conteneur backend n'est pas en cours d'exécution"
    print_step "Redémarrage du backend..."
    docker compose -f "$COMPOSE_FILE" up -d backend
    sleep 10
fi

# ============================================================================
# Step 2: Check Backend Health
# ============================================================================

print_step "Vérification de la santé du backend..."

MAX_RETRIES=15
RETRY_COUNT=0
BACKEND_HEALTHY=false

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health 2>/dev/null; then
        BACKEND_HEALTHY=true
        print_success "Backend est opérationnel"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    echo "   Tentative $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ "$BACKEND_HEALTHY" != true ]; then
    print_error "Le backend ne répond pas aux health checks"
    print_warning "Consultation des logs backend..."
    echo ""
    docker logs cloudwaste_backend --tail 50
    echo ""
    print_error "Le backend semble avoir un problème"
    exit 1
fi

# ============================================================================
# Step 3: Restart Nginx to Clear DNS Cache
# ============================================================================

print_step "Redémarrage de Nginx pour rafraîchir le cache DNS..."
docker compose -f "$COMPOSE_FILE" restart nginx

print_step "Attente du redémarrage de Nginx..."
sleep 5

# ============================================================================
# Step 4: Test External Access
# ============================================================================

print_step "Test d'accès externe via HTTPS..."

# Test with curl (allow self-signed certs)
HTTPS_STATUS=$(curl -k -s -o /dev/null -w "%{http_code}" https://localhost/api/v1/health || echo "000")

if [ "$HTTPS_STATUS" == "200" ]; then
    print_success "API publique: OK (HTTP $HTTPS_STATUS)"
else
    print_warning "API locale: HTTP $HTTPS_STATUS (peut être normal si pas de certificat SSL)"

    # Try external domain
    print_step "Test avec le domaine externe..."
    EXT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")

    if [ "$EXT_STATUS" == "200" ]; then
        print_success "API externe: OK (HTTP $EXT_STATUS)"
    else
        print_error "API externe: FAIL (HTTP $EXT_STATUS)"

        print_warning "Consultation des logs Nginx..."
        echo ""
        docker logs cloudwaste_nginx --tail 30
        echo ""
    fi
fi

# ============================================================================
# Step 5: Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ DIAGNOSTIC TERMINÉ${NC}                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step "Vérification finale avec curl externe..."
echo ""
echo "   curl https://cutcosts.tech/api/v1/health"
echo ""
curl -s https://cutcosts.tech/api/v1/health || print_error "Erreur lors du curl externe"
echo ""
echo ""

print_success "Diagnostic terminé !"
echo ""
echo -e "${GREEN}📋 Prochaines étapes:${NC}"
echo "   • Si l'API fonctionne maintenant: OK, le problème est résolu"
echo "   • Si 502 persiste: Consultez les logs backend:"
echo "     docker logs cloudwaste_backend --tail 100"
echo ""
