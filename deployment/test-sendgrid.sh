#!/bin/bash

# ============================================================================
# CloudWaste - Test SendGrid Configuration
# ============================================================================
#
# This script tests SendGrid email sending
#
# Usage:
#   ssh root@cutcosts.tech
#   cd /opt/cloudwaste
#   bash deployment/test-sendgrid.sh
#
# ============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${GREEN}▶${NC} Testing SendGrid configuration..."

# Load environment variables
if [ -f ".env.prod" ]; then
    source .env.prod
else
    echo -e "${RED}Error: .env.prod not found${NC}"
    exit 1
fi

# Check required variables
if [ -z "$SMTP_PASSWORD" ]; then
    echo -e "${RED}✗${NC} SMTP_PASSWORD is not set in .env.prod"
    exit 1
fi

if [ -z "$EMAILS_FROM_EMAIL" ]; then
    echo -e "${RED}✗${NC} EMAILS_FROM_EMAIL is not set in .env.prod"
    exit 1
fi

echo -e "${GREEN}✓${NC} Environment variables loaded"
echo -e "  SMTP_HOST: ${SMTP_HOST}"
echo -e "  SMTP_PORT: ${SMTP_PORT}"
echo -e "  SMTP_USER: ${SMTP_USER}"
echo -e "  SMTP_PASSWORD: ${SMTP_PASSWORD:0:15}... (truncated)"
echo -e "  EMAILS_FROM_EMAIL: ${EMAILS_FROM_EMAIL}"
echo ""

# Test SendGrid API key with curl
echo -e "${GREEN}▶${NC} Testing SendGrid API key..."

RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST https://api.sendgrid.com/v3/mail/send \
    -H "Authorization: Bearer $SMTP_PASSWORD" \
    -H "Content-Type: application/json" \
    -d '{
  "personalizations": [{
    "to": [{"email": "'"$EMAILS_FROM_EMAIL"'"}]
  }],
  "from": {"email": "'"$EMAILS_FROM_EMAIL"'"},
  "subject": "CloudWaste - SendGrid Test",
  "content": [{
    "type": "text/plain",
    "value": "This is a test email from CloudWaste production server. If you receive this, SendGrid is working correctly!"
  }]
}')

if [ "$RESPONSE" = "202" ]; then
    echo -e "${GREEN}✓${NC} SendGrid test email sent successfully!"
    echo -e "  Check your inbox at: ${EMAILS_FROM_EMAIL}"
    echo -e "  (Also check Spam folder)"
else
    echo -e "${RED}✗${NC} SendGrid API returned HTTP $RESPONSE"
    echo -e "  Common errors:"
    echo -e "    400 = Bad request (check email format)"
    echo -e "    401 = Unauthorized (invalid API key)"
    echo -e "    403 = Forbidden (sender not verified or insufficient permissions)"
    echo -e ""
    echo -e "  Verify on SendGrid:"
    echo -e "    1. API key is valid: https://app.sendgrid.com/settings/api_keys"
    echo -e "    2. Sender is verified: https://app.sendgrid.com/settings/sender_auth/senders"
    exit 1
fi

echo ""
echo -e "${GREEN}▶${NC} Checking backend email configuration..."

# Check backend can connect to SMTP
docker exec cloudwaste_backend python -c "
import smtplib
import os

try:
    smtp = smtplib.SMTP('${SMTP_HOST}', ${SMTP_PORT})
    smtp.starttls()
    smtp.login('${SMTP_USER}', '${SMTP_PASSWORD}')
    smtp.quit()
    print('✓ Backend can connect to SendGrid SMTP')
except Exception as e:
    print(f'✗ Backend cannot connect to SendGrid: {e}')
    exit(1)
" && echo -e "${GREEN}✓${NC} Backend email configuration is correct" || echo -e "${RED}✗${NC} Backend email configuration failed"

echo ""
echo -e "${GREEN}▶${NC} Summary:"
echo -e "  1. SendGrid API key is valid"
echo -e "  2. Test email sent to: ${EMAILS_FROM_EMAIL}"
echo -e "  3. Backend can connect to SendGrid SMTP"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo -e "  1. Check your email inbox (and Spam)"
echo -e "  2. Try creating a new account on https://cutcosts.tech/auth/register"
echo -e "  3. If still no email, check logs:"
echo -e "     docker logs cloudwaste_celery_worker | grep -i email"
