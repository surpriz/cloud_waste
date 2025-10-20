#!/bin/bash

###############################################################################
# CloudWaste VPS Setup Script
# Description: Sécurise et configure un VPS Ubuntu pour la production
# Usage: bash setup-vps.sh
# IMPORTANT: À exécuter en tant que root sur le VPS
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
VPS_USER="cloudwaste"
VPS_HOME="/home/${VPS_USER}"
APP_DIR="/opt/cloudwaste"
DOMAIN="cutcosts.tech"

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

check_root() {
    if [ "$EUID" -ne 0 ]; then
        log_error "Ce script doit être exécuté en tant que root"
        exit 1
    fi
}

# Main setup functions
setup_user() {
    log_info "Création de l'utilisateur ${VPS_USER}..."
    
    if id "${VPS_USER}" &>/dev/null; then
        log_warn "L'utilisateur ${VPS_USER} existe déjà"
    else
        useradd -m -s /bin/bash -G sudo "${VPS_USER}"
        log_info "Utilisateur ${VPS_USER} créé avec succès"
    fi
    
    # Set password
    log_info "Définir un mot de passe pour ${VPS_USER}:"
    passwd "${VPS_USER}"
    
    # Configure sudo without password for deployment tasks
    echo "${VPS_USER} ALL=(ALL) NOPASSWD: /usr/bin/docker, /usr/bin/docker-compose, /usr/bin/systemctl, /usr/sbin/nginx, /usr/bin/certbot" > /etc/sudoers.d/${VPS_USER}
    chmod 0440 /etc/sudoers.d/${VPS_USER}
}

setup_ssh_keys() {
    log_info "Configuration des clés SSH..."
    
    # Create .ssh directory for new user
    mkdir -p "${VPS_HOME}/.ssh"
    chmod 700 "${VPS_HOME}/.ssh"
    
    # Generate SSH key pair on the server (optional, for server-to-server communication)
    if [ ! -f "${VPS_HOME}/.ssh/id_rsa" ]; then
        log_info "Génération d'une paire de clés SSH..."
        su - "${VPS_USER}" -c "ssh-keygen -t rsa -b 4096 -f ${VPS_HOME}/.ssh/id_rsa -N ''"
    fi
    
    # Copy root's authorized_keys if they exist
    if [ -f /root/.ssh/authorized_keys ]; then
        log_info "Copie des clés autorisées depuis root..."
        cp /root/.ssh/authorized_keys "${VPS_HOME}/.ssh/authorized_keys"
    else
        # Create empty authorized_keys
        touch "${VPS_HOME}/.ssh/authorized_keys"
        log_warn "Aucune clé SSH trouvée. Vous devrez ajouter votre clé publique manuellement."
        log_info "Pour ajouter votre clé, exécutez sur votre machine locale:"
        log_info "ssh-copy-id ${VPS_USER}@${DOMAIN}"
    fi
    
    chmod 600 "${VPS_HOME}/.ssh/authorized_keys"
    chown -R "${VPS_USER}:${VPS_USER}" "${VPS_HOME}/.ssh"
    
    # Configure SSH security
    log_info "Sécurisation de la configuration SSH..."
    sed -i.bak \
        -e 's/^#\?PermitRootLogin.*/PermitRootLogin no/' \
        -e 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' \
        -e 's/^#\?PubkeyAuthentication.*/PubkeyAuthentication yes/' \
        -e 's/^#\?X11Forwarding.*/X11Forwarding no/' \
        /etc/ssh/sshd_config
    
    log_info "Redémarrage du service SSH..."
    systemctl restart sshd
    
    log_warn "IMPORTANT: Testez la connexion SSH dans un autre terminal avant de fermer cette session!"
    log_info "Test: ssh ${VPS_USER}@${DOMAIN}"
}

update_system() {
    log_info "Mise à jour du système..."
    apt-get update
    apt-get upgrade -y
    apt-get install -y \
        apt-transport-https \
        ca-certificates \
        curl \
        gnupg \
        lsb-release \
        software-properties-common \
        git \
        wget \
        ufw \
        fail2ban \
        unattended-upgrades \
        htop \
        vim \
        net-tools \
        certbot \
        python3-certbot-nginx
}

