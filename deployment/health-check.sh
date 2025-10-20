#!/bin/bash

###############################################################################
# CloudWaste Health Check Script
# Description: Vérifie l'état de santé de tous les services
# Usage: bash health-check.sh
###############################################################################

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
APP_DIR="/opt/cloudwaste"
COMPOSE_FILE="docker-compose.production.yml"
DOMAIN="cutcosts.tech"

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

check_docker() {
    section_header "Docker"
    
    if command -v docker &> /dev/null; then
        log_success "Docker est installé ($(docker --version | cut -d' ' -f3))"
    else
        log_failure "Docker n'est pas installé"
        return 1
    fi
    
    if docker compose version &> /dev/null; then
        log_success "Docker Compose est installé ($(docker compose version | cut -d' ' -f4))"
    else
        log_failure "Docker Compose n'est pas installé"
        return 1
    fi
    
    if systemctl is-active --quiet docker; then
        log_success "Service Docker actif"
    else
        log_failure "Service Docker inactif"
        return 1
    fi
}

check_containers() {
    section_header "Conteneurs Docker"
    
    if [ ! -d "${APP_DIR}" ]; then
        log_failure "Répertoire ${APP_DIR} non trouvé"
        return 1
    fi
    
    cd "${APP_DIR}"
    
    if [ ! -f "${COMPOSE_FILE}" ]; then
        log_failure "Fichier ${COMPOSE_FILE} non trouvé"
        return 1
    fi
    
    # Get list of expected services
    SERVICES=$(docker compose -f "${COMPOSE_FILE}" config --services)
    
    for service in $SERVICES; do
        if docker compose -f "${COMPOSE_FILE}" ps --status running | grep -q "$service"; then
            log_success "Conteneur $service: running"
        else
            log_failure "Conteneur $service: not running"
        fi
    done
}

check_database() {
    section_header "Base de données PostgreSQL"
    
    cd "${APP_DIR}"
    
    if docker compose -f "${COMPOSE_FILE}" exec -T postgres pg_isready -U cloudwaste &> /dev/null; then
        log_success "PostgreSQL répond"
    else
        log_failure "PostgreSQL ne répond pas"
        return 1
    fi
    
    # Check database exists
    if docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U cloudwaste -lqt | cut -d \| -f 1 | grep -qw cloudwaste; then
        log_success "Base de données 'cloudwaste' existe"
    else
        log_failure "Base de données 'cloudwaste' non trouvée"
    fi
    
    # Check connection count
    CONNECTIONS=$(docker compose -f "${COMPOSE_FILE}" exec -T postgres psql -U cloudwaste -d cloudwaste -t -c "SELECT count(*) FROM pg_stat_activity;" 2>/dev/null | tr -d ' ')
    if [ -n "$CONNECTIONS" ]; then
        log_success "Connexions actives: $CONNECTIONS"
    fi
}

check_redis() {
    section_header "Redis"
    
    cd "${APP_DIR}"
    
    if docker compose -f "${COMPOSE_FILE}" exec -T redis redis-cli ping 2>/dev/null | grep -q PONG; then
        log_success "Redis répond"
    else
        log_failure "Redis ne répond pas"
        return 1
    fi
    
    # Check memory usage
    REDIS_MEM=$(docker compose -f "${COMPOSE_FILE}" exec -T redis redis-cli info memory 2>/dev/null | grep "used_memory_human" | cut -d: -f2 | tr -d '\r')
    if [ -n "$REDIS_MEM" ]; then
        log_success "Mémoire Redis: $REDIS_MEM"
    fi
}

check_backend() {
    section_header "Backend API"
    
    # Check if backend container is running
    cd "${APP_DIR}"
    if ! docker compose -f "${COMPOSE_FILE}" ps --status running | grep -q backend; then
        log_failure "Backend container n'est pas actif"
        return 1
    fi
    
    # Check health endpoint (local)
    if curl -sf http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        log_success "Backend health check: OK"
    else
        log_failure "Backend health check: FAIL"
    fi
    
    # Check if API responds
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/docs 2>/dev/null)
    if [ "$RESPONSE" = "200" ]; then
        log_success "API docs accessible (HTTP $RESPONSE)"
    else
        log_warning "API docs non accessible (HTTP $RESPONSE)"
    fi
}

check_frontend() {
    section_header "Frontend"
    
    cd "${APP_DIR}"
    if ! docker compose -f "${COMPOSE_FILE}" ps --status running | grep -q frontend; then
        log_failure "Frontend container n'est pas actif"
        return 1
    fi
    
    # Check if frontend responds
    if curl -sf http://localhost:3000 > /dev/null 2>&1; then
        log_success "Frontend répond (localhost:3000)"
    else
        log_failure "Frontend ne répond pas"
    fi
}

check_celery() {
    section_header "Celery Workers"
    
    cd "${APP_DIR}"
    
    # Check worker
    if docker compose -f "${COMPOSE_FILE}" ps --status running | grep -q celery_worker; then
        log_success "Celery worker: running"
    else
        log_failure "Celery worker: not running"
    fi
    
    # Check beat
    if docker compose -f "${COMPOSE_FILE}" ps --status running | grep -q celery_beat; then
        log_success "Celery beat: running"
    else
        log_failure "Celery beat: not running"
    fi
    
    # Check celery status
    if docker compose -f "${COMPOSE_FILE}" exec -T celery_worker celery -A app.workers.celery_app inspect ping 2>/dev/null | grep -q "pong"; then
        log_success "Celery workers répondent"
    else
        log_warning "Celery workers ne répondent pas au ping"
    fi
}

