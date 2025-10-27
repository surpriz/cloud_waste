#!/bin/bash

###############################################################################
# CloudWaste Pre-Push Validation Script
# Description: Valide la configuration avant de pousser vers production
# Usage: bash deployment/validate-before-push.sh
# À exécuter depuis: racine du projet CloudWaste/
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
ERRORS=0
WARNINGS=0

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔍 VALIDATION PRÉ-DÉPLOIEMENT CLOUDWASTE                   ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Functions
log_info() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

log_error() {
    echo -e "${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
}

log_step() {
    echo -e "${BLUE}➜${NC} $1"
}

# Check 1: Verify we're in the correct directory
check_directory() {
    log_step "Vérification du répertoire..."
    
    if [ ! -f "docker-compose.yml" ] || [ ! -d "backend" ] || [ ! -d "frontend" ]; then
        log_error "Vous devez exécuter ce script depuis la racine du projet CloudWaste"
        return 1
    fi
    
    log_info "Répertoire correct"
}

# Check 2: Verify production docker-compose configuration
check_docker_compose_production() {
    log_step "Vérification de docker-compose.production.yml..."
    
    local compose_file="deployment/docker-compose.production.yml"
    
    if [ ! -f "$compose_file" ]; then
        log_error "Fichier $compose_file introuvable"
        return 1
    fi
    
    # Check that frontend uses Dockerfile.production
    if ! grep -q "dockerfile: Dockerfile.production" "$compose_file"; then
        log_error "Le frontend doit utiliser 'dockerfile: Dockerfile.production' dans $compose_file"
    else
        log_info "Frontend configuré avec Dockerfile.production"
    fi
    
    # Check for relative paths that should be ./ not ../
    if grep -q "context: \.\./backend" "$compose_file"; then
        log_error "Chemins relatifs incorrects: utilisez './backend' au lieu de '../backend'"
    else
        log_info "Chemins relatifs corrects pour backend"
    fi
    
    if grep -q "context: \.\./frontend" "$compose_file"; then
        log_error "Chemins relatifs incorrects: utilisez './frontend' au lieu de '../frontend'"
    else
        log_info "Chemins relatifs corrects pour frontend"
    fi
    
    # Check env_file paths
    if grep -q "env_file:.*\.\./\.env" "$compose_file"; then
        log_error "Chemin .env incorrect: utilisez '.env' au lieu de '../.env'"
    else
        log_info "Chemin .env correct"
    fi
}

# Check 3: Verify Dockerfile.production exists and is correct
check_dockerfiles() {
    log_step "Vérification des Dockerfiles de production..."
    
    # Check frontend Dockerfile.production
    if [ ! -f "frontend/Dockerfile.production" ]; then
        log_error "frontend/Dockerfile.production introuvable"
    else
        # Verify it's a multi-stage build
        if grep -q "FROM node:20-alpine AS deps" "frontend/Dockerfile.production" && \
           grep -q "FROM node:20-alpine AS builder" "frontend/Dockerfile.production" && \
           grep -q "FROM node:20-alpine AS runner" "frontend/Dockerfile.production"; then
            log_info "frontend/Dockerfile.production est un multi-stage build ✓"
        else
            log_error "frontend/Dockerfile.production n'est pas un multi-stage build correct"
        fi
        
        # Check that it installs all dependencies (not --only=production)
        if grep -q "npm ci --only=production" "frontend/Dockerfile.production"; then
            log_error "frontend/Dockerfile.production utilise 'npm ci --only=production' (devrait être 'npm ci')"
        else
            log_info "frontend/Dockerfile.production installe toutes les dépendances ✓"
        fi
    fi
    
    # Check backend Dockerfile exists
    if [ ! -f "backend/Dockerfile" ]; then
        log_error "backend/Dockerfile introuvable"
    else
        log_info "backend/Dockerfile présent"
    fi
}

