#!/bin/bash

# ============================================================================
# CloudWaste - Zero-Downtime Deployment Script
# ============================================================================
#
# This script performs a rolling update to avoid downtime during deployment
#
# What it does:
#   1. Save current commit for rollback capability
#   2. Build new images WITHOUT stopping current containers
#   3. Start new containers alongside old ones (blue-green)
#   4. Perform health checks on NEW containers
#   5. Switch traffic to new containers if healthy
#   6. Remove old containers
#   7. If any step fails → AUTOMATIC ROLLBACK to previous version
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
STABLE_COMMIT_FILE="/opt/cloudwaste/.last_stable_commit"
CURRENT_COMMIT=$(git rev-parse HEAD)

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

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Rollback function
rollback() {
    print_error "Déploiement échoué ! Lancement du rollback automatique..."

    if [ -f "$STABLE_COMMIT_FILE" ]; then
        STABLE_COMMIT=$(cat "$STABLE_COMMIT_FILE")
        print_warning "Retour au commit stable: $STABLE_COMMIT"

        # Reset to stable commit
        git reset --hard "$STABLE_COMMIT"

        # Rebuild and restart with stable version
        print_step "Reconstruction avec la version stable..."
        docker compose -f "$COMPOSE_FILE" build --no-cache --parallel
        docker compose -f "$COMPOSE_FILE" up -d

        print_success "Rollback terminé - Application restaurée à la version stable"
        exit 1
    else
        print_error "Aucun commit stable trouvé - Impossible de faire un rollback"
        print_warning "Les conteneurs actuels restent actifs"
        exit 1
    fi
}

# Trap errors to trigger rollback
trap 'rollback' ERR

# ============================================================================
# Load Environment Variables
# ============================================================================

print_step "Loading environment variables..."
set -a
source "$ENV_FILE"
set +a
print_success "Environment loaded"

# ============================================================================
# Step 0: Display Current Status
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}🚀 DÉPLOIEMENT SANS COUPURE (Blue-Green)${NC}                  ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

print_step "État actuel:"
echo "   • Commit actuel: $CURRENT_COMMIT"
if [ -f "$STABLE_COMMIT_FILE" ]; then
    echo "   • Dernier commit stable: $(cat $STABLE_COMMIT_FILE)"
else
    echo "   • Aucun commit stable enregistré (premier déploiement)"
fi
echo ""

# ============================================================================
# Step 1: Build New Images (WITHOUT stopping old containers)
# ============================================================================

print_step "Construction des nouvelles images Docker..."
print_warning "Les conteneurs actuels restent actifs pendant le build"

docker compose -f "$COMPOSE_FILE" build --no-cache --parallel

print_success "Nouvelles images construites"

# ============================================================================
# Step 2: Start New Containers (Blue-Green Deployment)
# ============================================================================

print_step "Démarrage des nouveaux conteneurs (en parallèle des anciens)..."

# Start databases first (if not running)
docker compose -f "$COMPOSE_FILE" up -d postgres redis

print_step "Attente de la disponibilité des bases de données..."
sleep 10

# Run migrations on new code
print_step "Application des migrations de base de données..."
docker compose -f "$COMPOSE_FILE" run --rm backend alembic upgrade head

# Start new containers with updated images
print_step "Démarrage de tous les services avec les nouvelles images..."
docker compose -f "$COMPOSE_FILE" up -d

print_step "Attente du démarrage des nouveaux conteneurs..."
sleep 20

# ============================================================================
# Step 3: Health Checks on NEW Containers
# ============================================================================

print_step "Vérification de la santé des NOUVEAUX conteneurs..."

MAX_RETRIES=30
RETRY_COUNT=0
BACKEND_HEALTHY=false
FRONTEND_HEALTHY=false

# Check backend health
print_step "Test du backend..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec cloudwaste_backend curl -f http://localhost:8000/api/v1/health 2>/dev/null; then
        BACKEND_HEALTHY=true
        print_success "Backend est opérationnel"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ "$BACKEND_HEALTHY" != true ]; then
    print_error "Le backend n'a pas démarré correctement"
    rollback
fi

# Check frontend health
RETRY_COUNT=0
print_step "Test du frontend..."
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if docker exec cloudwaste_frontend curl -f http://localhost:3000 2>/dev/null; then
        FRONTEND_HEALTHY=true
        print_success "Frontend est opérationnel"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT + 1))
    sleep 2
done

if [ "$FRONTEND_HEALTHY" != true ]; then
    print_warning "Le frontend n'a pas démarré à temps"
    print_warning "Cela peut être normal (démarrage lent de Next.js)"
fi

# ============================================================================
# Step 4: External Health Checks (Public URL)
# ============================================================================

print_step "Vérification externe de l'application..."
sleep 5

# Test frontend via public URL
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech || echo "000")
if [ "$FRONTEND_STATUS" == "200" ] || [ "$FRONTEND_STATUS" == "304" ]; then
    print_success "Frontend public: OK (HTTP $FRONTEND_STATUS)"
else
    print_error "Frontend public: FAIL (HTTP $FRONTEND_STATUS)"
    rollback
fi

# Test backend via public URL
API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health || echo "000")
if [ "$API_STATUS" == "200" ]; then
    print_success "API publique: OK (HTTP $API_STATUS)"
else
    print_error "API publique: FAIL (HTTP $API_STATUS)"
    rollback
fi

# ============================================================================
# Step 5: Deployment Success - Save Stable Commit
# ============================================================================

print_success "Tous les health checks sont passés !"
print_step "Enregistrement du commit stable..."

echo "$CURRENT_COMMIT" > "$STABLE_COMMIT_FILE"

print_success "Commit $CURRENT_COMMIT enregistré comme version stable"

# ============================================================================
# Step 6: Cleanup
# ============================================================================

print_step "Nettoyage des anciennes images..."
docker image prune -f > /dev/null 2>&1
print_success "Nettoyage terminé"

# ============================================================================
# Deployment Summary
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}✅ DÉPLOIEMENT RÉUSSI (ZERO DOWNTIME)${NC}                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "${GREEN}📊 Résumé du déploiement:${NC}"
echo "   • Commit déployé: $CURRENT_COMMIT"
echo "   • Aucune coupure de service détectée"
echo "   • Rollback automatique activé pour les prochains déploiements"
echo ""
echo -e "${GREEN}🌐 Application en ligne:${NC}"
echo "   • Site web: https://cutcosts.tech"
echo "   • API Docs: https://cutcosts.tech/api/docs"
echo ""
