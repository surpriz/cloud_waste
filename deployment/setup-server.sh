#!/bin/bash

# ============================================================================
# CloudWaste - VPS Initial Setup Script
# ============================================================================
#
# This script sets up a fresh Ubuntu VPS for CloudWaste production deployment
#
# What it does:
#   1. Install Docker & Docker Compose
#   2. Configure firewall (UFW)
#   3. Install Certbot for SSL certificates
#   4. Clone repository to /opt/cloudwaste
#   5. Generate SSL certificates (Let's Encrypt)
#   6. Create .env.prod with secure secrets
#   7. Deploy the application
#
# Usage:
#   ssh administrator@155.117.43.17
#   wget https://raw.githubusercontent.com/YOUR_REPO/master/deployment/setup-server.sh
#   chmod +x setup-server.sh
#   sudo ./setup-server.sh
#
# ============================================================================

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
DOMAIN="cutcosts.tech"
EMAIL="jerome0laval@gmail.com"  # For Let's Encrypt notifications
APP_DIR="/opt/cloudwaste"
GITHUB_REPO="https://github.com/surpriz/cloud_waste"  # TODO: Update with your repo URL

# ============================================================================
# Helper Functions
# ============================================================================

print_header() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}  $1${BLUE}║${NC}"
    echo -e "${BLUE}║${NC}                                                                    ${BLUE}║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_step() {
    echo -e "${GREEN}▶${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

generate_secret() {
    openssl rand -hex 32
}

# ============================================================================
# Pre-flight Checks
# ============================================================================

print_header "   🚀 CloudWaste - VPS Setup Script                              "

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    print_error "This script must be run as root (use sudo)"
    exit 1
fi

print_success "Running as root"

# Check Ubuntu version
if [ -f /etc/os-release ]; then
    . /etc/os-release
    print_success "Detected: $PRETTY_NAME"
else
    print_warning "Cannot detect OS version, continuing anyway..."
fi

# ============================================================================
# Step 1: System Update
# ============================================================================

print_header "   📦 Step 1/7: System Update                                    "

print_step "Updating package lists..."
apt-get update -qq

print_step "Upgrading existing packages..."
DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -qq

print_success "System updated"

# ============================================================================
# Step 2: Install Docker
# ============================================================================

print_header "   🐳 Step 2/7: Install Docker                                   "

if command -v docker &> /dev/null; then
    print_success "Docker already installed ($(docker --version))"
else
    print_step "Installing Docker dependencies..."
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release

    print_step "Adding Docker's official GPG key..."
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg

    print_step "Setting up Docker repository..."
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null

    print_step "Installing Docker Engine..."
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

    print_step "Starting Docker service..."
    systemctl start docker
    systemctl enable docker

    print_success "Docker installed successfully ($(docker --version))"
fi

# ============================================================================
# Step 3: Configure Firewall
# ============================================================================

print_header "   🔥 Step 3/7: Configure Firewall (UFW)                         "

print_step "Installing UFW..."
apt-get install -y -qq ufw

print_step "Configuring firewall rules..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow 22/tcp comment 'SSH'
ufw allow 80/tcp comment 'HTTP'
ufw allow 443/tcp comment 'HTTPS'

print_step "Enabling firewall..."
ufw --force enable

print_success "Firewall configured (ports 22, 80, 443 open)"

# ============================================================================
# Step 4: Install Certbot for SSL
# ============================================================================

print_header "   🔐 Step 4/7: Install Certbot (Let's Encrypt)                  "

print_step "Installing Certbot..."
apt-get install -y -qq certbot

print_success "Certbot installed ($(certbot --version | head -n1))"

# ============================================================================
# Step 5: Clone Repository
# ============================================================================

print_header "   📥 Step 5/7: Clone CloudWaste Repository                      "

if [ -d "$APP_DIR" ]; then
    print_warning "Directory $APP_DIR already exists"
    read -p "Do you want to remove it and re-clone? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        rm -rf "$APP_DIR"
    else
        print_step "Skipping clone, using existing directory"
    fi
fi

if [ ! -d "$APP_DIR" ]; then
    print_step "Cloning repository to $APP_DIR..."
    git clone "$GITHUB_REPO" "$APP_DIR"
    print_success "Repository cloned successfully"
else
    print_success "Using existing repository"
fi

cd "$APP_DIR"

