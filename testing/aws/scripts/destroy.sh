#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "CutCosts AWS Resource Destruction"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    exit 1
fi

# Source .env
source ../.env

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
cd ../terraform

# Check if terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo -e "${YELLOW}⚠ No terraform state found${NC}"
    echo "No resources to destroy"
    exit 0
fi

# Show what will be destroyed
echo "Analyzing resources to destroy..."
terraform plan -destroy

# Calculate current cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 20))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 478))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 378))
[ "${TF_VAR_enable_batch_4}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 243))
[ "${TF_VAR_enable_batch_5}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 700))

echo ""
echo -e "${YELLOW}This will destroy ALL test resources (saving ~\$${TOTAL_COST}/month)${NC}"
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
echo "Destroying AWS resources..."
terraform destroy $AUTO_APPROVE

echo ""
echo -e "${GREEN}=========================================="
echo "All resources destroyed successfully!"
echo "==========================================${NC}"
echo ""
echo "Cost savings: ~\$${TOTAL_COST}/month"
echo ""

# Cleanup terraform files
read -p "Remove local terraform state? (y/n): " CLEANUP
if [ "$CLEANUP" = "y" ]; then
    rm -rf .terraform terraform.tfstate terraform.tfstate.backup .terraform.lock.hcl
    echo -e "${GREEN}✓ Local state cleaned up${NC}"
fi

echo ""