# Check 4: Verify essential directories and files
check_essential_files() {
    log_step "Vérification des fichiers essentiels..."
    
    # Frontend
    if [ ! -d "frontend/src" ]; then
        log_error "frontend/src/ introuvable"
    else
        log_info "frontend/src/ présent"
    fi
    
    if [ ! -f "frontend/package.json" ]; then
        log_error "frontend/package.json introuvable"
    else
        log_info "frontend/package.json présent"
    fi
    
    # Backend
    if [ ! -d "backend/app" ]; then
        log_error "backend/app/ introuvable"
    else
        log_info "backend/app/ présent"
    fi
    
    if [ ! -f "backend/requirements.txt" ]; then
        log_error "backend/requirements.txt introuvable"
    else
        log_info "backend/requirements.txt présent"
    fi
    
    # Deployment files
    if [ ! -f "deployment/deploy.sh" ]; then
        log_warn "deployment/deploy.sh introuvable"
    else
        log_info "deployment/deploy.sh présent"
    fi
}

# Check 5: Verify Git status
check_git_status() {
    log_step "Vérification du statut Git..."
    
    if ! git rev-parse --git-dir > /dev/null 2>&1; then
        log_error "Pas de repository Git trouvé"
        return 1
    fi
    
    # Check for uncommitted changes
    if ! git diff-index --quiet HEAD -- 2>/dev/null; then
        log_warn "Vous avez des modifications non committées"
        echo "   Fichiers modifiés:"
        git diff --name-only | sed 's/^/   - /'
    else
        log_info "Aucune modification non committée"
    fi
    
    # Check current branch
    BRANCH=$(git rev-parse --abbrev-ref HEAD)
    if [ "$BRANCH" != "master" ]; then
        log_warn "Vous êtes sur la branche '$BRANCH' (recommandé: master)"
    else
        log_info "Branche: master"
    fi
}

# Check 6: Verify deployment configuration
check_deployment_config() {
    log_step "Vérification de la configuration de déploiement..."
    
    # Check GitHub Actions workflow
    if [ -f ".github/workflows/deploy-production.yml" ]; then
        if grep -q "branches:.*master" ".github/workflows/deploy-production.yml"; then
            log_info "GitHub Actions configuré pour la branche master"
        else
            log_warn "GitHub Actions pourrait ne pas être configuré pour master"
        fi
    else
        log_warn ".github/workflows/deploy-production.yml introuvable"
    fi
}

# Run all checks
main() {
    check_directory || exit 1
    check_docker_compose_production
    check_dockerfiles
    check_essential_files
    check_git_status
    check_deployment_config
    
    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    
    # Summary
    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        echo -e "${GREEN}╔════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${GREEN}║                                                                    ║${NC}"
        echo -e "${GREEN}║                  ✅ VALIDATION RÉUSSIE !                           ║${NC}"
        echo -e "${GREEN}║                                                                    ║${NC}"
        echo -e "${GREEN}╚════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${GREEN}Vous pouvez pousser en toute sécurité :${NC}"
        echo "  git add ."
        echo "  git commit -m \"Votre message\""
        echo "  git push origin master"
        echo ""
    elif [ $ERRORS -eq 0 ]; then
        echo -e "${YELLOW}╔════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${YELLOW}║                                                                    ║${NC}"
        echo -e "${YELLOW}║              ⚠️  VALIDATION AVEC AVERTISSEMENTS                    ║${NC}"
        echo -e "${YELLOW}║                                                                    ║${NC}"
        echo -e "${YELLOW}╚════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${YELLOW}$WARNINGS avertissement(s) détecté(s)${NC}"
        echo "Vous pouvez pousser, mais vérifiez les avertissements ci-dessus."
        echo ""
    else
        echo -e "${RED}╔════════════════════════════════════════════════════════════════════╗${NC}"
        echo -e "${RED}║                                                                    ║${NC}"
        echo -e "${RED}║                  ❌ VALIDATION ÉCHOUÉE !                           ║${NC}"
        echo -e "${RED}║                                                                    ║${NC}"
        echo -e "${RED}╚════════════════════════════════════════════════════════════════════╝${NC}"
        echo ""
        echo -e "${RED}$ERRORS erreur(s) et $WARNINGS avertissement(s) détecté(s)${NC}"
        echo ""
        echo "⚠️  NE POUSSEZ PAS avant d'avoir corrigé les erreurs ci-dessus."
        echo ""
        exit 1
    fi
}

# Execute
main

