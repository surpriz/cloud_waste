#!/bin/bash

# ============================================================================
# CloudWaste - Rebuild Frontend with Sentry Variables
# ============================================================================
#
# This script rebuilds the frontend container with Sentry environment variables
# properly injected at build time.
#
# Usage (on VPS):
#   cd /opt/cloudwaste
#   bash deployment/rebuild-frontend-sentry.sh
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

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}🔄 REBUILD FRONTEND AVEC SENTRY${NC}                        ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

COMPOSE_FILE="deployment/docker-compose.prod.yml"
ENV_FILE=".env.prod"

# ============================================================================
# Step 1: Verify .env.prod exists
# ============================================================================

print_step "Vérification de .env.prod..."
if [ ! -f "$ENV_FILE" ]; then
    print_error "Fichier $ENV_FILE introuvable"
    exit 1
fi
print_success "Fichier .env.prod trouvé"

# ============================================================================
# Step 2: Load environment variables
# ============================================================================

print_step "Chargement des variables d'environnement..."
set -a
source "$ENV_FILE"
set +a
print_success "Variables chargées depuis .env.prod"

# ============================================================================
# Step 3: Verify Sentry variables are set
# ============================================================================

print_step "Vérification des variables Sentry..."
echo ""

if [ -z "$NEXT_PUBLIC_SENTRY_DSN" ]; then
    print_error "NEXT_PUBLIC_SENTRY_DSN n'est pas défini dans .env.prod"
    exit 1
else
    print_success "NEXT_PUBLIC_SENTRY_DSN trouvé"
    print_info "DSN: ${NEXT_PUBLIC_SENTRY_DSN:0:50}..."
fi

if [ -z "$NEXT_PUBLIC_SENTRY_ENVIRONMENT" ]; then
    print_warning "NEXT_PUBLIC_SENTRY_ENVIRONMENT non défini, utilisation de 'production'"
    export NEXT_PUBLIC_SENTRY_ENVIRONMENT="production"
else
    print_success "NEXT_PUBLIC_SENTRY_ENVIRONMENT: $NEXT_PUBLIC_SENTRY_ENVIRONMENT"
fi

echo ""

# ============================================================================
# Step 4: Pull latest code
# ============================================================================

print_step "Récupération du dernier code..."
git fetch origin master
git reset --hard origin/master
CURRENT_COMMIT=$(git rev-parse --short HEAD)
print_success "Code mis à jour vers commit: $CURRENT_COMMIT"

# ============================================================================
# Step 5: Stop frontend container
# ============================================================================

print_step "Arrêt du conteneur frontend..."
docker compose -f "$COMPOSE_FILE" stop frontend
print_success "Frontend arrêté"

# ============================================================================
# Step 6: Remove old frontend container and image
# ============================================================================

print_step "Suppression de l'ancien conteneur et image..."
docker compose -f "$COMPOSE_FILE" rm -f frontend
docker rmi deployment-frontend 2>/dev/null || echo "Image deployment-frontend non trouvée (normal)"
print_success "Ancien conteneur supprimé"

# ============================================================================
# Step 7: Rebuild frontend with Sentry variables
# ============================================================================

print_step "Rebuild du frontend avec les variables Sentry..."
print_info "Cela peut prendre 2-3 minutes..."
echo ""

docker compose -f "$COMPOSE_FILE" build \
    --no-cache \
    --build-arg NEXT_PUBLIC_API_URL=https://cutcosts.tech \
    --build-arg NEXT_PUBLIC_APP_NAME=CloudWaste \
    --build-arg NEXT_PUBLIC_SENTRY_DSN="$NEXT_PUBLIC_SENTRY_DSN" \
    --build-arg NEXT_PUBLIC_SENTRY_ENVIRONMENT="$NEXT_PUBLIC_SENTRY_ENVIRONMENT" \
    frontend

print_success "Build terminé"

# ============================================================================
# Step 8: Start frontend container
# ============================================================================

