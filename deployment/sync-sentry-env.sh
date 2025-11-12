#!/bin/bash

# ============================================================================
# CloudWaste - Sentry Environment Variables Synchronization Script
# ============================================================================
#
# This script adds/updates Sentry configuration variables in .env.prod on VPS
#
# Usage (from local machine):
#   bash deployment/sync-sentry-env.sh
#
# Usage (from VPS):
#   cd /opt/cloudwaste && bash deployment/sync-sentry-env.sh --local
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

# ============================================================================
# Configuration
# ============================================================================

ENV_FILE="/opt/cloudwaste/.env.prod"

# Sentry variables for BACKEND
BACKEND_SENTRY_DSN="https://1e103a6f257e3a1c7f286efb9fa42c75@o4510350814085121.ingest.de.sentry.io/4510350841086032"
BACKEND_SENTRY_ENV="production"
BACKEND_SENTRY_TRACES_SAMPLE_RATE="0.1"
BACKEND_SENTRY_PROFILES_SAMPLE_RATE="0.1"

# Sentry variables for FRONTEND
FRONTEND_SENTRY_DSN="https://442a2365755e0b972138478b85fdb5a7@o4510350814085121.ingest.de.sentry.io/4510350846984272"
FRONTEND_SENTRY_ENV="production"

# ============================================================================
# Main Script
# ============================================================================

echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}         ${GREEN}🔄 SYNCHRONISATION DES VARIABLES SENTRY${NC}                  ${BLUE}║${NC}"
echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if running locally or on VPS
if [ "$1" == "--local" ]; then
    print_step "Mode: Exécution locale sur le VPS"

    # Check if .env.prod exists
    if [ ! -f "$ENV_FILE" ]; then
        print_error "Fichier $ENV_FILE introuvable !"
        exit 1
    fi

    print_step "Création d'une sauvegarde de .env.prod..."
    cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
    print_success "Sauvegarde créée"

    print_step "Ajout/mise à jour des variables Sentry..."

    # Backend variables
    if grep -q "^SENTRY_DSN=" "$ENV_FILE"; then
        print_warning "SENTRY_DSN existe déjà - Mise à jour..."
        sed -i "s|^SENTRY_DSN=.*|SENTRY_DSN=$BACKEND_SENTRY_DSN|" "$ENV_FILE"
    else
        echo "" >> "$ENV_FILE"
        echo "# Sentry Error Tracking (Backend)" >> "$ENV_FILE"
        echo "SENTRY_DSN=$BACKEND_SENTRY_DSN" >> "$ENV_FILE"
    fi

    if grep -q "^SENTRY_ENVIRONMENT=" "$ENV_FILE"; then
        sed -i "s|^SENTRY_ENVIRONMENT=.*|SENTRY_ENVIRONMENT=$BACKEND_SENTRY_ENV|" "$ENV_FILE"
    else
        echo "SENTRY_ENVIRONMENT=$BACKEND_SENTRY_ENV" >> "$ENV_FILE"
    fi

    if grep -q "^SENTRY_TRACES_SAMPLE_RATE=" "$ENV_FILE"; then
        sed -i "s|^SENTRY_TRACES_SAMPLE_RATE=.*|SENTRY_TRACES_SAMPLE_RATE=$BACKEND_SENTRY_TRACES_SAMPLE_RATE|" "$ENV_FILE"
    else
        echo "SENTRY_TRACES_SAMPLE_RATE=$BACKEND_SENTRY_TRACES_SAMPLE_RATE" >> "$ENV_FILE"
    fi

    if grep -q "^SENTRY_PROFILES_SAMPLE_RATE=" "$ENV_FILE"; then
        sed -i "s|^SENTRY_PROFILES_SAMPLE_RATE=.*|SENTRY_PROFILES_SAMPLE_RATE=$BACKEND_SENTRY_PROFILES_SAMPLE_RATE|" "$ENV_FILE"
    else
        echo "SENTRY_PROFILES_SAMPLE_RATE=$BACKEND_SENTRY_PROFILES_SAMPLE_RATE" >> "$ENV_FILE"
    fi

    # Frontend variables
    if grep -q "^NEXT_PUBLIC_SENTRY_DSN=" "$ENV_FILE"; then
        print_warning "NEXT_PUBLIC_SENTRY_DSN existe déjà - Mise à jour..."
        sed -i "s|^NEXT_PUBLIC_SENTRY_DSN=.*|NEXT_PUBLIC_SENTRY_DSN=$FRONTEND_SENTRY_DSN|" "$ENV_FILE"
    else
        echo "" >> "$ENV_FILE"
        echo "# Sentry Error Tracking (Frontend)" >> "$ENV_FILE"
        echo "NEXT_PUBLIC_SENTRY_DSN=$FRONTEND_SENTRY_DSN" >> "$ENV_FILE"
    fi

    if grep -q "^NEXT_PUBLIC_SENTRY_ENVIRONMENT=" "$ENV_FILE"; then
        sed -i "s|^NEXT_PUBLIC_SENTRY_ENVIRONMENT=.*|NEXT_PUBLIC_SENTRY_ENVIRONMENT=$FRONTEND_SENTRY_ENV|" "$ENV_FILE"
    else
        echo "NEXT_PUBLIC_SENTRY_ENVIRONMENT=$FRONTEND_SENTRY_ENV" >> "$ENV_FILE"
    fi

    print_success "Variables Sentry ajoutées/mises à jour"

    # Verification
    print_step "Vérification des variables..."
    echo ""
    echo "📋 Variables Backend:"
    grep "^SENTRY" "$ENV_FILE" | grep -v "NEXT_PUBLIC" || echo "  Aucune variable backend trouvée"
    echo ""
    echo "📋 Variables Frontend:"
    grep "^NEXT_PUBLIC_SENTRY" "$ENV_FILE" || echo "  Aucune variable frontend trouvée"
    echo ""

    print_success "Synchronisation terminée !"
    echo ""
    print_warning "⚠️  IMPORTANT: Redémarrez les conteneurs pour que les changements prennent effet:"
    echo "   docker compose -f deployment/docker-compose.prod.yml restart backend frontend"
    echo ""

else
    # Running from local machine - SSH to VPS
    print_step "Mode: Exécution distante via SSH"

    # Check if SSH config exists
    if [ -z "$VPS_HOST" ] || [ -z "$VPS_USER" ]; then
        print_error "Variables d'environnement VPS_HOST et VPS_USER non définies"
        echo ""
        echo "Usage:"
        echo "  export VPS_HOST=your-vps-ip"
        echo "  export VPS_USER=root"
        echo "  bash deployment/sync-sentry-env.sh"
        exit 1
    fi

    print_step "Connexion à $VPS_USER@$VPS_HOST..."

    # Execute on remote VPS
    ssh "$VPS_USER@$VPS_HOST" 'bash -s' <<'ENDSSH'
        cd /opt/cloudwaste
        bash deployment/sync-sentry-env.sh --local
ENDSSH

    print_success "Synchronisation distante terminée"
fi

echo ""
echo -e "${GREEN}✅ Sentry est maintenant configuré en production${NC}"
echo ""
