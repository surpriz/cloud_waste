#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔍 DIAGNOSTIC COMPLET - CloudWaste Production              ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 1. Vérifier Nginx et SSL
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  VÉRIFICATION NGINX ET SSL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Status Nginx
if sudo systemctl is-active --quiet nginx; then
    echo -e "${GREEN}✅ Nginx actif${NC}"
else
    echo -e "${RED}❌ Nginx inactif${NC}"
fi

# Test config Nginx
echo ""
echo "📝 Test configuration Nginx:"
sudo nginx -t

# Vérifier les certificats SSL
echo ""
echo "🔒 Certificats SSL installés:"
sudo certbot certificates

# Lister les sites Nginx activés
echo ""
echo "📂 Sites Nginx actifs:"
ls -la /etc/nginx/sites-enabled/

# Voir la config Nginx du site
echo ""
echo "📄 Configuration Nginx pour cutcosts.tech:"
if [ -f /etc/nginx/sites-enabled/cutcosts.tech ]; then
    echo -e "${GREEN}✅ Fichier existe${NC}"
    grep -E "listen|server_name|location|proxy_pass" /etc/nginx/sites-enabled/cutcosts.tech | head -30
else
    echo -e "${RED}❌ Fichier de config non trouvé${NC}"
fi

# 2. Vérifier les conteneurs Docker
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  VÉRIFICATION CONTENEURS DOCKER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cd /opt/cloudwaste
docker compose -f docker-compose.production.yml ps

# 3. Test des endpoints
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  TEST DES ENDPOINTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Test Backend direct
echo ""
echo "🔧 Test Backend (localhost:8000):"
curl -s http://localhost:8000/api/v1/health | jq . || echo "❌ Backend ne répond pas"

# Test Frontend direct
echo ""
echo "🔧 Test Frontend (localhost:3000):"
curl -s -o /dev/null -w "%{http_code}" http://localhost:3000
echo ""

# Test via Nginx (HTTP)
echo ""
echo "🌐 Test via Nginx HTTP:"
curl -s -o /dev/null -w "%{http_code}" http://localhost/
echo ""

# Test via Nginx (HTTPS local)
echo ""
echo "🌐 Test via Nginx HTTPS:"
curl -s -k -o /dev/null -w "%{http_code}" https://localhost/
echo ""

# Test API via Nginx
echo ""
echo "📡 Test API Docs via Nginx:"
curl -s http://localhost/api/v1/docs | head -20

# 4. Vérifier Portainer
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  VÉRIFICATION PORTAINER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if docker ps | grep -q portainer; then
    echo -e "${GREEN}✅ Portainer actif${NC}"
    docker ps | grep portainer
else
    echo -e "${RED}❌ Portainer inactif${NC}"
fi

# 5. Vérifier Netdata
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  VÉRIFICATION NETDATA"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if sudo systemctl is-active --quiet netdata; then
    echo -e "${GREEN}✅ Netdata actif${NC}"
    sudo systemctl status netdata --no-pager -l | head -10
    echo ""
    echo "Test accès local:"
    curl -s -o /dev/null -w "%{http_code}" http://localhost:19999
    echo ""
else
    echo -e "${RED}❌ Netdata inactif${NC}"
fi

# 6. Vérifier les Backups
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  VÉRIFICATION BACKUPS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Cron job
echo "📅 Cron job backup:"
if [ -f /etc/cron.d/cloudwaste-backup ]; then
    echo -e "${GREEN}✅ Cron job configuré${NC}"
    cat /etc/cron.d/cloudwaste-backup
else
    echo -e "${RED}❌ Cron job non trouvé${NC}"
fi

# Dossier backups
echo ""
echo "📦 Backups existants:"
if [ -d /opt/cloudwaste/backups ]; then
    ls -lh /opt/cloudwaste/backups/ | tail -10
else
    echo -e "${YELLOW}⚠️  Dossier backups non trouvé${NC}"
fi

# Log backup
echo ""
echo "📝 Derniers logs backup:"
if [ -f /var/log/cloudwaste-backup.log ]; then
    tail -20 /var/log/cloudwaste-backup.log
else
    echo -e "${YELLOW}⚠️  Pas de logs backup${NC}"
fi

# 7. Logs récents
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "7️⃣  LOGS RÉCENTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🔴 Erreurs Nginx récentes:"
sudo tail -20 /var/log/nginx/error.log

echo ""
echo "🔴 Erreurs Backend récentes:"
cd /opt/cloudwaste
docker compose -f docker-compose.production.yml logs backend --tail=20 2>&1 | grep -i error || echo "Aucune erreur"

# 8. Firewall
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "8️⃣  FIREWALL (UFW)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
sudo ufw status verbose

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                    🏁 DIAGNOSTIC TERMINÉ                           ║"
echo "╚════════════════════════════════════════════════════════════════════╝"

