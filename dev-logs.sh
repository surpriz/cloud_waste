#!/bin/bash

# Script to view logs from local development environment

SERVICE=$1
TAIL_LINES=${2:-50}

if [ -z "$SERVICE" ]; then
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║         📋 LOGS ENVIRONNEMENT DE DÉVELOPPEMENT                     ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "Usage: bash dev-logs.sh [service] [nombre_de_lignes]"
    echo ""
    echo "Services disponibles:"
    docker compose ps --services
    echo ""
    echo "Exemples:"
    echo "  bash dev-logs.sh backend        # Voir les 50 dernières lignes du backend"
    echo "  bash dev-logs.sh frontend 100   # Voir les 100 dernières lignes du frontend"
    echo "  bash dev-logs.sh                # Voir tous les logs (follow mode)"
    echo ""
    echo "📋 Affichage de tous les logs (Ctrl+C pour quitter)..."
    echo ""
    docker compose logs -f
else
    # Check if service exists
    if ! docker compose ps --services | grep -q "^${SERVICE}$"; then
        echo "❌ Service '$SERVICE' introuvable"
        echo ""
        echo "Services disponibles:"
        docker compose ps --services
        exit 1
    fi
    
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║         📋 LOGS: $SERVICE"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    
    docker compose logs "$SERVICE" --tail="$TAIL_LINES" -f
fi

