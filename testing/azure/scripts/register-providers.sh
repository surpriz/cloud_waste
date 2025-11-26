#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Register Azure Resource Providers"
echo "=========================================="
echo ""

# Required Resource Providers for Batch 1
PROVIDERS=(
    "Microsoft.Compute"
    "Microsoft.Network"
    "Microsoft.Storage"
)

echo "This script will register the following Resource Providers:"
for provider in "${PROVIDERS[@]}"; do
    echo "  - $provider"
done
echo ""
echo -e "${YELLOW}Note: This requires Owner or Contributor role on the subscription${NC}"
echo ""

# Check if logged in
if ! az account show &> /dev/null; then
    echo -e "${RED}✗ Not logged in to Azure${NC}"
    echo "Please login with: az login"
    exit 1
fi

ACCOUNT_INFO=$(az account show --query '{name:name, user:user.name, id:id}' -o json)
ACCOUNT_NAME=$(echo "$ACCOUNT_INFO" | grep -o '"name":"[^"]*' | cut -d'"' -f4)
SUBSCRIPTION_ID=$(echo "$ACCOUNT_INFO" | grep -o '"id":"[^"]*' | cut -d'"' -f4)

echo "Current subscription: $ACCOUNT_NAME ($SUBSCRIPTION_ID)"
echo ""

# Register each provider
echo "Registering Resource Providers..."
for provider in "${PROVIDERS[@]}"; do
    echo -n "  Registering $provider... "

    # Check if already registered
    STATE=$(az provider show --namespace "$provider" --query "registrationState" -o tsv 2>/dev/null || echo "NotRegistered")

    if [ "$STATE" = "Registered" ]; then
        echo -e "${GREEN}✓ Already registered${NC}"
    else
        # Register the provider
        if az provider register --namespace "$provider" --wait &> /dev/null; then
            echo -e "${GREEN}✓ Registered${NC}"
        else
            echo -e "${RED}✗ Failed${NC}"
            echo -e "${YELLOW}  You may not have sufficient permissions${NC}"
        fi
    fi
done

echo ""
echo -e "${GREEN}=========================================="
echo "Resource Providers registration complete!"
echo "==========================================${NC}"
echo ""
echo "You can now run: ./scripts/create.sh"
echo ""