print_step "Démarrage du nouveau conteneur frontend..."
docker compose -f "$COMPOSE_FILE" up -d frontend

print_step "Attente du démarrage complet (120 secondes)..."
echo ""
for i in {1..12}; do
    echo -ne "${CYAN}⏳${NC} Temps écoulé: $((i*10))s / 120s\r"
    sleep 10
done
echo ""

# ============================================================================
# Step 9: Verify frontend is healthy
# ============================================================================

print_step "Vérification de l'état du conteneur..."
FRONTEND_STATUS=$(docker inspect cloudwaste_frontend --format='{{.State.Status}}' 2>/dev/null || echo "not_found")

if [ "$FRONTEND_STATUS" == "running" ]; then
    print_success "Frontend en cours d'exécution"
else
    print_error "Frontend non démarré (status: $FRONTEND_STATUS)"
    print_info "Vérifiez les logs: docker logs cloudwaste_frontend"
    exit 1
fi

# ============================================================================
# Step 10: Verify Sentry variables in container
# ============================================================================

print_step "Vérification des variables Sentry dans le conteneur..."
echo ""

CONTAINER_SENTRY_DSN=$(docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY_DSN=" | cut -d'=' -f2)

if [ -z "$CONTAINER_SENTRY_DSN" ]; then
    print_error "NEXT_PUBLIC_SENTRY_DSN toujours vide dans le conteneur"
    print_warning "Le frontend doit avoir les variables au moment du build"
    echo ""
    print_info "Variables actuelles dans le conteneur:"
    docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY" || echo "Aucune"
else
    print_success "NEXT_PUBLIC_SENTRY_DSN présent dans le conteneur"
    print_info "DSN: ${CONTAINER_SENTRY_DSN:0:50}..."
fi

echo ""
docker exec cloudwaste_frontend env | grep "^NEXT_PUBLIC_SENTRY"

# ============================================================================
# Step 11: Test frontend accessibility
# ============================================================================

print_step "Test d'accès au frontend..."
FRONTEND_HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech || echo "000")

if [ "$FRONTEND_HTTP_CODE" == "200" ]; then
    print_success "Frontend accessible (HTTP $FRONTEND_HTTP_CODE)"
else
    print_warning "Frontend retourne HTTP $FRONTEND_HTTP_CODE"
    print_info "Le frontend peut nécessiter quelques minutes supplémentaires"
fi

# ============================================================================
# Step 12: Show logs (last 20 lines)
# ============================================================================

print_step "Logs frontend (dernières 20 lignes)..."
echo ""
docker logs cloudwaste_frontend --tail 20

# ============================================================================
# Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ REBUILD FRONTEND TERMINÉ${NC}                            ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_success "Frontend reconstruit avec les variables Sentry"
echo ""
echo -e "${GREEN}📋 Prochaines étapes:${NC}"
echo ""
echo "1. Attendre 2-3 minutes supplémentaires si le frontend retourne HTTP $FRONTEND_HTTP_CODE"
echo ""
echo "2. Vérifier les variables Sentry dans le navigateur:"
echo "   • Ouvrir: https://cutcosts.tech"
echo "   • Console (F12 → Console)"
echo "   • Chercher les logs: [SentryProvider]"
echo "   • DSN devrait être défini (pas 'undefined')"
echo ""
echo "3. Tester Sentry frontend:"
echo "   • Console JavaScript:"
echo "   Sentry.captureException(new Error(\"🧪 Test Frontend Sentry Error\"));"
echo ""
echo "4. Vérifier dans Sentry:"
echo "   • https://sentry.io → jerome-laval-x3 → cloudwaste-frontend"
echo ""
echo -e "${CYAN}💡 Astuce:${NC} Si NEXT_PUBLIC_SENTRY_DSN est toujours undefined dans le navigateur,"
echo "   c'est que Next.js n'a pas reçu la variable au moment du build."
echo ""
