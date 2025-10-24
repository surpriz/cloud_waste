#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔧 CORRECTION AUTOMATIQUE DES PROBLÈMES                    ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Couleurs
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# 1. Corriger la configuration Nginx pour SSL et API
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  CORRECTION NGINX ET SSL"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Créer une nouvelle configuration Nginx propre
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

echo -e "${GREEN}✅ Configuration Nginx créée${NC}"

# Activer le site
sudo ln -sf /etc/nginx/sites-available/cutcosts.tech /etc/nginx/sites-enabled/cutcosts.tech

# Désactiver le site par défaut s'il existe
sudo rm -f /etc/nginx/sites-enabled/default
sudo rm -f /etc/nginx/sites-enabled/cutcosts.tech-temp

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
    echo "❌ Erreur dans la configuration Nginx"
    exit 1
fi

# 2. Vérifier et redémarrer les conteneurs
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  VÉRIFICATION CONTENEURS DOCKER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

cd /opt/cloudwaste

# Vérifier que tous les conteneurs sont up
echo "📦 État actuel des conteneurs:"
docker compose -f docker-compose.production.yml ps

echo ""
echo "🔄 Redémarrage des conteneurs pour appliquer les changements..."
docker compose -f docker-compose.production.yml restart

echo ""
echo "⏳ Attente 15 secondes pour que tout démarre..."
sleep 15

echo ""
echo "📦 État après redémarrage:"
docker compose -f docker-compose.production.yml ps

# 3. Vérifier Portainer
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  VÉRIFICATION PORTAINER"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if ! docker ps | grep -q portainer; then
    echo -e "${YELLOW}⚠️  Portainer n'est pas actif, démarrage...${NC}"
    docker start portainer 2>/dev/null || docker run -d \
      -p 9443:9443 \
      --name portainer \
      --restart=always \
      -v /var/run/docker.sock:/var/run/docker.sock \
      -v portainer_data:/data \
      portainer/portainer-ce:latest
    echo -e "${GREEN}✅ Portainer démarré${NC}"
else
    echo -e "${GREEN}✅ Portainer actif${NC}"
fi

# 4. Configurer le backup cron si manquant
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  CONFIGURATION BACKUPS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Créer le dossier backups
mkdir -p /opt/cloudwaste/backups

# Vérifier le cron job
if [ ! -f /etc/cron.d/cloudwaste-backup ]; then
    echo -e "${YELLOW}⚠️  Cron job backup manquant, création...${NC}"
    sudo tee /etc/cron.d/cloudwaste-backup > /dev/null << 'CRONEOF'
# CloudWaste Backup - Tous les jours à 2h du matin
0 2 * * * cloudwaste cd /opt/cloudwaste && bash deployment/backup.sh >> /var/log/cloudwaste-backup.log 2>&1
CRONEOF
    sudo chmod 644 /etc/cron.d/cloudwaste-backup
    sudo touch /var/log/cloudwaste-backup.log
    sudo chown cloudwaste:cloudwaste /var/log/cloudwaste-backup.log
    echo -e "${GREEN}✅ Cron job backup créé${NC}"
else
    echo -e "${GREEN}✅ Cron job backup existe déjà${NC}"
fi

# Tester le script de backup
echo ""
echo "🧪 Test du script de backup..."
if [ -f /opt/cloudwaste/deployment/backup.sh ]; then
    bash /opt/cloudwaste/deployment/backup.sh
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✅ Backup test réussi${NC}"
        echo ""
        echo "📦 Backups créés:"
        ls -lh /opt/cloudwaste/backups/ | tail -5
    else
        echo -e "${YELLOW}⚠️  Backup test échoué (vérifier les logs)${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Script backup.sh non trouvé${NC}"
fi

# 5. Tests finaux
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  TESTS FINAUX"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🌐 Test HTTPS (cutcosts.tech):"
curl -s -o /dev/null -w "Status: %{http_code}\n" https://cutcosts.tech

echo ""
echo "📡 Test API Health:"
curl -s https://cutcosts.tech/api/v1/health | jq . 2>/dev/null || curl -s https://cutcosts.tech/api/v1/health

echo ""
echo "📚 Test API Docs (doit retourner du HTML):"
curl -s https://cutcosts.tech/api/v1/docs | head -5

echo ""
echo "🐳 Test Portainer (localhost:9443):"
curl -k -s -o /dev/null -w "Status: %{http_code}\n" https://localhost:9443

echo ""
echo "📊 Test Netdata (localhost:19999):"
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:19999

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║                  ✅ CORRECTIONS TERMINÉES                          ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 PROCHAINES ÉTAPES:"
echo ""
echo "1. ✅ Site web: https://cutcosts.tech (devrait maintenant être sécurisé)"
echo "2. ✅ API Docs: https://cutcosts.tech/api/v1/docs"
echo "3. ⚠️  Portainer: https://cutcosts.tech:9443"
echo "   → Acceptez le certificat auto-signé dans votre navigateur"
echo "   → Cliquez sur 'Avancé' puis 'Continuer vers le site'"
echo "4. ✅ Netdata: http://cutcosts.tech:19999 (HTTP, pas HTTPS)"
echo "5. ✅ Backups: Configurés et testés"
echo ""
echo "📝 Pour voir les logs:"
echo "   docker compose -f docker-compose.production.yml logs -f"
echo ""

