#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "=========================================="
echo "CutCosts Azure Resource Creation"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Run ./scripts/setup.sh first"
    exit 1
fi

# Source .env but DON'T export ARM_CLIENT_ID and ARM_CLIENT_SECRET
# This forces Terraform to use az login instead of Service Principal
source "$PROJECT_DIR/.env"

# Export only the variables needed (NOT the Service Principal credentials)
export TF_VAR_azure_subscription_id="$ARM_SUBSCRIPTION_ID"
export TF_VAR_azure_tenant_id="$ARM_TENANT_ID"
export TF_VAR_azure_region="${AZURE_REGION:-westeurope}"
export TF_VAR_environment="${TF_VAR_environment:-test}"
export TF_VAR_project_name="${TF_VAR_project_name:-cutcosts-testing}"
export TF_VAR_owner_email="${TF_VAR_owner_email}"

# Unset Service Principal credentials to force az login usage
unset ARM_CLIENT_ID
unset ARM_CLIENT_SECRET

# Parse command line arguments
BATCH_ARG=""
AUTO_APPROVE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            export TF_VAR_enable_batch_1=true
            export TF_VAR_enable_batch_2=true
            export TF_VAR_enable_batch_3=true
            shift
            ;;
        --batch)
            shift
            BATCH_ARG="$1"
            shift
            ;;
        --force)
            AUTO_APPROVE="-auto-approve"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--all] [--batch 1 2 3] [--force]"
            exit 1
            ;;
    esac
done

# Handle --batch argument
if [ -n "$BATCH_ARG" ]; then
    export TF_VAR_enable_batch_1=false
    export TF_VAR_enable_batch_2=false
    export TF_VAR_enable_batch_3=false

    for batch in $BATCH_ARG; do
        case $batch in
            1) export TF_VAR_enable_batch_1=true ;;
            2) export TF_VAR_enable_batch_2=true ;;
            3) export TF_VAR_enable_batch_3=true ;;
            *) echo -e "${YELLOW}⚠ Warning: Invalid batch number $batch${NC}" ;;
        esac
    done
fi

# Calculate estimated cost
TOTAL_COST=0
echo "Batches to create:"
[ "${TF_VAR_enable_batch_1}" = "true" ] && echo "  ✓ Batch 1 (Core) - ~€68/month" && TOTAL_COST=$((TOTAL_COST + 68))
[ "${TF_VAR_enable_batch_2}" = "true" ] && echo "  ✓ Batch 2 (Advanced) - ~€71/month" && TOTAL_COST=$((TOTAL_COST + 71))
[ "${TF_VAR_enable_batch_3}" = "true" ] && echo "  ✓ Batch 3 (Premium) - TBD" && TOTAL_COST=$((TOTAL_COST + 0))

if [ $TOTAL_COST -eq 0 ]; then
    echo -e "${RED}✗ No batches enabled${NC}"
    echo "Enable at least one batch in .env or use --batch flag"
    exit 1
fi

echo ""
echo -e "${YELLOW}Estimated monthly cost: ~€${TOTAL_COST}${NC}"
echo ""

# Warning for expensive batches
if [ $TOTAL_COST -gt 50 ]; then
    echo -e "${RED}⚠ WARNING: Cost detected!${NC}"
    echo "This configuration will cost approximately €${TOTAL_COST}/month"
    echo ""
fi

# Check Azure login (using user account, not Service Principal)
echo "Checking Azure login..."
if ! az account show &> /dev/null; then
    echo -e "${RED}✗ Not logged in to Azure${NC}"
    echo "Please login with: az login --tenant $ARM_TENANT_ID"
    exit 1
fi

# Verify correct subscription
CURRENT_SUB=$(az account show --query id -o tsv 2>/dev/null)
if [ "$CURRENT_SUB" != "$ARM_SUBSCRIPTION_ID" ]; then
    echo "Setting subscription to $ARM_SUBSCRIPTION_ID..."
    az account set --subscription "$ARM_SUBSCRIPTION_ID"
fi

ACCOUNT_INFO=$(az account show --query '{name:name, user:user.name}' -o json)
ACCOUNT_NAME=$(echo "$ACCOUNT_INFO" | grep -o '"name":"[^"]*' | cut -d'"' -f4)
USER_NAME=$(echo "$ACCOUNT_INFO" | grep -o '"user.name":"[^"]*' | cut -d'"' -f4 || echo "unknown")

echo -e "${GREEN}✓ Azure authenticated${NC}"
echo "  User: $USER_NAME"
echo "  Subscription: $ACCOUNT_NAME"
echo ""

# Confirmation (unless --force)
if [ -z "$AUTO_APPROVE" ]; then
    echo -e "${BLUE}Do you want to proceed?${NC}"
    read -p "Type 'yes' to continue: " CONFIRM
    if [ "$CONFIRM" != "yes" ]; then
        echo "Aborted."
        exit 0
    fi
fi

# Change to terraform directory
cd "$PROJECT_DIR/terraform"

# Run terraform plan
echo ""
echo "Running Terraform plan..."
terraform plan -out=tfplan

# Apply terraform
echo ""
echo "Creating Azure resources..."
if [ -n "$AUTO_APPROVE" ]; then
    terraform apply tfplan
else
    terraform apply tfplan
fi

# Cleanup plan file
rm -f tfplan

echo ""
echo -e "${GREEN}=========================================="
echo "Resources created successfully!"
echo "==========================================${NC}"
echo ""
echo "Next steps:"
echo "  1. Run ./scripts/status.sh to view created resources"
echo "  2. Add Azure account to CutCosts.tech"
echo "  3. Wait 3+ days for detection (or use /test/detect-resources endpoint)"
echo "  4. Clean up when done: ./scripts/destroy.sh"
echo ""
echo -e "${YELLOW}⚠ IMPORTANT: Remember to destroy these resources to avoid charges!${NC}"
echo ""
