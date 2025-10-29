#!/bin/bash

# ============================================================================
# CloudWaste - Manual User Account Activation Script
# ============================================================================
#
# This script manually activates a user account in production
# Use this if email verification is not working yet
#
# Usage:
#   ssh root@cutcosts.tech
#   cd /opt/cloudwaste
#   bash deployment/activate-user.sh your.email@example.com
#
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Check if email argument provided
if [ -z "$1" ]; then
    echo -e "${RED}Error: Email address required${NC}"
    echo "Usage: bash deployment/activate-user.sh your.email@example.com"
    exit 1
fi

USER_EMAIL="$1"

echo -e "${GREEN}▶${NC} Activating user account: $USER_EMAIL"

# SQL command to activate user and make them superuser
SQL_COMMAND="UPDATE users SET is_active = true, is_superuser = true WHERE email = '$USER_EMAIL';"

# Load environment variables
if [ -f ".env.prod" ]; then
    source .env.prod
else
    echo -e "${RED}Error: .env.prod not found${NC}"
    exit 1
fi

# Execute SQL in PostgreSQL container
docker exec cloudwaste_postgres psql \
    -U "${POSTGRES_USER:-cloudwaste}" \
    -d "${POSTGRES_DB:-cloudwaste}" \
    -c "$SQL_COMMAND"

# Check if user was updated
RESULT=$(docker exec cloudwaste_postgres psql \
    -U "${POSTGRES_USER:-cloudwaste}" \
    -d "${POSTGRES_DB:-cloudwaste}" \
    -t -c "SELECT email, is_active, is_superuser FROM users WHERE email = '$USER_EMAIL';")

if [ -z "$RESULT" ]; then
    echo -e "${YELLOW}⚠${NC} User $USER_EMAIL not found in database"
    echo "Please create an account first at https://cutcosts.tech/auth/register"
else
    echo -e "${GREEN}✓${NC} User activated successfully!"
    echo "$RESULT"
    echo ""
    echo -e "${GREEN}You can now log in at:${NC} https://cutcosts.tech/auth/login"
fi
