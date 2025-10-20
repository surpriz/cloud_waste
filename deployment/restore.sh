#!/bin/bash

###############################################################################
# CloudWaste Restore Script
# Description: Restaure CloudWaste depuis un backup
# Usage: bash restore.sh <backup-file.tar.gz>
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
RESTORE_TEMP_DIR="/tmp/cloudwaste-restore-$$"

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
    if [ -z "$1" ]; then
        log_error "Usage: bash restore.sh <backup-file.tar.gz>"
        exit 1
    fi
    
    BACKUP_FILE="$1"
    
    if [ ! -f "${BACKUP_FILE}" ]; then
        log_error "Fichier de backup non trouvé: ${BACKUP_FILE}"
        exit 1
    fi
    
    if [ ! -d "${APP_DIR}" ]; then
        log_error "Répertoire ${APP_DIR} non trouvé"
        exit 1
    fi
    
    log_info "Fichier de backup: ${BACKUP_FILE}"
}

confirm_restore() {
    echo ""
    log_warn "⚠️  ATTENTION ⚠️"
    log_warn "Cette opération va:"
    echo "  - Arrêter tous les services CloudWaste"
    echo "  - Supprimer les données actuelles"
    echo "  - Restaurer les données depuis: $(basename ${BACKUP_FILE})"
    echo ""
    read -p "Êtes-vous sûr de vouloir continuer? (yes/NO) " -r
    echo ""
    
    if [ "$REPLY" != "yes" ]; then
        log_info "Restauration annulée"
        exit 0
    fi
}

stop_services() {
    log_step "Arrêt des services..."
    
    cd "${APP_DIR}"
    
    if [ -f "${COMPOSE_FILE}" ]; then
        docker compose -f "${COMPOSE_FILE}" down
        log_info "Services arrêtés"
    else
        log_warn "Fichier docker-compose non trouvé, étape ignorée"
    fi
}

extract_backup() {
    log_step "Extraction du backup..."
    
    mkdir -p "${RESTORE_TEMP_DIR}"
    
    tar xzf "${BACKUP_FILE}" -C "${RESTORE_TEMP_DIR}"
    
    # Find the extracted directory
    BACKUP_DIR=$(find "${RESTORE_TEMP_DIR}" -maxdepth 1 -type d -name "cloudwaste-backup-*" | head -1)
    
    if [ -z "${BACKUP_DIR}" ]; then
        log_error "Structure de backup invalide"
        exit 1
    fi
    
    log_info "Backup extrait dans ${BACKUP_DIR}"
}

restore_database() {
    log_step "Restauration de la base de données..."
    
    if [ ! -f "${BACKUP_DIR}/database.sql" ]; then
        log_error "Fichier database.sql non trouvé dans le backup"
        return 1
    fi
    
    # Start only postgres to restore
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" up -d postgres
    
    # Wait for postgres to be ready
    log_info "Attente de PostgreSQL..."
    sleep 10
    
    # Drop and recreate database
    log_info "Recréation de la base de données..."
    docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U cloudwaste -d postgres <<EOF
DROP DATABASE IF EXISTS cloudwaste;
CREATE DATABASE cloudwaste;
EOF
    
    # Restore database
    log_info "Importation des données..."
    docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U cloudwaste -d cloudwaste < "${BACKUP_DIR}/database.sql"
    
    log_info "Base de données restaurée"
}

restore_docker_volumes() {
    log_step "Restauration des volumes Docker..."
    
    for volume_archive in "${BACKUP_DIR}"/volume_*.tar.gz; do
        if [ -f "${volume_archive}" ]; then
            volume_name=$(basename "${volume_archive}" .tar.gz | sed 's/^volume_//')
            log_info "Restauration du volume: ${volume_name}"
            
            # Remove old volume
            docker volume rm "${volume_name}" 2>/dev/null || true
            
            # Create new volume and restore data
            docker volume create "${volume_name}"
            docker run --rm \
                -v "${volume_name}:/volume" \
                -v "${BACKUP_DIR}:/backup" \
                alpine tar xzf "/backup/volume_${volume_name}.tar.gz" -C /volume
        fi
    done
    
    log_info "Volumes Docker restaurés"
}

