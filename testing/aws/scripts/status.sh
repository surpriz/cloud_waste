#!/bin/bash
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

echo "=========================================="
echo "CutCosts AWS Resources Status"
echo "=========================================="
echo ""

# Check if .env exists
if [ ! -f "../.env" ]; then
    echo -e "${RED}✗ Error: .env file not found${NC}"
    exit 1
fi

# Source .env
source ../.env

# Change to terraform directory
cd ../terraform

# Check if terraform state exists
if [ ! -f "terraform.tfstate" ]; then
    echo -e "${YELLOW}⚠ No terraform state found${NC}"
    echo "No resources have been created yet"
    echo "Run: ./scripts/create.sh"
    exit 0
fi

# Get terraform outputs
echo "Fetching resource information..."
echo ""

# VPC Info
VPC_ID=$(terraform output -raw vpc_id 2>/dev/null || echo "N/A")
echo -e "${BLUE}VPC:${NC}"
echo "  VPC ID: $VPC_ID"
echo ""

# Batch 1 Resources
if [ "${TF_VAR_enable_batch_1}" = "true" ]; then
    echo -e "${BLUE}Batch 1 Resources (Core):${NC}"

    # EBS Volume
    EBS_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"ebs_volume_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EBS_ID" ] && [ "$EBS_ID" != "null" ]; then
        EBS_STATE=$(aws ec2 describe-volumes --volume-ids $EBS_ID --query 'Volumes[0].State' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        EBS_SIZE=$(aws ec2 describe-volumes --volume-ids $EBS_ID --query 'Volumes[0].Size' --output text --region $AWS_REGION 2>/dev/null || echo "?")
        echo "  ✓ EBS Volume: $EBS_ID - ${EBS_SIZE}GB - $EBS_STATE (~\$0.10/month)"
    fi

    # Elastic IP
    EIP=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"elastic_ip":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EIP" ] && [ "$EIP" != "null" ]; then
        echo "  ✓ Elastic IP: $EIP - Unassociated (~\$3.60/month)"
    fi

    # Snapshot
    SNAP_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"snapshot_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$SNAP_ID" ] && [ "$SNAP_ID" != "null" ]; then
        echo "  ✓ Snapshot: $SNAP_ID (~\$0.05/month)"
    fi

    # EC2 Instance
    EC2_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"ec2_instance_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$EC2_ID" ] && [ "$EC2_ID" != "null" ]; then
        EC2_STATE=$(aws ec2 describe-instances --instance-ids $EC2_ID --query 'Reservations[0].Instances[0].State.Name' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        echo "  ✓ EC2 Instance: $EC2_ID - $EC2_STATE (~\$0/month when stopped)"
    fi

    # ALB
    ALB_ARN=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"alb_arn":"[^"]*' | cut -d'"' -f4)
    if [ -n "$ALB_ARN" ] && [ "$ALB_ARN" != "null" ]; then
        ALB_NAME=$(echo $ALB_ARN | awk -F'/' '{print $3}')
        echo "  ✓ Load Balancer: $ALB_NAME (~\$16/month)"
    fi

    # RDS
    RDS_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"rds_instance_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$RDS_ID" ] && [ "$RDS_ID" != "null" ]; then
        RDS_STATE=$(aws rds describe-db-instances --db-instance-identifier $RDS_ID --query 'DBInstances[0].DBInstanceStatus' --output text --region $AWS_REGION 2>/dev/null || echo "unknown")
        echo "  ✓ RDS Instance: $RDS_ID - $RDS_STATE (~\$0/month when stopped)"
    fi

    # NAT Gateway
    NAT_ID=$(terraform output -json batch_1_resources 2>/dev/null | grep -o '"nat_gateway_id":"[^"]*' | cut -d'"' -f4)
    if [ -n "$NAT_ID" ] && [ "$NAT_ID" != "null" ]; then
        echo "  ✓ NAT Gateway: $NAT_ID (~\$32/month)"
    fi

    echo ""
fi

# Calculate total cost
TOTAL_COST=0
[ "${TF_VAR_enable_batch_1}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 20))
[ "${TF_VAR_enable_batch_2}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 478))
[ "${TF_VAR_enable_batch_3}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 378))
[ "${TF_VAR_enable_batch_4}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 243))
[ "${TF_VAR_enable_batch_5}" = "true" ] && TOTAL_COST=$((TOTAL_COST + 700))

echo -e "${YELLOW}=========================================="
echo "Estimated Total Cost: ~\$${TOTAL_COST}/month"
echo "==========================================${NC}"
echo ""
echo "Commands:"
echo "  View detailed costs: terraform -chdir=../terraform show"
echo "  Destroy resources: ./scripts/destroy.sh"
echo ""
