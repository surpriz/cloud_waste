#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "CutCosts AWS Testing Infrastructure Setup"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    echo "Please copy .env.example to .env and fill in your credentials:"
    echo "  cp .env.example .env"
    echo "  vim .env"
    exit 1
fi

# Source .env
source ../.env

# Check AWS CLI
echo -n "Checking AWS CLI... "
if ! command -v aws &> /dev/null; then
    echo -e "${RED}✗ Not installed${NC}"
    echo "Please install AWS CLI: https://aws.amazon.com/cli/"
    exit 1
fi
echo -e "${GREEN}✓ Installed${NC}"

# Check Terraform
echo -n "Checking Terraform... "
if ! command -v terraform &> /dev/null; then
    echo -e "${RED}✗ Not installed${NC}"
    echo "Please install Terraform: https://www.terraform.io/downloads"
    exit 1
fi
TERRAFORM_VERSION=$(terraform version -json | grep -o '"terraform_version":"[^"]*' | cut -d'"' -f4)
echo -e "${GREEN}✓ Installed (v${TERRAFORM_VERSION})${NC}"

# Check Terraform version
REQUIRED_VERSION="1.5.0"
if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$TERRAFORM_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo -e "${RED}✗ Terraform version must be >= ${REQUIRED_VERSION}${NC}"
    exit 1
fi

# Check AWS credentials
echo -n "Checking AWS credentials... "
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo -e "${RED}✗ Missing AWS credentials in .env${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Found in .env${NC}"

# Validate AWS credentials
echo -n "Validating AWS credentials... "
if ! aws sts get-caller-identity --region $AWS_REGION &> /dev/null; then
    echo -e "${RED}✗ Invalid credentials${NC}"
    exit 1
fi
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_USER=$(aws sts get-caller-identity --query Arn --output text)
echo -e "${GREEN}✓ Valid${NC}"
echo "  Account ID: $AWS_ACCOUNT_ID"
echo "  User/Role: $AWS_USER"

# Check region availability
echo -n "Checking region $AWS_REGION... "
if ! aws ec2 describe-regions --region-names $AWS_REGION &> /dev/null; then
    echo -e "${RED}✗ Invalid region${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Valid${NC}"

# Check owner email
if [ -z "$TF_VAR_owner_email" ]; then
    echo -e "${YELLOW}⚠ Warning: TF_VAR_owner_email not set in .env${NC}"
    echo "  This is required for resource tagging"
fi

# Display batch configuration
echo ""
echo "Batch Configuration:"
echo "  Batch 1 (Core): ${TF_VAR_enable_batch_1:-false} (~\$20/month)"
echo "  Batch 2 (Advanced): ${TF_VAR_enable_batch_2:-false} (~\$478/month)"
echo "  Batch 3 (Data/Transfer): ${TF_VAR_enable_batch_3:-false} (~\$378/month)"
echo "  Batch 4 (Platform/Messaging): ${TF_VAR_enable_batch_4:-false} (~\$243/month)"
echo "  Batch 5 (Search/IaC): ${TF_VAR_enable_batch_5:-false} (~\$700/month)"

# Calculate total cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 20))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 478))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 378))
[ "${TF_VAR_enable_batch_4}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 243))
[ "${TF_VAR_enable_batch_5}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 700))

echo ""
if [ $TOTAL_COST -eq 0 ]; then
    echo -e "${YELLOW}⚠ No batches enabled. Set TF_VAR_enable_batch_1=true in .env to enable Batch 1${NC}"
else
    echo -e "${GREEN}Estimated monthly cost: ~\$${TOTAL_COST}${NC}"
fi

# Initialize Terraform
echo ""
echo "Initializing Terraform..."
cd ../terraform
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
echo "  1. Review your .env configuration"
echo "  2. Run: ./scripts/create.sh"
echo "  3. Wait 3+ days for CutCosts detection"
echo "  4. Clean up: ./scripts/destroy.sh"
echo ""
