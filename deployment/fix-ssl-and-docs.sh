#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔧 CORRECTION SSL et API Docs                              ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  VÉRIFICATION CERTIFICAT SSL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "📜 Certificats installés:"
sudo certbot certificates

echo ""
echo "🧪 Test SSL pour cutcosts.tech (sans www):"
curl -I https://cutcosts.tech 2>&1 | head -10

echo ""
echo "🧪 Test SSL pour www.cutcosts.tech:"
curl -I https://www.cutcosts.tech 2>&1 | head -10

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  DIAGNOSTIC API DOCS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🔍 Vérification des routes FastAPI disponibles:"
echo ""
echo "Test /docs (FastAPI par défaut):"
curl -s http://localhost:8000/docs | head -5
echo ""

echo "Test /api/v1/docs:"
curl -s http://localhost:8000/api/v1/docs
echo ""

echo "Test /redoc:"
curl -s http://localhost:8000/redoc | head -5
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  CORRECTION AUTOMATIQUE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Vérifier si le certificat couvre cutcosts.tech (sans www)
CERT_DOMAINS=$(sudo certbot certificates 2>/dev/null | grep "Domains:" | head -1)

if echo "$CERT_DOMAINS" | grep -q "cutcosts.tech"; then
    echo -e "${GREEN}✅ Certificat SSL couvre cutcosts.tech${NC}"
else
    echo -e "${RED}❌ Certificat SSL ne couvre pas cutcosts.tech${NC}"
    echo ""
    echo -e "${YELLOW}⚠️  Renouvellement du certificat nécessaire${NC}"
    echo "Exécuter: sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech --expand"
fi

# Corriger la configuration Nginx pour les docs
echo ""
echo "🔧 Ajout de routes pour les API Docs..."

# Créer une nouvelle configuration Nginx avec les routes docs
sudo tee /etc/nginx/sites-available/cutcosts.tech > /dev/null << 'NGINXEOF'
# Redirection HTTP vers HTTPS
server {
    listen 80;
    listen [::]:80;
    server_name cutcosts.tech www.cutcosts.tech;
    
    # Redirection permanente vers HTTPS
    return 301 https://$server_name$request_uri;
}

# Configuration HTTPS principale
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name cutcosts.tech www.cutcosts.tech;

    # Certificats SSL (gérés par Certbot)
    ssl_certificate /etc/letsencrypt/live/cutcosts.tech/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/cutcosts.tech/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Logs
    access_log /var/log/nginx/cutcosts.tech.access.log;
    error_log /var/log/nginx/cutcosts.tech.error.log;

    # Taille maximale des requêtes
    client_max_body_size 50M;

    # API Backend (FastAPI)
    location /api/ {
        proxy_pass http://localhost:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # API Documentation (Swagger UI)
    location /docs {
        proxy_pass http://localhost:8000/docs;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # API Documentation (ReDoc)
    location /redoc {
        proxy_pass http://localhost:8000/redoc;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # OpenAPI JSON
    location /openapi.json {
        proxy_pass http://localhost:8000/openapi.json;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Netdata Monitoring (via proxy HTTPS)
    location /netdata/ {
        proxy_pass http://localhost:19999/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        
        # Headers spécifiques pour Netdata
        proxy_set_header X-Forwarded-Host $host;
        proxy_set_header X-Forwarded-Server $host;
    }

    # Frontend (Next.js)
    location / {
        proxy_pass http://localhost:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}
NGINXEOF

echo -e "${GREEN}✅ Configuration Nginx mise à jour${NC}"

# Tester la configuration
echo ""
echo "🧪 Test de la configuration Nginx:"
sudo nginx -t

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✅ Configuration Nginx valide${NC}"
    echo ""
    echo "🔄 Rechargement Nginx..."
    sudo systemctl reload nginx
    echo -e "${GREEN}✅ Nginx rechargé${NC}"
else
    echo -e "${RED}❌ Erreur dans la configuration Nginx${NC}"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  TESTS FINAUX"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🌐 Test cutcosts.tech (sans www):"
curl -s -o /dev/null -w "Status: %{http_code}\n" https://cutcosts.tech

echo ""
echo "🌐 Test www.cutcosts.tech:"
curl -s -o /dev/null -w "Status: %{http_code}\n" https://www.cutcosts.tech

echo ""
echo "📚 Test API Docs (/docs):"
curl -s https://cutcosts.tech/docs | head -5

echo ""
echo "📚 Test API Docs (/redoc):"
curl -s https://cutcosts.tech/redoc | head -5

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║                  ✅ CORRECTIONS TERMINÉES                          ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 URLS MISES À JOUR:"
echo ""
echo "✅ Site web:        https://cutcosts.tech (devrait être sécurisé maintenant)"
echo "✅ API Swagger:     https://cutcosts.tech/docs"
echo "✅ API ReDoc:       https://cutcosts.tech/redoc"
echo "✅ API OpenAPI:     https://cutcosts.tech/openapi.json"
echo "✅ Netdata:         https://cutcosts.tech/netdata/"
echo "✅ Portainer:       https://cutcosts.tech:9443"
echo ""
echo "📝 Si cutcosts.tech (sans www) affiche toujours 'Non sécurisé':"
echo "   Exécutez: sudo certbot --nginx -d cutcosts.tech -d www.cutcosts.tech --expand"
echo ""

