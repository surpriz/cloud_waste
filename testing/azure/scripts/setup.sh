#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "CutCosts Azure Testing Infrastructure Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and fill in your credentials:"
    echo "  cp $PROJECT_DIR/.env.example $PROJECT_DIR/.env"
    echo "  vim $PROJECT_DIR/.env"
    exit 1
fi

# Source .env
source "$PROJECT_DIR/.env"

# Check Azure CLI
echo -n "Checking Azure CLI... "
if ! command -v az &> /dev/null; then
    echo -e "${RED}✗ Not installed${NC}"
    echo "Please install Azure CLI: https://docs.microsoft.com/cli/azure/install-azure-cli"
    exit 1
fi
AZURE_CLI_VERSION=$(az version --query '"azure-cli"' -o tsv 2>/dev/null || echo "unknown")
echo -e "${GREEN}✓ Installed (v${AZURE_CLI_VERSION})${NC}"

# Check Terraform
echo -n "Checking Terraform... "
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}✗ Not installed${NC}"
    echo "Please install Terraform: https://www.terraform.io/downloads"
    exit 1
fi
TERRAFORM_VERSION=$(terraform version -json | grep '"terraform_version"' | cut -d'"' -f4)
echo -e "${GREEN}✓ Installed (v${TERRAFORM_VERSION})${NC}"

# Check Terraform version
REQUIRED_VERSION="1.5.0"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$TERRAFORM_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}✗ Terraform version must be >= ${REQUIRED_VERSION}${NC}"
    exit 1
fi

# Check Azure login (user account)
echo -n "Checking Azure login... "
if ! az account show &> /dev/null; then
    echo -e "${RED}✗ Not logged in${NC}"
    echo "Please login with: az login --tenant ${ARM_TENANT_ID:-your-tenant-id}"
    exit 1
fi

# Verify subscription
CURRENT_SUB=$(az account show --query id -o tsv 2>/dev/null)
CURRENT_TENANT=$(az account show --query tenantId -o tsv 2>/dev/null)

if [ -n "$ARM_SUBSCRIPTION_ID" ] && [ "$CURRENT_SUB" != "$ARM_SUBSCRIPTION_ID" ]; then
    echo -e "${YELLOW}⚠ Wrong subscription${NC}"
    echo "Setting subscription to $ARM_SUBSCRIPTION_ID..."
    az account set --subscription "$ARM_SUBSCRIPTION_ID" &> /dev/null
fi

if [ -n "$ARM_TENANT_ID" ] && [ "$CURRENT_TENANT" != "$ARM_TENANT_ID" ]; then
    echo -e "${YELLOW}⚠ Wrong tenant${NC}"
    echo "Please login to the correct tenant:"
    echo "  az logout && az login --tenant $ARM_TENANT_ID"
    exit 1
fi

AZURE_ACCOUNT=$(az account show --query '{subscription_name:name, user_name:user.name}' -o json 2>/dev/null)
SUBSCRIPTION_NAME=$(echo "$AZURE_ACCOUNT" | grep -o '"subscription_name":"[^"]*' | cut -d'"' -f4)
USER_NAME=$(echo "$AZURE_ACCOUNT" | grep -o '"user_name":"[^"]*' | cut -d'"' -f4)

echo -e "${GREEN}✓ Authenticated${NC}"
echo "  User: $USER_NAME"
echo "  Subscription: $SUBSCRIPTION_NAME"
echo "  Subscription ID: $ARM_SUBSCRIPTION_ID"
echo "  Tenant ID: $ARM_TENANT_ID"

# Check region
echo -n "Checking region $AZURE_REGION... "
if ! az account list-locations --query "[?name=='$AZURE_REGION']" -o tsv &> /dev/null; then
    echo -e "${RED}✗ Invalid region${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Valid${NC}"

# Check owner email
if [ -z "$TF_VAR_owner_email" ]; then
    echo -e "${YELLOW}⚠ Warning: TF_VAR_owner_email not set in .env${NC}"
    echo "  This is required for resource tagging"
fi

# Check SSH key for VM
echo -n "Checking SSH key (~/.ssh/id_rsa.pub)... "
if [ ! -f "$HOME/.ssh/id_rsa.pub" ]; then
    echo -e "${RED}✗ Not found${NC}"
    echo "Please generate SSH key:"
    echo "  ssh-keygen -t rsa -b 4096 -f ~/.ssh/id_rsa -N ''"
    exit 1
fi
echo -e "${GREEN}✓ Found${NC}"

# Display batch configuration
echo ""
echo "Batch Configuration:"
echo "  Batch 1 (Core): ${TF_VAR_enable_batch_1:-false} (~€68/month)"
echo "  Batch 2 (Advanced): ${TF_VAR_enable_batch_2:-false} (~€71/month)"
echo "  Batch 3 (Premium): ${TF_VAR_enable_batch_3:-false} (TBD)"

# Calculate total cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 68))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 71))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 0))

echo ""
if [ $TOTAL_COST -eq 0 ]; then
    echo -e "${YELLOW}⚠ No batches enabled. Set TF_VAR_enable_batch_1=true in .env to enable Batch 1${NC}"
else
    echo -e "${GREEN}Estimated monthly cost: ~€${TOTAL_COST}${NC}"
fi

# Initialize Terraform
echo ""
echo "Initializing Terraform..."
cd "$PROJECT_DIR/terraform"
if terraform init; then
    echo -e "${GREEN}✓ Terraform initialized successfully${NC}"
else
    echo -e "${RED}✗ Terraform initialization failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}=========================================="
echo "Setup complete!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Register Resource Providers: ./scripts/register-providers.sh"
echo "  2. Create resources: ./scripts/create.sh"
echo "  3. Wait 3+ days for CutCosts detection"
echo "  4. Clean up: ./scripts/destroy.sh"
echo ""
echo -e "${YELLOW}Note: Resource Provider registration requires Owner or Contributor role${NC}"
echo ""
