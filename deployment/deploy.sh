#!/bin/bash

###############################################################################
# CloudWaste Deployment Script
# Description: Déploie ou met à jour CloudWaste en production
# Usage: bash deploy.sh
# À exécuter depuis: /opt/cloudwaste/
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_DIR="/opt/cloudwaste"
COMPOSE_FILE="docker-compose.production.yml"
BACKUP_BEFORE_DEPLOY=true

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}==>${NC} $1"
}

check_prerequisites() {
    log_step "Vérification des prérequis..."
    
    if [ ! -d "${APP_DIR}" ]; then
        log_error "Répertoire ${APP_DIR} non trouvé"
        exit 1
    fi
    
    cd "${APP_DIR}"
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "Fichier ${COMPOSE_FILE} non trouvé"
        exit 1
    fi
    
    if [ ! -f ".env" ]; then
        log_error "Fichier .env non trouvé"
        log_info "Créez le fichier .env avant de déployer (voir VPS_PRODUCTION_GUIDE.md)"
        exit 1
    fi
    
    if [ ! -f "encryption_key" ]; then
        log_error "Fichier encryption_key non trouvé"
        exit 1
    fi
    
    log_info "Prérequis OK"
}

backup_before_deploy() {
    if [ "$BACKUP_BEFORE_DEPLOY" = true ]; then
        log_step "Création d'un backup avant déploiement..."
        
        if [ -f "${APP_DIR}/backup.sh" ]; then
            bash "${APP_DIR}/backup.sh"
            log_info "Backup créé avec succès"
        else
            log_warn "Script backup.sh non trouvé, backup ignoré"
        fi
    fi
}

pull_latest_code() {
    log_step "Récupération du code le plus récent..."
    
    if [ -d ".git" ]; then
        # Get current branch
        BRANCH=$(git rev-parse --abbrev-ref HEAD)
        log_info "Branche actuelle: ${BRANCH}"
        
        # Stash local changes if any
        if ! git diff-index --quiet HEAD --; then
            log_warn "Changements locaux détectés, sauvegarde temporaire..."
            git stash
        fi
        
        # Pull latest changes
        git pull origin "${BRANCH}"
        log_info "Code mis à jour"
        
        # Show latest commit
        log_info "Dernier commit: $(git log -1 --oneline)"
    else
        log_warn "Pas de repository git, étape ignorée"
    fi
}

build_images() {
    log_step "Construction des images Docker..."
    
    # Pull base images to get latest updates
    docker compose -f "${COMPOSE_FILE}" pull || true
    
    # Build images
    docker compose -f "${COMPOSE_FILE}" build --no-cache
    
    log_info "Images construites"
}

run_migrations() {
    log_step "Exécution des migrations de base de données..."
    
    # Check if database is ready
    log_info "Attente de la base de données..."
    sleep 5
    
    # Run migrations
    docker compose -f "${COMPOSE_FILE}" run --rm backend alembic upgrade head
    
    log_info "Migrations terminées"
}

deploy_services() {
    log_step "Déploiement des services..."
    
    # Deploy with zero-downtime (will recreate only changed containers)
    docker compose -f "${COMPOSE_FILE}" up -d --remove-orphans
    
    log_info "Services déployés"
}

wait_for_services() {
    log_step "Attente du démarrage des services..."
    
    sleep 10
    
    # Check if services are healthy
    log_info "Vérification de l'état des services..."
    docker compose -f "${COMPOSE_FILE}" ps
}

verify_deployment() {
    log_step "Vérification du déploiement..."
    
    # Check backend health
    log_info "Test de l'API backend..."
    sleep 5
    
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        log_info "✓ Backend opérationnel"
    else
        log_warn "⚠ Backend ne répond pas encore (peut prendre quelques secondes)"
    fi
    
    # Check if all containers are running
    RUNNING=$(docker compose -f "${COMPOSE_FILE}" ps --filter "status=running" --quiet | wc -l)
    TOTAL=$(docker compose -f "${COMPOSE_FILE}" ps --quiet | wc -l)
    
    if [ "$RUNNING" -eq "$TOTAL" ]; then
        log_info "✓ Tous les conteneurs sont actifs ($RUNNING/$TOTAL)"
    else
        log_warn "⚠ Certains conteneurs ne sont pas actifs ($RUNNING/$TOTAL)"
        log_info "Vérifiez les logs: docker compose -f ${COMPOSE_FILE} logs"
    fi
}

cleanup_old_images() {
    log_step "Nettoyage des anciennes images..."
    
    docker image prune -f
    
    log_info "Nettoyage terminé"
}

display_logs() {
    log_step "Affichage des logs (Ctrl+C pour quitter)..."
    echo ""
    docker compose -f "${COMPOSE_FILE}" logs -f --tail=50
}

show_summary() {
    echo ""
    log_info "==================================================================="
    log_info "Déploiement terminé avec succès!"
    log_info "==================================================================="
    echo ""
    log_info "Services actifs:"
    docker compose -f "${COMPOSE_FILE}" ps
    echo ""
    log_info "Commandes utiles:"
    echo "  - Voir les logs:    docker compose -f ${COMPOSE_FILE} logs -f"
    echo "  - Redémarrer:       docker compose -f ${COMPOSE_FILE} restart"
    echo "  - Arrêter:          docker compose -f ${COMPOSE_FILE} down"
    echo "  - État:             docker compose -f ${COMPOSE_FILE} ps"
    echo ""
    log_info "Accès:"
    echo "  - Frontend:         https://cutcosts.tech"
    echo "  - API:              https://cutcosts.tech/api/v1"
    echo "  - API Docs:         https://cutcosts.tech/api/v1/docs"
    echo "  - Portainer:        https://cutcosts.tech:9443"
    echo "  - Monitoring:       https://cutcosts.tech/netdata"
    echo ""
}

# Main execution
main() {
    log_info "Démarrage du déploiement CloudWaste..."
    echo ""
    
    check_prerequisites
    backup_before_deploy
    pull_latest_code
    build_images
    run_migrations
    deploy_services
    wait_for_services
    verify_deployment
    cleanup_old_images
    show_summary
    
    # Ask if user wants to see logs
    read -p "Afficher les logs en temps réel? (y/N) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        display_logs
    fi
}

# Handle script arguments
case "${1:-}" in
    --no-backup)
        BACKUP_BEFORE_DEPLOY=false
        main
        ;;
    --logs-only)
        cd "${APP_DIR}"
        display_logs
        ;;
    --help)
        echo "Usage: bash deploy.sh [OPTIONS]"
        echo ""
        echo "Options:"
        echo "  --no-backup    Ne pas créer de backup avant le déploiement"
        echo "  --logs-only    Afficher uniquement les logs"
        echo "  --help         Afficher cette aide"
        echo ""
        ;;
    *)
        main
        ;;
esac

