#!/bin/bash

###############################################################################
# Pre-Deployment Check Script
# Description: Vérifie que tous les prérequis sont en place avant déploiement
# Usage: bash pre-deployment-check.sh
###############################################################################

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Counters
CHECKS_PASSED=0
CHECKS_FAILED=0
CHECKS_WARNING=0

log_success() {
    echo -e "${GREEN}✓${NC} $1"
    ((CHECKS_PASSED++))
}

log_failure() {
    echo -e "${RED}✗${NC} $1"
    ((CHECKS_FAILED++))
}

log_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
    ((CHECKS_WARNING++))
}

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

section_header() {
    echo ""
    echo -e "${BLUE}===${NC} $1"
}

check_vps_access() {
    section_header "Accès VPS"
    
    VPS_IP="155.117.43.17"
    
    if ping -c 1 -W 2 $VPS_IP > /dev/null 2>&1; then
        log_success "VPS accessible ($VPS_IP)"
    else
        log_failure "VPS non accessible ($VPS_IP)"
    fi
    
    log_info "Testez la connexion SSH: ssh root@${VPS_IP}"
}

check_dns() {
    section_header "Configuration DNS"
    
    DOMAIN="cutcosts.tech"
    VPS_IP="155.117.43.17"
    
    if command -v nslookup &> /dev/null; then
        RESOLVED_IP=$(nslookup $DOMAIN 2>/dev/null | awk '/^Address: / { print $2 }' | tail -1)
        
        if [ "$RESOLVED_IP" = "$VPS_IP" ]; then
            log_success "DNS configuré correctement ($DOMAIN → $VPS_IP)"
        else
            log_warning "DNS non configuré ou en propagation ($DOMAIN → ${RESOLVED_IP:-N/A})"
            log_info "Configurez les enregistrements A dans votre gestionnaire DNS"
        fi
    else
        log_warning "nslookup non disponible, vérification DNS ignorée"
    fi
}

