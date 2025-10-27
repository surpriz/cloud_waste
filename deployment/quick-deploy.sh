#!/bin/bash

# Quick deployment script for production
# Usage: bash deployment/quick-deploy.sh [--skip-build] [--services service1,service2]

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🚀 DÉPLOIEMENT RAPIDE EN PRODUCTION                        ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Parse arguments
SKIP_BUILD=false
SPECIFIC_SERVICES=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-build)
            SKIP_BUILD=true
            shift
            ;;
        --services)
            SPECIFIC_SERVICES="$2"
            shift 2
            ;;
        *)
            echo "❌ Option inconnue: $1"
            echo "Usage: $0 [--skip-build] [--services service1,service2]"
            exit 1
            ;;
    esac
done

# Ensure we're in the right directory
if [ ! -f "docker-compose.production.yml" ]; then
    echo "❌ Fichier docker-compose.production.yml introuvable"
    echo "   Exécutez ce script depuis /opt/cloudwaste"
    exit 1
fi

# Default to all services if none specified
if [ -z "$SPECIFIC_SERVICES" ]; then
    SERVICES_TO_DEPLOY="backend frontend celery_worker celery_beat"
else
    SERVICES_TO_DEPLOY=$(echo "$SPECIFIC_SERVICES" | tr ',' ' ')
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  RÉCUPÉRATION DES DERNIÈRES MODIFICATIONS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Save current commit
CURRENT_COMMIT=$(git rev-parse HEAD)
echo "📌 Commit actuel : ${CURRENT_COMMIT:0:8}"

# Pull latest changes
echo "⏳ Récupération des modifications depuis GitHub..."
git fetch origin master

# Check if there are new commits
LATEST_COMMIT=$(git rev-parse origin/master)
if [ "$CURRENT_COMMIT" == "$LATEST_COMMIT" ]; then
    echo "✅ Aucune nouvelle modification (déjà à jour)"
else
    echo "🔄 Nouvelles modifications détectées"
    git pull origin master
    echo "✅ Code mis à jour : ${CURRENT_COMMIT:0:8} → ${LATEST_COMMIT:0:8}"
fi

echo ""

if [ "$SKIP_BUILD" = true ]; then
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "2️⃣  REBUILD (IGNORÉ)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⏩ Rebuild ignoré (--skip-build)"
    echo ""
else
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "2️⃣  REBUILD DES IMAGES DOCKER"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "⏳ Construction des images pour : $SERVICES_TO_DEPLOY"
    echo "   (Cela peut prendre quelques minutes...)"
    echo ""
    
    for service in $SERVICES_TO_DEPLOY; do
        if docker compose -f docker-compose.production.yml config --services | grep -q "^${service}$"; then
            echo "🔨 Build de $service..."
            docker compose -f docker-compose.production.yml build --no-cache "$service"
        fi
    done
    
    echo ""
    echo "✅ Images Docker construites"
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  REDÉMARRAGE DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Restart services
for service in $SERVICES_TO_DEPLOY; do
    echo "🔄 Redémarrage de $service..."
    docker compose -f docker-compose.production.yml up -d "$service"
done

echo ""
echo "✅ Services redémarrés"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  VÉRIFICATION DE LA SANTÉ DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⏳ Attente de 15 secondes pour le démarrage..."
sleep 15

echo ""
echo "📊 Status des conteneurs :"
docker compose -f docker-compose.production.yml ps

echo ""

# Check health of each service
ALL_HEALTHY=true

for service in $SERVICES_TO_DEPLOY; do
    STATUS=$(docker compose -f docker-compose.production.yml ps "$service" --format json | jq -r '.[0].Health' 2>/dev/null || echo "unknown")
    
    if [ "$STATUS" == "healthy" ]; then
        echo "✅ $service : healthy"
    elif [ "$STATUS" == "starting" ]; then
        echo "⏳ $service : démarrage en cours"
    elif [ "$STATUS" == "unknown" ] || [ "$STATUS" == "null" ]; then
        # Check if container is running (some services don't have healthcheck)
        if docker compose -f docker-compose.production.yml ps "$service" | grep -q "Up"; then
            echo "✅ $service : running (pas de healthcheck)"
        else
            echo "❌ $service : problème détecté"
            ALL_HEALTHY=false
        fi
    else
        echo "❌ $service : unhealthy"
        ALL_HEALTHY=false
    fi
done

echo ""

if [ "$ALL_HEALTHY" = false ]; then
    echo "⚠️  ATTENTION : Certains services ont des problèmes"
    echo ""
    echo "📋 Vérifiez les logs avec :"
    for service in $SERVICES_TO_DEPLOY; do
        echo "   docker compose -f docker-compose.production.yml logs $service --tail=50"
    done
    echo ""
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  TESTS DE CONNECTIVITÉ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test backend
if echo "$SERVICES_TO_DEPLOY" | grep -q "backend"; then
    echo "🧪 Test du backend (API health check)..."
    if curl -s -f http://localhost:8000/api/v1/health > /dev/null 2>&1; then
        echo "✅ Backend : OK"
    else
        echo "❌ Backend : Échec du health check"
        ALL_HEALTHY=false
    fi
fi

# Test frontend
if echo "$SERVICES_TO_DEPLOY" | grep -q "frontend"; then
    echo "🧪 Test du frontend..."
    FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
    if [ "$FRONTEND_STATUS" == "200" ] || [ "$FRONTEND_STATUS" == "304" ]; then
        echo "✅ Frontend : OK (HTTP $FRONTEND_STATUS)"
    else
        echo "❌ Frontend : Échec (HTTP $FRONTEND_STATUS)"
        ALL_HEALTHY=false
    fi
fi

echo ""

# Test public URLs via Nginx
echo "🌐 Test des URLs publiques via Nginx..."
PUBLIC_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech 2>/dev/null || echo "000")
if [ "$PUBLIC_STATUS" == "200" ] || [ "$PUBLIC_STATUS" == "304" ]; then
    echo "✅ https://cutcosts.tech : OK (HTTP $PUBLIC_STATUS)"
else
    echo "⚠️  https://cutcosts.tech : HTTP $PUBLIC_STATUS"
fi

API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" https://cutcosts.tech/api/v1/health 2>/dev/null || echo "000")
if [ "$API_STATUS" == "200" ]; then
    echo "✅ https://cutcosts.tech/api/v1/health : OK"
else
    echo "⚠️  https://cutcosts.tech/api/v1/health : HTTP $API_STATUS"
fi

echo ""

if [ "$ALL_HEALTHY" = true ]; then
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║              ✅ DÉPLOIEMENT RÉUSSI !                               ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "🎉 Votre application est en ligne !"
    echo ""
    echo "🌐 URLs :"
    echo "   • Site web : https://cutcosts.tech"
    echo "   • API Docs : https://cutcosts.tech/api/docs"
    echo "   • Portainer: https://cutcosts.tech:9443"
    echo "   • Netdata  : https://cutcosts.tech/netdata/"
    echo ""
else
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║              ⚠️  DÉPLOIEMENT AVEC AVERTISSEMENTS                   ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "⚠️  Le déploiement est terminé mais certains services ont des problèmes"
    echo ""
    echo "📋 Consultez les logs :"
    for service in $SERVICES_TO_DEPLOY; do
        echo "   docker compose -f docker-compose.production.yml logs $service --tail=50"
    done
    echo ""
    exit 1
fi