setup_firewall() {
    log_info "Configuration du firewall UFW..."
    
    # Allow SSH first (critical!)
    ufw allow 22/tcp
    
    # Allow HTTP/HTTPS
    ufw allow 80/tcp
    ufw allow 443/tcp
    
    # Allow Portainer
    ufw allow 9443/tcp
    
    # Enable UFW
    ufw --force enable
    
    log_info "Firewall configuré et activé"
    ufw status verbose
}

setup_fail2ban() {
    log_info "Configuration de Fail2Ban..."
    
    cat > /etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5
destemail = root@localhost
sendername = Fail2Ban

[sshd]
enabled = true
port = 22
filter = sshd
logpath = /var/log/auth.log
maxretry = 5
EOF
    
    systemctl enable fail2ban
    systemctl restart fail2ban
    log_info "Fail2Ban configuré et activé"
}

setup_unattended_upgrades() {
    log_info "Configuration des mises à jour automatiques..."
    
    cat > /etc/apt/apt.conf.d/50unattended-upgrades <<EOF
Unattended-Upgrade::Allowed-Origins {
    "\${distro_id}:\${distro_codename}-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF
    
    cat > /etc/apt/apt.conf.d/20auto-upgrades <<EOF
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
    
    log_info "Mises à jour automatiques de sécurité configurées"
}

install_docker() {
    log_info "Installation de Docker..."
    
    # Remove old versions
    apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Set up the repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker Engine
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Add user to docker group
    usermod -aG docker "${VPS_USER}"
    
    # Enable Docker service
    systemctl enable docker
    systemctl start docker
    
    log_info "Docker installé avec succès"
    docker --version
    docker compose version
}

install_portainer() {
    log_info "Installation de Portainer..."
    
    docker volume create portainer_data
    
    docker run -d \
        -p 9443:9443 \
        -p 8000:8000 \
        --name portainer \
        --restart=always \
        -v /var/run/docker.sock:/var/run/docker.sock \
        -v portainer_data:/data \
        portainer/portainer-ce:latest
    
    log_info "Portainer installé - Accès: https://${DOMAIN}:9443"
}

install_nginx() {
    log_info "Installation de Nginx..."
    
    apt-get install -y nginx
    
    # Backup default config
    mv /etc/nginx/sites-enabled/default /etc/nginx/sites-enabled/default.bak 2>/dev/null || true
    
    systemctl enable nginx
    systemctl start nginx
    
    log_info "Nginx installé avec succès"
}

install_ollama() {
    log_info "Installation d'Ollama..."
    
    curl -fsSL https://ollama.com/install.sh | sh
    
    # Enable Ollama service
    systemctl enable ollama
    systemctl start ollama
    
    log_info "Ollama installé avec succès"
    log_info "Pour télécharger un modèle: ollama pull llama2"
}

install_netdata() {
    log_info "Installation de Netdata (monitoring)..."
    
    # Install Netdata
    wget -O /tmp/netdata-kickstart.sh https://get.netdata.cloud/kickstart.sh
    sh /tmp/netdata-kickstart.sh --dont-wait --stable-channel
    
    # Configure Netdata to be accessible via Nginx proxy
    cat > /etc/nginx/sites-available/netdata <<EOF
location = /netdata {
    return 301 /netdata/;
}

location ~ /netdata/(?<ndpath>.*) {
    proxy_redirect off;
    proxy_set_header Host \$host;
    
    proxy_set_header X-Forwarded-Host \$host;
    proxy_set_header X-Forwarded-Server \$host;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_http_version 1.1;
    proxy_pass_request_headers on;
    proxy_set_header Connection "keep-alive";
    proxy_store off;
    proxy_pass http://127.0.0.1:19999/\$ndpath\$is_args\$args;
    
    gzip on;
    gzip_proxied any;
    gzip_types *;
}
EOF
    
    log_info "Netdata installé - Sera accessible via https://${DOMAIN}/netdata après configuration SSL"
}

setup_app_directory() {
    log_info "Création de la structure de répertoires..."
    
    mkdir -p "${APP_DIR}"
    mkdir -p "${APP_DIR}/backups"
    mkdir -p "${APP_DIR}/data"
    
    chown -R "${VPS_USER}:${VPS_USER}" "${APP_DIR}"
    
    log_info "Répertoire ${APP_DIR} créé"
}

setup_backup_cron() {
    log_info "Configuration des backups automatiques..."
    
    # Create cron job for daily backups at 2 AM
    cat > /etc/cron.d/cloudwaste-backup <<EOF
# CloudWaste daily backup at 2 AM
0 2 * * * ${VPS_USER} ${APP_DIR}/backup.sh >> /var/log/cloudwaste-backup.log 2>&1
EOF
    
    chmod 0644 /etc/cron.d/cloudwaste-backup
    
    # Create log file
    touch /var/log/cloudwaste-backup.log
    chown "${VPS_USER}:${VPS_USER}" /var/log/cloudwaste-backup.log
    
    log_info "Backup automatique configuré (tous les jours à 2h du matin)"
}

configure_docker_logging() {
    log_info "Configuration du logging Docker..."
    
    mkdir -p /etc/docker
    cat > /etc/docker/daemon.json <<EOF
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF
    
    systemctl restart docker
    log_info "Logging Docker configuré (rotation automatique)"
}

display_summary() {
    log_info "==================================================================="
    log_info "Configuration du VPS terminée avec succès!"
    log_info "==================================================================="
    echo ""
    log_info "Prochaines étapes:"
    echo "  1. TESTEZ la connexion SSH: ssh ${VPS_USER}@${DOMAIN}"
    echo "  2. Configurez le DNS pour ${DOMAIN} → $(curl -s ifconfig.me)"
    echo "  3. Clonez le repository dans ${APP_DIR}"
    echo "  4. Créez le fichier .env de production"
    echo "  5. Exécutez le script deploy.sh"
    echo "  6. Configurez SSL: sudo certbot --nginx -d ${DOMAIN} -d www.${DOMAIN}"
    echo ""
    log_info "Services installés:"
    echo "  - Docker & Docker Compose"
    echo "  - Nginx"
    echo "  - Certbot (Let's Encrypt)"
    echo "  - Portainer: https://${DOMAIN}:9443"
    echo "  - Ollama"
    echo "  - Netdata: https://${DOMAIN}/netdata (après SSL)"
    echo "  - Fail2Ban (protection SSH)"
    echo "  - UFW Firewall"
    echo ""
    log_info "Sécurité:"
    echo "  - Connexion root désactivée"
    echo "  - Authentification par mot de passe désactivée"
    echo "  - Firewall activé (ports 22, 80, 443, 9443)"
    echo "  - Fail2Ban actif"
    echo "  - Mises à jour de sécurité automatiques"
    echo ""
    log_warn "IMPORTANT: Ne fermez pas cette session avant d'avoir testé la connexion SSH!"
}

# Main execution
main() {
    log_info "Démarrage de la configuration du VPS CloudWaste..."
    echo ""
    
    check_root
    
    log_info "Étape 1/13: Mise à jour du système..."
    update_system
    
    log_info "Étape 2/13: Création de l'utilisateur..."
    setup_user
    
    log_info "Étape 3/13: Configuration SSH..."
    setup_ssh_keys
    
    log_info "Étape 4/13: Configuration du firewall..."
    setup_firewall
    
    log_info "Étape 5/13: Configuration de Fail2Ban..."
    setup_fail2ban
    
    log_info "Étape 6/13: Configuration des mises à jour automatiques..."
    setup_unattended_upgrades
    
    log_info "Étape 7/13: Installation de Docker..."
    install_docker
    
    log_info "Étape 8/13: Configuration du logging Docker..."
    configure_docker_logging
    
    log_info "Étape 9/13: Installation de Portainer..."
    install_portainer
    
    log_info "Étape 10/13: Installation de Nginx..."
    install_nginx
    
    log_info "Étape 11/13: Installation d'Ollama..."
    install_ollama
    
    log_info "Étape 12/13: Installation de Netdata..."
    install_netdata
    
    log_info "Étape 13/13: Création de la structure de répertoires..."
    setup_app_directory
    setup_backup_cron
    
    display_summary
}

# Run main function
main