restore_config_files() {
    log_step "Restauration des fichiers de configuration..."
    
    cd "${APP_DIR}"
    
    # Backup current files before overwriting
    if [ -f .env ]; then
        cp .env .env.before_restore
    fi
    
    # Restore config files
    if [ -f "${BACKUP_DIR}/.env" ]; then
        cp "${BACKUP_DIR}/.env" .env
        log_info ".env restauré"
    fi
    
    if [ -f "${BACKUP_DIR}/encryption_key" ]; then
        cp "${BACKUP_DIR}/encryption_key" encryption_key
        chmod 600 encryption_key
        log_info "encryption_key restauré"
    fi
    
    if [ -f "${BACKUP_DIR}/${COMPOSE_FILE}" ]; then
        cp "${BACKUP_DIR}/${COMPOSE_FILE}" "${COMPOSE_FILE}"
        log_info "${COMPOSE_FILE} restauré"
    fi
    
    # Restore nginx config
    if [ -f "${BACKUP_DIR}/nginx-cutcosts.tech.conf" ]; then
        sudo cp "${BACKUP_DIR}/nginx-cutcosts.tech.conf" /etc/nginx/sites-available/cutcosts.tech
        log_info "Configuration Nginx restaurée"
    fi
}

restore_application_data() {
    log_step "Restauration des données applicatives..."
    
    cd "${APP_DIR}"
    
    if [ -f "${BACKUP_DIR}/app_data.tar.gz" ]; then
        rm -rf data
        tar xzf "${BACKUP_DIR}/app_data.tar.gz" -C .
        log_info "Données applicatives restaurées"
    else
        log_warn "Aucune donnée applicative à restaurer"
    fi
}

start_services() {
    log_step "Démarrage des services..."
    
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" up -d
    
    log_info "Services démarrés"
}

verify_restore() {
    log_step "Vérification de la restauration..."
    
    sleep 10
    
    # Check if services are running
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" ps
    
    # Check backend health
    log_info "Test de l'API backend..."
    sleep 5
    
    if curl -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        log_info "✓ Backend opérationnel"
    else
        log_warn "⚠ Backend ne répond pas encore"
    fi
}

cleanup() {
    log_step "Nettoyage..."
    
    rm -rf "${RESTORE_TEMP_DIR}"
    
    log_info "Nettoyage terminé"
}

display_summary() {
    echo ""
    log_info "==================================================================="
    log_info "Restauration terminée!"
    log_info "==================================================================="
    echo ""
    log_info "Services restaurés:"
    cd "${APP_DIR}"
    docker compose -f "${COMPOSE_FILE}" ps
    echo ""
    log_info "Vérifications recommandées:"
    echo "  1. Tester l'accès: https://cutcosts.tech"
    echo "  2. Vérifier les logs: docker compose -f ${COMPOSE_FILE} logs -f"
    echo "  3. Tester les fonctionnalités principales"
    echo ""
    log_info "Fichiers de configuration sauvegardés:"
    echo "  - .env.before_restore (si elle existait)"
    echo ""
}

# Main execution
main() {
    local backup_file="$1"
    
    log_info "Démarrage de la restauration CloudWaste..."
    echo ""
    
    check_prerequisites "${backup_file}"
    confirm_restore
    stop_services
    extract_backup
    
    # Restore components
    if restore_config_files && \
       restore_docker_volumes && \
       restore_database && \
       restore_application_data; then
        
        start_services
        verify_restore
        cleanup
        display_summary
        
        log_info "Restauration réussie!"
        exit 0
    else
        log_error "La restauration a échoué"
        log_info "Consultez les logs pour plus de détails"
        cleanup
        exit 1
    fi
}

# Run main function
main "$@"

