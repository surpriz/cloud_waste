#!/bin/bash

# Script to test Azure connection and credentials from Docker containers

set -e

echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║                                                                    ║"
echo "║         🧪 TEST DE CONNEXION AZURE                                 ║"
echo "║                                                                    ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""

cd /opt/cloudwaste 2>/dev/null || cd ..

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1️⃣  VÉRIFICATION DES CREDENTIALS DANS .ENV"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if .env exists
if [ ! -f ".env" ]; then
    echo "❌ Fichier .env introuvable !"
    echo "   Exécutez d'abord : bash deployment/configure-azure-credentials.sh"
    exit 1
fi

# Check Azure credentials in .env
TENANT_ID=$(grep "^AZURE_TENANT_ID=" .env | cut -d '=' -f2)
CLIENT_ID=$(grep "^AZURE_CLIENT_ID=" .env | cut -d '=' -f2)
SUBSCRIPTION_ID=$(grep "^AZURE_SUBSCRIPTION_ID=" .env | cut -d '=' -f2)
CLIENT_SECRET=$(grep "^AZURE_CLIENT_SECRET=" .env | cut -d '=' -f2)

if [ -z "$TENANT_ID" ] || [ -z "$CLIENT_ID" ] || [ -z "$SUBSCRIPTION_ID" ] || [ -z "$CLIENT_SECRET" ]; then
    echo "❌ Credentials Azure manquants ou vides dans .env"
    echo ""
    echo "   Variables requises :"
    echo "   - AZURE_TENANT_ID       : $([ -n "$TENANT_ID" ] && echo "✅" || echo "❌ manquant")"
    echo "   - AZURE_CLIENT_ID       : $([ -n "$CLIENT_ID" ] && echo "✅" || echo "❌ manquant")"
    echo "   - AZURE_SUBSCRIPTION_ID : $([ -n "$SUBSCRIPTION_ID" ] && echo "✅" || echo "❌ manquant")"
    echo "   - AZURE_CLIENT_SECRET   : $([ -n "$CLIENT_SECRET" ] && echo "✅" || echo "❌ manquant")"
    echo ""
    echo "   Exécutez : bash deployment/configure-azure-credentials.sh"
    exit 1
fi

echo "✅ Credentials Azure trouvés dans .env"
echo "   - AZURE_TENANT_ID       : ${TENANT_ID:0:8}...${TENANT_ID: -8}"
echo "   - AZURE_CLIENT_ID       : ${CLIENT_ID:0:8}...${CLIENT_ID: -8}"
echo "   - AZURE_SUBSCRIPTION_ID : ${SUBSCRIPTION_ID:0:8}...${SUBSCRIPTION_ID: -8}"
echo "   - AZURE_CLIENT_SECRET   : ******* (masqué)"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2️⃣  VÉRIFICATION DES CREDENTIALS DANS LE CONTENEUR BACKEND"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Check if backend container is running
if ! docker compose -f docker-compose.production.yml ps backend | grep -q "Up"; then
    echo "❌ Le conteneur backend n'est pas démarré"
    echo "   Démarrez-le avec : docker compose -f docker-compose.production.yml up -d backend"
    exit 1
fi

echo "✅ Conteneur backend démarré"
echo ""

# Check credentials in backend container
echo "🔍 Vérification des variables d'environnement dans le conteneur..."
CONTAINER_TENANT=$(docker compose -f docker-compose.production.yml exec -T backend env | grep "^AZURE_TENANT_ID=" | cut -d '=' -f2 | tr -d '\r')
CONTAINER_CLIENT=$(docker compose -f docker-compose.production.yml exec -T backend env | grep "^AZURE_CLIENT_ID=" | cut -d '=' -f2 | tr -d '\r')
CONTAINER_SUB=$(docker compose -f docker-compose.production.yml exec -T backend env | grep "^AZURE_SUBSCRIPTION_ID=" | cut -d '=' -f2 | tr -d '\r')
CONTAINER_SECRET=$(docker compose -f docker-compose.production.yml exec -T backend env | grep "^AZURE_CLIENT_SECRET=" | cut -d '=' -f2 | tr -d '\r')

if [ -z "$CONTAINER_TENANT" ] || [ -z "$CONTAINER_CLIENT" ] || [ -z "$CONTAINER_SUB" ] || [ -z "$CONTAINER_SECRET" ]; then
    echo "❌ Credentials Azure non chargés dans le conteneur backend"
    echo ""
    echo "   Cela peut arriver si le conteneur a été démarré avant la configuration."
    echo "   Redémarrez les services avec :"
    echo ""
    echo "   docker compose -f docker-compose.production.yml restart backend celery_worker celery_beat"
    echo ""
    exit 1
fi

