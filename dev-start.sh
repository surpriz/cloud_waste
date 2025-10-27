#!/bin/bash

# Script to start local development environment

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🚀 DÉMARRAGE ENVIRONNEMENT DE DÉVELOPPEMENT                ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "⚠️  Fichier .env introuvable"
    echo ""
    if [ -f ".env.example" ]; then
        echo "📝 Copie de .env.example vers .env..."
        cp .env.example .env
        echo "✅ Fichier .env créé"
        echo ""
        echo "⚠️  IMPORTANT : Configurez vos credentials Azure/AWS dans .env"
        echo "   Éditez le fichier .env et ajoutez :"
        echo "   - AZURE_TENANT_ID"
        echo "   - AZURE_CLIENT_ID"
        echo "   - AZURE_SUBSCRIPTION_ID"
        echo "   - AZURE_CLIENT_SECRET"
        echo ""
    else
        echo "❌ Aucun fichier .env ou .env.example trouvé"
        echo "   Créez un fichier .env avec les variables nécessaires"
        exit 1
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  VÉRIFICATION DE L'ENVIRONNEMENT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker n'est pas installé"
    echo "   Installez Docker Desktop : https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker installé"

# Check Docker Compose
if ! command -v docker compose &> /dev/null; then
    echo "❌ Docker Compose n'est pas installé"
    exit 1
fi

echo "✅ Docker Compose installé"

# Check if Docker is running
if ! docker info &> /dev/null; then
    echo "❌ Docker n'est pas démarré"
    echo "   Démarrez Docker Desktop"
    exit 1
fi

echo "✅ Docker est démarré"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  ARRÊT DES CONTENEURS EXISTANTS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Stop any running containers
if docker compose ps --quiet | grep -q .; then
    echo "⏹️  Arrêt des conteneurs existants..."
    docker compose down
    echo "✅ Conteneurs arrêtés"
else
    echo "ℹ️  Aucun conteneur en cours d'exécution"
fi

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  DÉMARRAGE DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⏳ Démarrage de l'environnement de développement..."
echo "   (La première fois peut prendre plusieurs minutes pour builder les images)"
echo ""

# Start services
docker compose up -d

echo ""
echo "✅ Services démarrés"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  ATTENTE DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "⏳ Attente que tous les services soient prêts (30 secondes)..."
sleep 30

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "5️⃣  STATUT DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

docker compose ps

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "6️⃣  TESTS DE CONNECTIVITÉ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Test backend
echo "🧪 Test du backend..."
BACKEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/v1/health 2>/dev/null || echo "000")
if [ "$BACKEND_STATUS" == "200" ]; then
    echo "✅ Backend : OK (http://localhost:8000)"
else
    echo "⚠️  Backend : En attente... (HTTP $BACKEND_STATUS)"
fi

# Test frontend
echo "🧪 Test du frontend..."
FRONTEND_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 2>/dev/null || echo "000")
if [ "$FRONTEND_STATUS" == "200" ] || [ "$FRONTEND_STATUS" == "304" ]; then
    echo "✅ Frontend : OK (http://localhost:3000)"
else
    echo "⚠️  Frontend : En attente... (HTTP $FRONTEND_STATUS)"
fi

echo ""

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║              ✅ ENVIRONNEMENT PRÊT !                               ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎉 Votre environnement de développement est démarré !"
echo ""
echo "🌐 URLs locales :"
echo "   • Frontend   : http://localhost:3000"
echo "   • Backend    : http://localhost:8000"
echo "   • API Docs   : http://localhost:8000/docs"
echo "   • PostgreSQL : localhost:5433 (user: cloudwaste, db: cloudwaste)"
echo "   • Redis      : localhost:6379"
echo ""
echo "📝 Commandes utiles :"
echo "   • Voir les logs       : bash dev-logs.sh [service]"
echo "   • Arrêter l'env       : bash dev-stop.sh"
echo "   • Redémarrer un service : docker compose restart [service]"
echo ""
echo "💡 Le hot-reload est activé :"
echo "   - Modifiez le code backend → redémarrage automatique"
echo "   - Modifiez le code frontend → rechargement automatique dans le navigateur"
echo ""
echo "🔧 Configuration Azure/AWS :"
echo "   Éditez le fichier .env pour ajouter vos credentials cloud"
echo ""

