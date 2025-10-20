#!/bin/bash

###############################################################################
# CloudWaste Backup Script
# Description: Sauvegarde complète de la base de données et des fichiers
# Usage: bash backup.sh
# Cron: 0 2 * * * /opt/cloudwaste/backup.sh
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Configuration
APP_DIR="/opt/cloudwaste"
BACKUP_DIR="${APP_DIR}/backups"
COMPOSE_FILE="docker-compose.production.yml"
RETENTION_DAYS=7  # Garder les backups pendant 7 jours
TIMESTAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_NAME="cloudwaste-backup-${TIMESTAMP}"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_NAME}"

# Email notification (optionnel)
SEND_EMAIL=false
EMAIL_TO="admin@cutcosts.tech"

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

send_notification() {
    local status=$1
    local message=$2
    
    if [ "$SEND_EMAIL" = true ]; then
        echo "${message}" | mail -s "CloudWaste Backup ${status}" "${EMAIL_TO}" 2>/dev/null || true
    fi
}

check_prerequisites() {
    if [ ! -d "${APP_DIR}" ]; then
        log_error "Répertoire ${APP_DIR} non trouvé"
        exit 1
    fi
    
    cd "${APP_DIR}"
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_error "Fichier ${COMPOSE_FILE} non trouvé"
        exit 1
    fi
    
    # Create backup directory if it doesn't exist
    mkdir -p "${BACKUP_DIR}"
    mkdir -p "${BACKUP_PATH}"
}

backup_database() {
    log_info "Backup de la base de données PostgreSQL..."
    
    # Export database
    docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_dump -U cloudwaste -d cloudwaste > "${BACKUP_PATH}/database.sql"
    
    # Check if backup file is not empty
    if [ ! -s "${BACKUP_PATH}/database.sql" ]; then
        log_error "Le backup de la base de données est vide"
        return 1
    fi
    
    local db_size=$(du -h "${BACKUP_PATH}/database.sql" | cut -f1)
    log_info "Base de données sauvegardée (${db_size})"
}

backup_docker_volumes() {
    log_info "Backup des volumes Docker..."
    
    # Get list of volumes used by our compose file
    local volumes=$(docker compose -f "${COMPOSE_FILE}" config --volumes)
    
    for volume in $volumes; do
        log_info "Backup du volume: ${volume}"
        
        # Export volume data
        docker run --rm \
            -v "${volume}:/volume" \
            -v "${BACKUP_PATH}:/backup" \
            alpine tar czf "/backup/volume_${volume}.tar.gz" -C /volume .
    done
    
    log_info "Volumes Docker sauvegardés"
}

backup_config_files() {
    log_info "Backup des fichiers de configuration..."
    
    # Backup important files
    cp .env "${BACKUP_PATH}/.env" 2>/dev/null || log_warn "Fichier .env non trouvé"
    cp encryption_key "${BACKUP_PATH}/encryption_key" 2>/dev/null || log_warn "Fichier encryption_key non trouvé"
    cp "${COMPOSE_FILE}" "${BACKUP_PATH}/${COMPOSE_FILE}"
    
    # Backup nginx config if it exists
    if [ -f /etc/nginx/sites-available/cutcosts.tech ]; then
        sudo cp /etc/nginx/sites-available/cutcosts.tech "${BACKUP_PATH}/nginx-cutcosts.tech.conf"
    fi
    
    log_info "Fichiers de configuration sauvegardés"
}

backup_application_data() {
    log_info "Backup des données applicatives..."
    
    # Backup any uploaded files or generated data
    if [ -d "${APP_DIR}/data" ]; then
        tar czf "${BACKUP_PATH}/app_data.tar.gz" -C "${APP_DIR}" data
        log_info "Données applicatives sauvegardées"
    fi
}