echo "✅ Credentials Azure chargés dans le conteneur backend"
echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3️⃣  TEST DE CONNECTIVITÉ RÉSEAU VERS AZURE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🌐 Test de résolution DNS pour login.microsoftonline.com..."
if docker compose -f docker-compose.production.yml exec -T backend nslookup login.microsoftonline.com > /dev/null 2>&1; then
    echo "✅ Résolution DNS réussie"
else
    # Try with dig if nslookup is not available
    if docker compose -f docker-compose.production.yml exec -T backend getent hosts login.microsoftonline.com > /dev/null 2>&1; then
        echo "✅ Résolution DNS réussie"
    else
        echo "❌ Impossible de résoudre login.microsoftonline.com"
        echo ""
        echo "   Cela peut indiquer un problème réseau Docker."
        echo "   Vérifiez la configuration réseau dans docker-compose.production.yml"
        exit 1
    fi
fi

echo ""
echo "🌐 Test de connectivité HTTPS vers Azure..."
if docker compose -f docker-compose.production.yml exec -T backend curl -s --connect-timeout 5 https://management.azure.com/ > /dev/null 2>&1; then
    echo "✅ Connexion HTTPS vers Azure réussie"
else
    echo "⚠️  Impossible de se connecter à Azure API"
    echo "   Cela peut être temporaire. Vérifiez :"
    echo "   1. La connexion Internet du VPS"
    echo "   2. Les règles de pare-feu (UFW)"
fi

echo ""

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "4️⃣  TEST D'AUTHENTIFICATION AZURE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

echo "🔐 Test d'authentification avec les credentials fournis..."
echo "   (Ceci utilise les bibliothèques Python Azure SDK)"
echo ""

# Create a simple Python test script
cat > /tmp/test_azure_auth.py << 'EOF'
import sys
import os
from azure.identity import ClientSecretCredential
from azure.mgmt.resource import ResourceManagementClient

try:
    tenant_id = os.environ.get('AZURE_TENANT_ID')
    client_id = os.environ.get('AZURE_CLIENT_ID')
    client_secret = os.environ.get('AZURE_CLIENT_SECRET')
    subscription_id = os.environ.get('AZURE_SUBSCRIPTION_ID')
    
    if not all([tenant_id, client_id, client_secret, subscription_id]):
        print("❌ Credentials Azure manquants")
        sys.exit(1)
    
    # Authenticate
    credential = ClientSecretCredential(
        tenant_id=tenant_id,
        client_id=client_id,
        client_secret=client_secret
    )
    
    # Try to list resource groups (this validates auth)
    resource_client = ResourceManagementClient(credential, subscription_id)
    rgs = list(resource_client.resource_groups.list())
    
    print(f"✅ Authentification réussie !")
    print(f"   Nombre de resource groups trouvés : {len(rgs)}")
    if rgs:
        print(f"   Exemples : {', '.join([rg.name for rg in rgs[:3]])}")
    
    sys.exit(0)
    
except Exception as e:
    print(f"❌ Erreur d'authentification : {str(e)}")
    sys.exit(1)
EOF

# Copy script to container and run it
docker cp /tmp/test_azure_auth.py cloudwaste_backend_prod:/tmp/test_azure_auth.py 2>/dev/null
AUTH_RESULT=$(docker compose -f docker-compose.production.yml exec -T backend python /tmp/test_azure_auth.py 2>&1)
AUTH_EXIT_CODE=$?

echo "$AUTH_RESULT"
echo ""

# Cleanup
rm -f /tmp/test_azure_auth.py
docker compose -f docker-compose.production.yml exec -T backend rm -f /tmp/test_azure_auth.py 2>/dev/null || true

if [ $AUTH_EXIT_CODE -eq 0 ]; then
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║              ✅ TOUS LES TESTS SONT RÉUSSIS !                      ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "🎉 Votre configuration Azure est fonctionnelle !"
    echo ""
    echo "🎯 Vous pouvez maintenant :"
    echo "   1. Lancer un scan Azure depuis https://cutcosts.tech"
    echo "   2. Les ressources orphelines seront détectées"
    echo ""
else
    echo "╔════════════════════════════════════════════════════════════════════╗"
    echo "║                                                                    ║"
    echo "║              ❌ ÉCHEC DU TEST D'AUTHENTIFICATION                   ║"
    echo "║                                                                    ║"
    echo "╚════════════════════════════════════════════════════════════════════╝"
    echo ""
    echo "🔧 SOLUTIONS POSSIBLES :"
    echo ""
    echo "   1. Vérifiez que les credentials sont corrects dans le portail Azure"
    echo "   2. Vérifiez que le Service Principal a les permissions nécessaires :"
    echo "      - Role : Reader (sur la subscription)"
    echo "   3. Reconfigurez les credentials :"
    echo "      bash deployment/configure-azure-credentials.sh"
    echo ""
    exit 1
fi

