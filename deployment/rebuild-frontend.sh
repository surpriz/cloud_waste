#!/bin/bash

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔧 REBUILD FRONTEND PRODUCTION                             ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  ARRÊT DU FRONTEND"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f docker-compose.production.yml stop frontend
docker compose -f docker-compose.production.yml rm -f frontend

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  SUPPRESSION DE L'IMAGE ET DU CACHE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
# Supprimer l'image frontend
docker rmi cloudwaste-frontend 2>/dev/null || true

# Nettoyer le cache de build Docker
docker builder prune -f

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  REBUILD DU FRONTEND (avec toutes les dépendances)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "⏳ Cela peut prendre 2-3 minutes..."
docker compose -f docker-compose.production.yml build --no-cache frontend

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  DÉMARRAGE DU FRONTEND"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker compose -f docker-compose.production.yml up -d frontend

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  VÉRIFICATION"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⏳ Attente du démarrage (30 secondes)..."
sleep 30

echo ""
echo "📊 Status des conteneurs:"
docker compose -f docker-compose.production.yml ps frontend

echo ""
echo "📋 Derniers logs du frontend:"
docker compose -f docker-compose.production.yml logs frontend --tail=20

echo ""
echo "🧪 Test HTTP local (depuis le VPS):"
curl -s -o /dev/null -w "Status: %{http_code}\n" http://localhost:3000

echo ""
echo "🌐 Test HTTPS public (via Nginx):"
curl -s -o /dev/null -w "Status: %{http_code}\n" https://cutcosts.tech

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║                  ✅ REBUILD TERMINÉ                                ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 URLS À TESTER:"
echo "   • Site web:     https://cutcosts.tech"
echo "   • API Docs:     https://cutcosts.tech/api/docs"
echo "   • Portainer:    https://cutcosts.tech:9443"
echo "   • Netdata:      https://cutcosts.tech/netdata/"
echo ""
echo "📝 Si le site affiche toujours une erreur 500:"
echo "   docker compose -f docker-compose.production.yml logs frontend --tail=50"
echo ""

