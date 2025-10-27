#!/bin/bash

# Script to configure Azure credentials in production .env file
# This script is interactive and secure (no credentials displayed in terminal)

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🔧 CONFIGURATION DES CREDENTIALS AZURE                     ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

# Determine the correct path to .env
if [ -f "/opt/cloudwaste/.env" ]; then
    ENV_FILE="/opt/cloudwaste/.env"
elif [ -f "../.env" ]; then
    ENV_FILE="../.env"
elif [ -f ".env" ]; then
    ENV_FILE=".env"
else
    echo "❌ Fichier .env introuvable !"
    echo "   Veuillez exécuter ce script depuis /opt/cloudwaste ou /opt/cloudwaste/deployment"
    exit 1
fi

echo "📁 Fichier .env détecté : $ENV_FILE"
echo ""

# Check if Azure credentials already exist
if grep -q "^AZURE_TENANT_ID=.\+" "$ENV_FILE" 2>/dev/null; then
    echo "⚠️  Des credentials Azure existent déjà dans le fichier .env"
    echo ""
    read -p "Voulez-vous les remplacer ? (oui/non) : " replace
    if [ "$replace" != "oui" ] && [ "$replace" != "yes" ]; then
        echo "❌ Configuration annulée."
        exit 0
    fi
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📝 SAISIE DES CREDENTIALS AZURE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "ℹ️  Vous pouvez trouver ces informations dans le portail Azure :"
echo "   https://portal.azure.com → Azure Active Directory → App registrations"
echo ""

# Prompt for Azure credentials
read -p "AZURE_TENANT_ID (UUID format) : " AZURE_TENANT_ID
read -p "AZURE_CLIENT_ID (UUID format) : " AZURE_CLIENT_ID
read -p "AZURE_SUBSCRIPTION_ID (UUID format) : " AZURE_SUBSCRIPTION_ID
read -s -p "AZURE_CLIENT_SECRET (masqué) : " AZURE_CLIENT_SECRET
echo ""
echo ""

# Validate format (basic UUID check)
UUID_REGEX='^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'

if ! [[ $AZURE_TENANT_ID =~ $UUID_REGEX ]]; then
    echo "❌ AZURE_TENANT_ID ne semble pas être un UUID valide"
    echo "   Format attendu : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    exit 1
fi

if ! [[ $AZURE_CLIENT_ID =~ $UUID_REGEX ]]; then
    echo "❌ AZURE_CLIENT_ID ne semble pas être un UUID valide"
    echo "   Format attendu : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    exit 1
fi

if ! [[ $AZURE_SUBSCRIPTION_ID =~ $UUID_REGEX ]]; then
    echo "❌ AZURE_SUBSCRIPTION_ID ne semble pas être un UUID valide"
    echo "   Format attendu : xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
    exit 1
fi

if [ -z "$AZURE_CLIENT_SECRET" ]; then
    echo "❌ AZURE_CLIENT_SECRET ne peut pas être vide"
    exit 1
fi

echo "✅ Format des credentials validé"
echo ""

# Backup existing .env
echo "💾 Création d'une sauvegarde de .env..."
cp "$ENV_FILE" "${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo "   Sauvegarde créée : ${ENV_FILE}.backup.$(date +%Y%m%d_%H%M%S)"
echo ""

# Update or add Azure credentials
echo "📝 Mise à jour du fichier .env..."

# Function to update or add env variable
update_or_add_env() {
    local key=$1
    local value=$2
    local file=$3
    
    if grep -q "^${key}=" "$file"; then
        # Key exists, update it
        sed -i.tmp "s|^${key}=.*|${key}=${value}|" "$file"
        rm -f "${file}.tmp"
    else
        # Key doesn't exist, add it
        echo "${key}=${value}" >> "$file"
    fi
}

update_or_add_env "AZURE_TENANT_ID" "$AZURE_TENANT_ID" "$ENV_FILE"
update_or_add_env "AZURE_CLIENT_ID" "$AZURE_CLIENT_ID" "$ENV_FILE"
update_or_add_env "AZURE_SUBSCRIPTION_ID" "$AZURE_SUBSCRIPTION_ID" "$ENV_FILE"
update_or_add_env "AZURE_CLIENT_SECRET" "$AZURE_CLIENT_SECRET" "$ENV_FILE"

echo "✅ Credentials Azure ajoutés au fichier .env"
echo ""

# Verify credentials were written
if grep -q "^AZURE_TENANT_ID=.\+" "$ENV_FILE" && \
   grep -q "^AZURE_CLIENT_ID=.\+" "$ENV_FILE" && \
   grep -q "^AZURE_SUBSCRIPTION_ID=.\+" "$ENV_FILE" && \
   grep -q "^AZURE_CLIENT_SECRET=.\+" "$ENV_FILE"; then
    echo "✅ Vérification : Tous les credentials sont présents dans .env"
else
    echo "❌ Erreur : Certains credentials n'ont pas été écrits correctement"
    exit 1
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔄 REDÉMARRAGE DES SERVICES"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "⏳ Redémarrage du backend et des workers Celery pour appliquer les nouveaux credentials..."

cd /opt/cloudwaste || cd ..

# Restart backend and celery services
docker compose -f docker-compose.production.yml restart backend celery_worker celery_beat

echo ""
echo "⏳ Attente de 10 secondes pour que les services redémarrent..."
sleep 10

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║              ✅ CONFIGURATION TERMINÉE                             ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
echo "🎯 PROCHAINES ÉTAPES :"
echo ""
echo "   1. Tester la connexion Azure :"
echo "      bash deployment/test-azure-connection.sh"
echo ""
echo "   2. Lancer un scan Azure depuis l'interface web :"
echo "      https://cutcosts.tech"
echo ""
echo "   3. Vérifier les logs des workers en cas de problème :"
echo "      docker compose -f docker-compose.production.yml logs celery_worker --tail=50"
echo ""

