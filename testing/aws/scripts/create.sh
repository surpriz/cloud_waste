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
echo "CutCosts AWS Resource Creation"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Run ./scripts/setup.sh first"
    exit 1
fi

# Source .env
source "$PROJECT_DIR/.env"

# Parse command line arguments
BATCH_ARG=""
AUTO_APPROVE=""
while [[ $# -gt 0 ]]; do
    case $1 in
        --all)
            export TF_VAR_enable_batch_1=true
            export TF_VAR_enable_batch_2=true
            export TF_VAR_enable_batch_3=true
            export TF_VAR_enable_batch_4=true
            export TF_VAR_enable_batch_5=true
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
    export TF_VAR_enable_batch_4=false
    export TF_VAR_enable_batch_5=false

    for batch in $BATCH_ARG; do
        case $batch in
            1) export TF_VAR_enable_batch_1=true ;;
            2) export TF_VAR_enable_batch_2=true ;;
            3) export TF_VAR_enable_batch_3=true ;;
            4) export TF_VAR_enable_batch_4=true ;;
            5) export TF_VAR_enable_batch_5=true ;;
            *) echo -e "${YELLOW}⚠ Warning: Invalid batch number $batch${NC}" ;;
        esac
    done
fi

# Calculate estimated cost
TOTAL_COST=0
echo "Batches to create:"
[ "${TF_VAR_enable_batch_1}" = "true" ] && echo "  ✓ Batch 1 (Core) - ~\$20/month" && TOTAL_COST=$((TOTAL_COST + 20))
[ "${TF_VAR_enable_batch_2}" = "true" ] && echo "  ✓ Batch 2 (Advanced) - ~\$478/month" && TOTAL_COST=$((TOTAL_COST + 478))
[ "${TF_VAR_enable_batch_3}" = "true" ] && echo "  ✓ Batch 3 (Data/Transfer) - ~\$378/month" && TOTAL_COST=$((TOTAL_COST + 378))
[ "${TF_VAR_enable_batch_4}" = "true" ] && echo "  ✓ Batch 4 (Platform/Messaging) - ~\$243/month" && TOTAL_COST=$((TOTAL_COST + 243))
[ "${TF_VAR_enable_batch_5}" = "true" ] && echo "  ✓ Batch 5 (Search/IaC) - ~\$700/month" && TOTAL_COST=$((TOTAL_COST + 700))

if [ $TOTAL_COST -eq 0 ]; then
    echo -e "${RED}✗ No batches enabled${NC}"
    echo "Enable at least one batch in .env or use --batch flag"
    exit 1
fi

echo ""
echo -e "${YELLOW}Estimated monthly cost: ~\$${TOTAL_COST}${NC}"
echo ""

# Warning for expensive batches
if [ $TOTAL_COST -gt 100 ]; then
    echo -e "${RED}⚠ WARNING: High cost detected!${NC}"
    echo "This configuration will cost approximately \$${TOTAL_COST}/month"
    echo "Consider starting with Batch 1 only (~\$20/month)"
    echo ""
fi

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
echo "Creating AWS resources..."
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
echo "  2. Add AWS account to CutCosts.tech"
echo "  3. Wait 3+ days for detection (or use /test/detect-resources endpoint)"
echo "  4. Clean up when done: ./scripts/destroy.sh"
echo ""
echo -e "${YELLOW}⚠ IMPORTANT: Remember to destroy these resources to avoid charges!${NC}"
echo ""
