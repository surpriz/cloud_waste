#!/bin/bash

# Script to stop local development environment

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         ⏹️  ARRÊT ENVIRONNEMENT DE DÉVELOPPEMENT                   ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Check if any containers are running
if ! docker compose ps --quiet | grep -q .; then
    echo "ℹ️  Aucun conteneur en cours d'exécution"
    exit 0
fi

echo "⏹️  Arrêt des conteneurs..."
docker compose down

echo ""
echo "✅ Environnement de développement arrêté"
echo ""
echo "💡 Pour redémarrer : bash dev-start.sh"
echo ""