check_nginx() {
    section_header "Nginx"
    
    if command -v nginx &> /dev/null; then
        log_success "Nginx est installé ($(nginx -v 2>&1 | cut -d'/' -f2))"
    else
        log_failure "Nginx n'est pas installé"
        return 1
    fi
    
    if systemctl is-active --quiet nginx; then
        log_success "Service Nginx actif"
    else
        log_failure "Service Nginx inactif"
        return 1
    fi
    
    if nginx -t &> /dev/null; then
        log_success "Configuration Nginx valide"
    else
        log_failure "Configuration Nginx invalide"
    fi
}

check_ssl() {
    section_header "SSL/TLS"
    
    if [ -f "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" ]; then
        log_success "Certificat SSL trouvé"
        
        # Check expiration
        EXPIRY=$(openssl x509 -enddate -noout -in "/etc/letsencrypt/live/${DOMAIN}/fullchain.pem" 2>/dev/null | cut -d= -f2)
        if [ -n "$EXPIRY" ]; then
            log_info "Expiration: $EXPIRY"
        fi
    else
        log_warning "Certificat SSL non trouvé"
    fi
}

check_external_access() {
    section_header "Accès Externe"
    
    # Check HTTPS
    RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN} 2>/dev/null)
    if [ "$RESPONSE" = "200" ]; then
        log_success "Site accessible via HTTPS (${DOMAIN})"
    else
        log_warning "Site non accessible via HTTPS (HTTP $RESPONSE)"
    fi
    
    # Check API
    API_RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" https://${DOMAIN}/api/v1/health 2>/dev/null)
    if [ "$API_RESPONSE" = "200" ]; then
        log_success "API accessible (${DOMAIN}/api/v1)"
    else
        log_warning "API non accessible (HTTP $API_RESPONSE)"
    fi
}

check_disk_space() {
    section_header "Espace Disque"
    
    DISK_USAGE=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
    
    if [ "$DISK_USAGE" -lt 70 ]; then
        log_success "Espace disque: ${DISK_USAGE}% utilisé"
    elif [ "$DISK_USAGE" -lt 85 ]; then
        log_warning "Espace disque: ${DISK_USAGE}% utilisé"
    else
        log_failure "Espace disque critique: ${DISK_USAGE}% utilisé"
    fi
    
    # Docker volumes
    DOCKER_USAGE=$(df -h /var/lib/docker | awk 'NR==2 {print $5}' | sed 's/%//')
    log_info "Docker volumes: ${DOCKER_USAGE}% utilisé"
}

check_memory() {
    section_header "Mémoire"
    
    TOTAL_MEM=$(free -h | awk 'NR==2 {print $2}')
    USED_MEM=$(free -h | awk 'NR==2 {print $3}')
    AVAILABLE_MEM=$(free -h | awk 'NR==2 {print $7}')
    
    log_info "Total: $TOTAL_MEM | Utilisée: $USED_MEM | Disponible: $AVAILABLE_MEM"
    
    MEM_PERCENT=$(free | awk 'NR==2 {printf "%.0f", $3/$2*100}')
    
    if [ "$MEM_PERCENT" -lt 80 ]; then
        log_success "Utilisation mémoire: ${MEM_PERCENT}%"
    elif [ "$MEM_PERCENT" -lt 90 ]; then
        log_warning "Utilisation mémoire: ${MEM_PERCENT}%"
    else
        log_failure "Utilisation mémoire critique: ${MEM_PERCENT}%"
    fi
}

check_logs() {
    section_header "Logs Récents"
    
    cd "${APP_DIR}"
    
    # Check for errors in logs
    ERROR_COUNT=$(docker compose -f "${COMPOSE_FILE}" logs --tail=100 2>/dev/null | grep -i "error" | wc -l)
    
    if [ "$ERROR_COUNT" -eq 0 ]; then
        log_success "Aucune erreur récente dans les logs"
    elif [ "$ERROR_COUNT" -lt 5 ]; then
        log_warning "$ERROR_COUNT erreurs trouvées dans les logs récents"
    else
        log_failure "$ERROR_COUNT erreurs trouvées dans les logs récents"
    fi
}

display_summary() {
    echo ""
    echo "================================================================="
    echo "                    RÉSUMÉ DU HEALTH CHECK"
    echo "================================================================="
    echo -e "${GREEN}Réussis:${NC}    $CHECKS_PASSED"
    echo -e "${YELLOW}Warnings:${NC}   $CHECKS_WARNING"
    echo -e "${RED}Échoués:${NC}    $CHECKS_FAILED"
    echo "================================================================="
    
    if [ "$CHECKS_FAILED" -eq 0 ] && [ "$CHECKS_WARNING" -eq 0 ]; then
        echo -e "${GREEN}✓ Tous les services sont opérationnels!${NC}"
        return 0
    elif [ "$CHECKS_FAILED" -eq 0 ]; then
        echo -e "${YELLOW}⚠ Système fonctionnel avec warnings${NC}"
        return 0
    else
        echo -e "${RED}✗ Des problèmes ont été détectés${NC}"
        return 1
    fi
}

# Main execution
main() {
    echo "================================================================="
    echo "            CloudWaste Production Health Check"
    echo "================================================================="
    echo "Date: $(date)"
    echo "Hostname: $(hostname)"
    echo "================================================================="
    
    check_docker
    check_containers
    check_database
    check_redis
    check_backend
    check_frontend
    check_celery
    check_nginx
    check_ssl
    check_external_access
    check_disk_space
    check_memory
    check_logs
    
    display_summary
}

main

