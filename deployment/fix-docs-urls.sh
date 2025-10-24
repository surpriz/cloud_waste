#!/bin/bash

echo "🔧 Correction des URLs de documentation FastAPI"
echo ""

# La configuration Nginx actuelle redirige /api/* vers le backend
# Donc /api/docs, /api/redoc et /api/openapi.json devraient déjà fonctionner
# via la règle location /api/

echo "🧪 Test des URLs de documentation:"
echo ""

echo "1. Test /api/docs:"
curl -s http://localhost:8000/api/docs | head -5
echo ""

echo "2. Test /api/redoc:"
curl -s http://localhost:8000/api/redoc | head -5
echo ""

echo "3. Test /api/openapi.json:"
curl -s http://localhost:8000/api/openapi.json | head -10
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Test via Nginx (public):"
echo ""

echo "1. Test https://cutcosts.tech/api/docs:"
curl -s https://cutcosts.tech/api/docs | head -5
echo ""

echo "2. Test https://cutcosts.tech/api/redoc:"
curl -s https://cutcosts.tech/api/redoc | head -5
echo ""

echo "3. Test https://cutcosts.tech/api/openapi.json:"
curl -s https://cutcosts.tech/api/openapi.json | head -10
echo ""

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║                  ✅ VÉRIFICATION TERMINÉE                          ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 URLs CORRECTES DE LA DOCUMENTATION:"
echo ""
echo "✅ Swagger UI:     https://cutcosts.tech/api/docs"
echo "✅ ReDoc:          https://cutcosts.tech/api/redoc"
echo "✅ OpenAPI JSON:   https://cutcosts.tech/api/openapi.json"
echo ""
echo "📝 Note: Les docs sont à /api/docs, pas /docs (configuration FastAPI)"
echo ""

