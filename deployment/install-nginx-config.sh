#!/bin/bash

###############################################################################
# Install Nginx Configuration for CloudWaste
# Description: Installe et configure Nginx pour cutcosts.tech
# Usage: sudo bash install-nginx-config.sh
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Ce script doit être exécuté avec sudo"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
NGINX_CONF="${SCRIPT_DIR}/nginx/cutcosts.tech.conf"
DOMAIN="cutcosts.tech"

log_info "Installation de la configuration Nginx pour ${DOMAIN}..."

# Check if Nginx is installed
if ! command -v nginx &> /dev/null; then
    log_error "Nginx n'est pas installé"
    log_info "Installez Nginx: sudo apt install nginx"
    exit 1
fi

# Check if config file exists
if [ ! -f "${NGINX_CONF}" ]; then
    log_error "Fichier de configuration non trouvé: ${NGINX_CONF}"
    exit 1
fi

# Backup existing config if it exists
if [ -f "/etc/nginx/sites-available/${DOMAIN}" ]; then
    log_warn "Une configuration existe déjà, création d'un backup..."
    cp "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-available/${DOMAIN}.backup.$(date +%Y%m%d-%H%M%S)"
fi

# Copy config file
log_info "Copie du fichier de configuration..."
cp "${NGINX_CONF}" "/etc/nginx/sites-available/${DOMAIN}"

# Create symlink if it doesn't exist
if [ ! -L "/etc/nginx/sites-enabled/${DOMAIN}" ]; then
    log_info "Création du lien symbolique..."
    ln -s "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
else
    log_info "Le lien symbolique existe déjà"
fi

# Remove default site if it exists
if [ -L "/etc/nginx/sites-enabled/default" ]; then
    log_info "Suppression du site par défaut..."
    rm "/etc/nginx/sites-enabled/default"
fi

# Test Nginx configuration
log_info "Test de la configuration Nginx..."
if nginx -t; then
    log_info "✓ Configuration Nginx valide"
else
    log_error "✗ Configuration Nginx invalide"
    log_error "Restaurez le backup si nécessaire"
    exit 1
fi

# Reload Nginx
log_info "Rechargement de Nginx..."
systemctl reload nginx

log_info "Configuration Nginx installée avec succès!"
echo ""
log_info "Prochaines étapes:"
echo "  1. Assurez-vous que le DNS pointe vers ce serveur"
echo "  2. Obtenez un certificat SSL: sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
echo "  3. Testez votre site: http://${DOMAIN}"
echo ""
log_info "Fichiers de configuration:"
echo "  - Config: /etc/nginx/sites-available/${DOMAIN}"
echo "  - Lien: /etc/nginx/sites-enabled/${DOMAIN}"
echo ""
log_info "Logs:"
echo "  - Access: /var/log/nginx/${DOMAIN}.access.log"
echo "  - Error: /var/log/nginx/${DOMAIN}.error.log"