create_backup_archive() {
    log_info "Création de l'archive finale..."
    
    cd "${BACKUP_DIR}"
    tar czf "${BACKUP_NAME}.tar.gz" "${BACKUP_NAME}"
    
    # Remove temporary backup directory
    rm -rf "${BACKUP_PATH}"
    
    local archive_size=$(du -h "${BACKUP_NAME}.tar.gz" | cut -f1)
    log_info "Archive créée: ${BACKUP_NAME}.tar.gz (${archive_size})"
}

create_backup_manifest() {
    log_info "Création du manifeste de backup..."
    
    cat > "${BACKUP_DIR}/${BACKUP_NAME}.txt" <<EOF
CloudWaste Backup Manifest
==========================
Backup ID: ${BACKUP_NAME}
Date: $(date '+%Y-%m-%d %H:%M:%S')
Hostname: $(hostname)
Git Commit: $(git rev-parse HEAD 2>/dev/null || echo "N/A")
Git Branch: $(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "N/A")

Contents:
- PostgreSQL database dump
- Docker volumes
- Configuration files (.env, encryption_key, docker-compose)
- Nginx configuration
- Application data

Archive: ${BACKUP_NAME}.tar.gz
Size: $(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)

Restore command:
bash /opt/cloudwaste/restore.sh ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz
EOF
    
    log_info "Manifeste créé"
}

cleanup_old_backups() {
    log_info "Nettoyage des anciens backups (> ${RETENTION_DAYS} jours)..."
    
    # Delete backups older than RETENTION_DAYS
    find "${BACKUP_DIR}" -name "cloudwaste-backup-*.tar.gz" -type f -mtime +${RETENTION_DAYS} -delete
    find "${BACKUP_DIR}" -name "cloudwaste-backup-*.txt" -type f -mtime +${RETENTION_DAYS} -delete
    
    local backup_count=$(find "${BACKUP_DIR}" -name "cloudwaste-backup-*.tar.gz" | wc -l)
    log_info "Backups actuels: ${backup_count}"
}

verify_backup() {
    log_info "Vérification de l'intégrité du backup..."
    
    # Test if archive can be extracted
    if tar tzf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" > /dev/null 2>&1; then
        log_info "✓ Archive valide"
        return 0
    else
        log_error "✗ Archive corrompue"
        return 1
    fi
}

display_summary() {
    echo ""
    log_info "==================================================================="
    log_info "Backup terminé avec succès!"
    log_info "==================================================================="
    echo ""
    log_info "Détails du backup:"
    echo "  - Fichier:      ${BACKUP_NAME}.tar.gz"
    echo "  - Emplacement:  ${BACKUP_DIR}/"
    echo "  - Taille:       $(du -h "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" | cut -f1)"
    echo "  - Date:         $(date '+%Y-%m-%d %H:%M:%S')"
    echo ""
    log_info "Backups disponibles:"
    ls -lh "${BACKUP_DIR}"/cloudwaste-backup-*.tar.gz 2>/dev/null | tail -5 || echo "  Aucun"
    echo ""
    log_info "Pour restaurer ce backup:"
    echo "  bash /opt/cloudwaste/restore.sh ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    echo ""
}

# Main execution
main() {
    log_info "Démarrage du backup CloudWaste - ${TIMESTAMP}"
    echo ""
    
    # Redirect all output to log file as well
    exec 1> >(tee -a "${BACKUP_DIR}/backup.log")
    exec 2>&1
    
    if check_prerequisites && \
       backup_database && \
       backup_docker_volumes && \
       backup_config_files && \
       backup_application_data && \
       create_backup_archive && \
       create_backup_manifest && \
       verify_backup; then
        
        cleanup_old_backups
        display_summary
        send_notification "SUCCESS" "Backup CloudWaste réussi: ${BACKUP_NAME}.tar.gz"
        exit 0
    else
        log_error "Le backup a échoué"
        send_notification "FAILED" "Backup CloudWaste échoué - vérifiez les logs"
        exit 1
    fi
}

# Run main function
main

