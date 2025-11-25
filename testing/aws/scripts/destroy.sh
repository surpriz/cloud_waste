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
echo "CutCosts AWS Resource Destruction"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "$PROJECT_DIR/.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    exit 1
fi

# Source .env and export all variables for Terraform
set -a  # Enable automatic export of all variables
source "$PROJECT_DIR/.env"
set +a  # Disable automatic export

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

# Pre-destruction: Disable CloudFront distributions (batch 3)
if [ "${TF_VAR_enable_batch_3}" = "true" ]; then
    echo ""
    echo "Checking for CloudFront distributions..."

    # Get CloudFront distribution ID from Terraform output
    CF_ID=$(terraform output -json 2>/dev/null | grep -o '"cloudfront_distribution_id":"[^"]*' | cut -d'"' -f4 || echo "")

    if [ -n "$CF_ID" ] && [ "$CF_ID" != "null" ]; then
        echo "Found CloudFront distribution: $CF_ID"

        # Check if distribution is enabled
        CF_ENABLED=$(aws cloudfront get-distribution --id "$CF_ID" 2>/dev/null | grep -o '"Enabled":[^,]*' | cut -d':' -f2 | tr -d ' ' || echo "")

        if [ "$CF_ENABLED" = "true" ]; then
            echo -e "${YELLOW}⚠ CloudFront distribution is enabled. Disabling it now...${NC}"
            echo "(This can take 15-30 minutes - please be patient)"

            # Extract config and disable
            aws cloudfront get-distribution-config --id "$CF_ID" --query 'DistributionConfig' > /tmp/cf-dist-config.json 2>/dev/null || true
            ETAG=$(aws cloudfront get-distribution-config --id "$CF_ID" --query 'ETag' --output text 2>/dev/null || echo "")

            if [ -n "$ETAG" ]; then
                # Disable the distribution
                sed -i '' 's/"Enabled": true/"Enabled": false/' /tmp/cf-dist-config.json 2>/dev/null || \
                sed -i 's/"Enabled": true/"Enabled": false/' /tmp/cf-dist-config.json 2>/dev/null

                aws cloudfront update-distribution \
                    --id "$CF_ID" \
                    --if-match "$ETAG" \
                    --distribution-config file:///tmp/cf-dist-config.json 2>/dev/null || true

                echo -e "${GREEN}✓ CloudFront distribution disabled${NC}"
                echo "Note: CloudFront will continue disabling in background (~15-20 min)"
                echo "Terraform destroy will wait for completion automatically."
            fi
        else
            echo "CloudFront distribution is already disabled or being disabled."
        fi
    fi
fi

# Destroy resources
echo ""
echo "Destroying AWS resources..."
echo "(CloudFront, ElastiCache, OpenSearch may take 30-45 minutes total)"
terraform destroy $AUTO_APPROVE

# Cleanup orphaned CloudWatch Log Groups
echo ""
echo "Checking for orphaned CloudWatch Log Groups..."

# Find all log groups related to CutCosts testing
ORPHANED_LOGS=$(aws logs describe-log-groups \
    --region "${AWS_DEFAULT_REGION:-eu-north-1}" \
    --query "logGroups[?contains(logGroupName, 'cutcosts')].logGroupName" \
    --output text 2>/dev/null || echo "")

if [ -n "$ORPHANED_LOGS" ]; then
    echo -e "${YELLOW}Found orphaned log groups:${NC}"
    for log_group in $ORPHANED_LOGS; do
        echo "  - $log_group"

        # Delete the log group
        if aws logs delete-log-group --log-group-name "$log_group" --region "${AWS_DEFAULT_REGION:-eu-north-1}" 2>/dev/null; then
            echo -e "    ${GREEN}✓ Deleted${NC}"
        else
            echo -e "    ${RED}✗ Failed to delete${NC}"
        fi
    done
else
    echo -e "${GREEN}✓ No orphaned log groups found${NC}"
fi

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
