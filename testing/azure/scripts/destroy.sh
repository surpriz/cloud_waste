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
echo "CutCosts Azure Resource Destruction"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    exit 1
fi

# Source .env but DON'T export ARM_CLIENT_ID and ARM_CLIENT_SECRET
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
AUTO_APPROVE=""
BATCH_SPECIFIC=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --force)
            AUTO_APPROVE="-auto-approve"
            shift
            ;;
        --batch)
            shift
            BATCH_SPECIFIC="$1"
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--force] [--batch N]"
            exit 1
            ;;
    esac
done

# Change to terraform directory
cd "$PROJECT_DIR/terraform"

# Check if terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo -e "${YELLOW}⚠ No terraform state found${NC}"
    echo "No resources to destroy"
    exit 0
fi

# Check Azure login
echo "Checking Azure login..."
if ! az account show &> /dev/null; then
    echo -e "${RED}✗ Not logged in to Azure${NC}"
    echo "Please login with: az login --tenant $ARM_TENANT_ID"
    exit 1
fi

# Verify correct subscription
CURRENT_SUB=$(az account show --query id -o tsv 2>/dev/null)
if [ "$CURRENT_SUB" != "$ARM_SUBSCRIPTION_ID" ]; then
    az account set --subscription "$ARM_SUBSCRIPTION_ID"
fi
echo -e "${GREEN}✓ Azure authenticated${NC}"
echo ""

# Pre-destruction: Start deallocated VMs
echo ""
echo "Checking for deallocated VMs..."

# Get VM name from Terraform output
VM_NAME=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"vm_name":"[^"]*' | cut -d'"' -f4 || echo "")
RG_NAME=$(terraform output -raw resource_group_name 2>/dev/null || echo "cutcosts-testing-rg")

if [ -n "$VM_NAME" ] && [ "$VM_NAME" != "null" ]; then
    echo "Found VM: $VM_NAME"

    # Check VM power state
    VM_STATE=$(az vm get-instance-view --resource-group "$RG_NAME" --name "$VM_NAME" --query "instanceView.statuses[?starts_with(code, 'PowerState/')].displayStatus" -o tsv 2>/dev/null || echo "")

    if [[ "$VM_STATE" == *"deallocated"* ]] || [[ "$VM_STATE" == *"stopped"* ]]; then
        echo -e "${YELLOW}VM is deallocated/stopped. Starting VM to allow proper cleanup...${NC}"

        # Start VM and wait for completion (synchronous)
        az vm start --resource-group "$RG_NAME" --name "$VM_NAME"

        echo -e "${GREEN}✓ VM started successfully${NC}"
    else
        echo "VM is already running or in a valid state for deletion"
    fi
fi

# Show what will be destroyed
echo ""
echo "Analyzing resources to destroy..."
terraform plan -destroy

# Calculate current cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 68))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 0))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 0))

echo ""
echo -e "${YELLOW}This will destroy ALL test resources (saving ~€${TOTAL_COST}/month)${NC}"
echo ""

# Confirmation (unless --force)
if [ -z "$AUTO_APPROVE" ]; then
    echo -e "${RED}⚠ WARNING: This action cannot be undone!${NC}"
    read -p "Type 'destroy' to confirm: " CONFIRM
    if [ "$CONFIRM" != "destroy" ]; then
        echo "Aborted."
        exit 0
    fi
fi

# Destroy resources
echo ""
echo "Destroying Azure resources..."
terraform destroy $AUTO_APPROVE

echo ""
echo -e "${GREEN}=========================================="
echo "All resources destroyed successfully!"
echo "==========================================${NC}"
echo ""
echo "Cost savings: ~€${TOTAL_COST}/month"
echo ""

# Cleanup terraform files
read -p "Remove local terraform state? (y/n): " CLEANUP
if [ "$CLEANUP" = "y" ]; then
    rm -rf .terraform terraform.tfstate terraform.tfstate.backup .terraform.lock.hcl
    echo -e "${GREEN}✓ Local state cleaned up${NC}"
fi

echo ""