# ============================================================================
# Step 6: Generate SSL Certificates
# ============================================================================

print_header "   🔐 Step 6/7: Generate SSL Certificates                        "

if [ -d "/etc/letsencrypt/live/$DOMAIN" ]; then
    print_success "SSL certificates already exist for $DOMAIN"
else
    print_step "Generating SSL certificate for $DOMAIN..."
    print_warning "Make sure DNS is pointing to this server (155.117.43.17)"

    read -p "Press Enter to continue with SSL certificate generation..."

    certbot certonly --standalone \
        --non-interactive \
        --agree-tos \
        --email "$EMAIL" \
        -d "$DOMAIN" \
        -d "www.$DOMAIN"

    print_success "SSL certificates generated"

    # Setup auto-renewal
    print_step "Setting up automatic renewal..."
    (crontab -l 2>/dev/null; echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker exec cloudwaste_nginx nginx -s reload'") | crontab -
    print_success "Auto-renewal configured (daily check at 3 AM)"
fi

# ============================================================================
# Step 7: Create .env.prod with Secrets
# ============================================================================

print_header "   🔑 Step 7/7: Generate Production Environment File             "

if [ -f "$APP_DIR/.env.prod" ]; then
    print_warning ".env.prod already exists"
    read -p "Do you want to regenerate it? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_step "Skipping .env.prod generation"
    else
        GENERATE_ENV=true
    fi
else
    GENERATE_ENV=true
fi

if [ "$GENERATE_ENV" = true ]; then
    print_step "Generating secure secrets..."

    SECRET_KEY=$(generate_secret)
    JWT_SECRET=$(generate_secret)
    POSTGRES_PASSWORD=$(generate_secret)

    print_step "Creating .env.prod file..."

    cat > "$APP_DIR/.env.prod" <<EOF
# ============================================================================
# CloudWaste - Production Environment Variables
# Auto-generated by setup-server.sh on $(date)
# ============================================================================

# Application
APP_NAME=CloudWaste
APP_ENV=production
DEBUG=False

# Security
SECRET_KEY=$SECRET_KEY
JWT_SECRET_KEY=$JWT_SECRET
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
ENCRYPTION_KEY=AUTO_GENERATED_DO_NOT_CHANGE

# Database
POSTGRES_USER=cloudwaste
POSTGRES_PASSWORD=$POSTGRES_PASSWORD
POSTGRES_DB=cloudwaste
DATABASE_URL=postgresql+asyncpg://cloudwaste:$POSTGRES_PASSWORD@postgres:5432/cloudwaste

# Redis
REDIS_URL=redis://redis:6379/0

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Email - CONFIGURE MANUALLY
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=YOUR_SENDGRID_API_KEY_HERE
EMAILS_FROM_EMAIL=noreply@cutcosts.tech
EMAILS_FROM_NAME=CloudWaste

# Domain
DOMAIN=cutcosts.tech
NEXT_PUBLIC_API_URL=https://cutcosts.tech
NEXT_PUBLIC_APP_NAME=CloudWaste
EOF

    chmod 600 "$APP_DIR/.env.prod"
    print_success ".env.prod created with secure secrets"

    print_warning "⚠️  IMPORTANT: Edit .env.prod to configure email settings:"
    echo "   nano $APP_DIR/.env.prod"
fi

# ============================================================================
# Final Steps
# ============================================================================

print_header "   ✅ Setup Complete!                                            "

echo ""
echo -e "${GREEN}Next steps:${NC}"
echo ""
echo "1. Configure email settings (optional):"
echo "   ${YELLOW}nano $APP_DIR/.env.prod${NC}"
echo ""
echo "2. Deploy the application:"
echo "   ${YELLOW}cd $APP_DIR${NC}"
echo "   ${YELLOW}bash deployment/quick-deploy.sh${NC}"
echo ""
echo "3. Check application status:"
echo "   ${YELLOW}docker ps${NC}"
echo ""
echo "4. View logs:"
echo "   ${YELLOW}docker logs -f cloudwaste_backend${NC}"
echo "   ${YELLOW}docker logs -f cloudwaste_frontend${NC}"
echo ""
echo -e "${GREEN}Your application will be available at:${NC}"
echo "   🌐 https://cutcosts.tech"
echo "   📚 https://cutcosts.tech/api/docs"
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════════════${NC}"
echo ""