check_local_files() {
    section_header "Fichiers Locaux"
    
    # Check deployment directory
    if [ -d "deployment" ]; then
        log_success "Dossier deployment/ présent"
    else
        log_failure "Dossier deployment/ manquant"
        return 1
    fi
    
    # Check required scripts
    REQUIRED_SCRIPTS=(
        "deployment/setup-vps.sh"
        "deployment/deploy.sh"
        "deployment/backup.sh"
        "deployment/restore.sh"
        "deployment/docker-compose.production.yml"
        "deployment/env.production.template"
    )
    
    for script in "${REQUIRED_SCRIPTS[@]}"; do
        if [ -f "$script" ]; then
            log_success "Script $(basename $script) présent"
        else
            log_failure "Script $(basename $script) manquant"
        fi
    done
    
    # Check if scripts are executable
    for script in deployment/*.sh; do
        if [ -x "$script" ]; then
            log_success "$(basename $script) est exécutable"
        else
            log_warning "$(basename $script) n'est pas exécutable"
            log_info "Exécutez: chmod +x deployment/*.sh"
        fi
    done
}

check_environment_files() {
    section_header "Fichiers d'Environnement"
    
    # Check .env exists
    if [ -f ".env" ]; then
        log_success "Fichier .env local présent"
        
        # Check for required variables
        REQUIRED_VARS=(
            "SECRET_KEY"
            "JWT_SECRET_KEY"
            "ENCRYPTION_KEY"
            "DATABASE_URL"
            "ANTHROPIC_API_KEY"
        )
        
        for var in "${REQUIRED_VARS[@]}"; do
            if grep -q "^${var}=" .env 2>/dev/null; then
                log_success "Variable ${var} définie"
            else
                log_warning "Variable ${var} manquante ou commentée"
            fi
        done
    else
        log_warning "Fichier .env local non trouvé"
        log_info "Créez-le depuis .env.example pour référence"
    fi
    
    # Check encryption key
    if [ -f "encryption_key" ]; then
        log_success "Fichier encryption_key présent"
        KEY_SIZE=$(wc -c < encryption_key | tr -d ' ')
        if [ "$KEY_SIZE" -gt 40 ]; then
            log_success "Clé de chiffrement a une taille valide"
        else
            log_warning "Clé de chiffrement semble trop courte"
        fi
    else
        log_failure "Fichier encryption_key manquant (CRITIQUE)"
        log_info "Ce fichier est essentiel pour le déploiement"
    fi
}

check_documentation() {
    section_header "Documentation"
    
    DOCS=(
        "VPS_PRODUCTION_GUIDE.md"
        "deployment/QUICKSTART.md"
        "deployment/README.md"
        "deployment/DEPLOYMENT_CHECKLIST.md"
    )
    
    for doc in "${DOCS[@]}"; do
        if [ -f "$doc" ]; then
            log_success "$(basename $doc) disponible"
        else
            log_warning "$(basename $doc) manquant"
        fi
    done
}

check_github_workflow() {
    section_header "GitHub Actions"
    
    if [ -f ".github/workflows/deploy-production.yml" ]; then
        log_success "Workflow GitHub Actions présent"
        log_info "N'oubliez pas de configurer les secrets GitHub"
    else
        log_warning "Workflow GitHub Actions manquant"
    fi
}

check_git_status() {
    section_header "État Git"
    
    if [ -d ".git" ]; then
        log_success "Repository Git initialisé"
        
        # Check for uncommitted changes
        if git diff-index --quiet HEAD -- 2>/dev/null; then
            log_success "Aucun changement non commité"
        else
            log_warning "Changements non commités détectés"
            log_info "Commitez vos changements avant le déploiement"
        fi
        
        # Check current branch
        BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null)
        log_info "Branche actuelle: $BRANCH"
    else
        log_warning "Pas de repository Git"
    fi
}

check_api_keys() {
    section_header "Clés API"
    
    log_info "Vérifiez que vous avez ces clés API prêtes:"
    echo "  - Anthropic API Key (pour le chat AI)"
    echo "  - Azure Client ID, Secret, Tenant ID (pour scans Azure)"
    echo "  - AWS Access Key ID, Secret (pour scans AWS)"
    echo ""
    
    read -p "Avez-vous toutes les clés API nécessaires? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        log_success "Clés API prêtes"
    else
        log_warning "Préparez vos clés API avant le déploiement"
    fi
}

display_summary() {
    echo ""
    echo "================================================================="
    echo "                RÉSUMÉ DE LA VÉRIFICATION"
    echo "================================================================="
    echo -e "${GREEN}Réussis:${NC}    $CHECKS_PASSED"
    echo -e "${YELLOW}Warnings:${NC}   $CHECKS_WARNING"
    echo -e "${RED}Échoués:${NC}    $CHECKS_FAILED"
    echo "================================================================="
    
    if [ "$CHECKS_FAILED" -eq 0 ]; then
        echo -e "${GREEN}✓ Vous êtes prêt à déployer!${NC}"
        echo ""
        echo "Prochaines étapes:"
        echo "  1. Ouvrez: deployment/QUICKSTART.md"
        echo "  2. Suivez le guide pas-à-pas"
        echo "  3. Commencez par: scp deployment/setup-vps.sh root@155.117.43.17:/root/"
        echo ""
        return 0
    else
        echo -e "${RED}✗ Corrigez les erreurs avant de déployer${NC}"
        echo ""
        return 1
    fi
}

display_next_steps() {
    echo ""
    echo "================================================================="
    echo "                    PROCHAINES ÉTAPES"
    echo "================================================================="
    echo ""
    echo "1. Si DNS non configuré:"
    echo "   → Ajoutez les enregistrements A dans votre gestionnaire DNS"
    echo ""
    echo "2. Copiez le script d'installation sur le VPS:"
    echo "   → scp deployment/setup-vps.sh root@155.117.43.17:/root/"
    echo ""
    echo "3. Connectez-vous au VPS et lancez l'installation:"
    echo "   → ssh root@155.117.43.17"
    echo "   → bash /root/setup-vps.sh"
    echo ""
    echo "4. Suivez le guide complet:"
    echo "   → open deployment/QUICKSTART.md"
    echo ""
    echo "================================================================="
}

# Main execution
main() {
    echo "================================================================="
    echo "      CloudWaste - Vérification Pré-Déploiement"
    echo "================================================================="
    
    check_local_files
    check_environment_files
    check_documentation
    check_github_workflow
    check_git_status
    check_vps_access
    check_dns
    check_api_keys
    
    display_summary
    display_next_steps
}

main

