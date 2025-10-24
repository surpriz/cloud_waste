#!/bin/bash

##############################################################################
# CloudWaste AWS Connectivity Diagnostic Script
#
# Purpose: Diagnose why the VPS cannot connect to AWS endpoints
#
# Usage:
#   chmod +x diagnose_aws_connectivity.sh
#   ./diagnose_aws_connectivity.sh
#
# This script tests:
# - Internet connectivity
# - DNS resolution for AWS endpoints
# - HTTPS connectivity to AWS
# - Firewall rules
# - Proxy configuration
# - boto3 connectivity from Docker container
##############################################################################

set -e

echo "=========================================="
echo "CloudWaste AWS Connectivity Diagnostic"
echo "=========================================="
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counter
PASSED=0
FAILED=0

# Function to print test result
test_result() {
    if [ $1 -eq 0 ]; then
        echo -e "${GREEN}✓ PASS${NC}: $2"
        ((PASSED++))
    else
        echo -e "${RED}✗ FAIL${NC}: $2"
        ((FAILED++))
    fi
}

# Test 1: Internet Connectivity
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 1: Internet Connectivity"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
if ping -c 3 -W 5 8.8.8.8 > /dev/null 2>&1; then
    test_result 0 "Internet connectivity (ping 8.8.8.8)"
else
    test_result 1 "Internet connectivity (ping 8.8.8.8) - No internet access!"
fi
echo ""

# Test 2: DNS Resolution
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 2: DNS Resolution for AWS Endpoints"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

DNS_ENDPOINTS=("sts.amazonaws.com" "ec2.amazonaws.com" "s3.amazonaws.com")
for endpoint in "${DNS_ENDPOINTS[@]}"; do
    if nslookup "$endpoint" > /dev/null 2>&1; then
        test_result 0 "DNS resolution for $endpoint"
    else
        test_result 1 "DNS resolution for $endpoint - Cannot resolve!"
        echo "  → Current DNS servers:"
        cat /etc/resolv.conf | grep nameserver
    fi
done
echo ""

# Test 3: HTTPS Connectivity to AWS
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 3: HTTPS Connectivity to AWS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

HTTPS_ENDPOINTS=("https://sts.amazonaws.com/" "https://ec2.amazonaws.com/")
for url in "${HTTPS_ENDPOINTS[@]}"; do
    if curl -s -I -m 10 "$url" > /dev/null 2>&1; then
        test_result 0 "HTTPS connection to $url"
    else
        test_result 1 "HTTPS connection to $url - Connection refused/timeout!"
        echo "  → Testing with verbose output:"
        curl -v -m 10 "$url" 2>&1 | head -20
    fi
done
echo ""

# Test 4: Firewall Rules (iptables)
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 4: Firewall Rules (iptables)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if command -v iptables > /dev/null 2>&1; then
    DROP_RULES=$(sudo iptables -L -n -v 2>/dev/null | grep -c DROP || true)
    if [ "$DROP_RULES" -gt 0 ]; then
        test_result 1 "iptables has $DROP_RULES DROP rules (may block AWS)"
        echo "  → Blocking rules:"
        sudo iptables -L -n -v | grep DROP
    else
        test_result 0 "iptables has no DROP rules"
    fi

    # Check OUTPUT chain
    OUTPUT_POLICY=$(sudo iptables -L OUTPUT -n | head -1 | awk '{print $4}')
    if [ "$OUTPUT_POLICY" = "DROP" ] || [ "$OUTPUT_POLICY" = "REJECT" ]; then
        test_result 1 "OUTPUT chain policy is $OUTPUT_POLICY (blocks outgoing traffic!)"
        echo "  → You need to allow HTTPS outgoing traffic:"
        echo "     sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT"
    else
        test_result 0 "OUTPUT chain policy is $OUTPUT_POLICY (allows outgoing traffic)"
    fi
else
    echo -e "${YELLOW}⚠ SKIP${NC}: iptables not found (may use ufw/firewalld)"
fi
echo ""

# Test 5: Proxy Configuration
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 5: Proxy Configuration"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PROXY_VARS=$(env | grep -i proxy || true)
if [ -n "$PROXY_VARS" ]; then
    echo -e "${YELLOW}⚠ WARNING${NC}: Proxy variables detected:"
    echo "$PROXY_VARS"
    echo "  → Make sure Docker containers have proxy configuration"
else
    test_result 0 "No proxy configuration detected"
fi
echo ""

# Test 6: Docker Container Network
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 6: Docker Container Network"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker ps | grep -q cloudwaste_backend; then
    # Test DNS from inside container
    if docker exec cloudwaste_backend ping -c 2 8.8.8.8 > /dev/null 2>&1; then
        test_result 0 "Container can ping external IPs"
    else
        test_result 1 "Container CANNOT ping external IPs - Docker network issue!"
    fi

    # Test DNS resolution from container
    if docker exec cloudwaste_backend nslookup sts.amazonaws.com > /dev/null 2>&1; then
        test_result 0 "Container can resolve AWS DNS"
    else
        test_result 1 "Container CANNOT resolve AWS DNS"
        echo "  → Container DNS config:"
        docker exec cloudwaste_backend cat /etc/resolv.conf
    fi

    # Test HTTPS from container
    if docker exec cloudwaste_backend curl -s -I -m 10 https://sts.amazonaws.com/ > /dev/null 2>&1; then
        test_result 0 "Container can connect to AWS via HTTPS"
    else
        test_result 1 "Container CANNOT connect to AWS via HTTPS"
    fi
else
    echo -e "${RED}✗ FAIL${NC}: cloudwaste_backend container not running!"
    echo "  → Start with: docker-compose up -d"
fi
echo ""

# Test 7: boto3 Connection Test
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Test 7: boto3 AWS Connection Test"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if docker ps | grep -q cloudwaste_backend; then
    echo "Testing boto3 connectivity..."
    BOTO_TEST=$(docker exec cloudwaste_backend python3 -c "
import boto3
from botocore.config import Config

config = Config(
    connect_timeout=10,
    read_timeout=10
)

try:
    # This doesn't require credentials, just tests connectivity
    sts = boto3.client('sts', region_name='us-east-1', config=config)
    # This will fail with auth error, but that means connectivity works
    sts.get_caller_identity()
    print('SUCCESS')
except Exception as e:
    if 'Could not connect' in str(e):
        print('CONNECTIVITY_ERROR')
    elif 'Unable to locate credentials' in str(e) or 'InvalidClientTokenId' in str(e):
        print('SUCCESS_AUTH_ERROR')  # Auth error means connectivity works!
    else:
        print(f'ERROR: {e}')
" 2>&1)

    if echo "$BOTO_TEST" | grep -q "SUCCESS"; then
        test_result 0 "boto3 can connect to AWS STS"
    elif echo "$BOTO_TEST" | grep -q "SUCCESS_AUTH_ERROR"; then
        test_result 0 "boto3 can connect to AWS STS (auth error is expected without credentials)"
    elif echo "$BOTO_TEST" | grep -q "CONNECTIVITY_ERROR"; then
        test_result 1 "boto3 CANNOT connect to AWS STS - Network blocked!"
        echo "  → Error details:"
        echo "$BOTO_TEST"
    else
        test_result 1 "boto3 connection test failed"
        echo "  → Error details:"
        echo "$BOTO_TEST"
    fi
else
    echo -e "${RED}✗ SKIP${NC}: cloudwaste_backend container not running"
fi
echo ""

# Summary
echo "=========================================="
echo "DIAGNOSTIC SUMMARY"
echo "=========================================="
echo -e "Tests Passed: ${GREEN}$PASSED${NC}"
echo -e "Tests Failed: ${RED}$FAILED${NC}"
echo ""

if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All tests passed!${NC}"
    echo "AWS connectivity should work. Check your AWS credentials."
else
    echo -e "${RED}✗ Some tests failed.${NC}"
    echo ""
    echo "RECOMMENDED ACTIONS:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    if ! ping -c 1 8.8.8.8 > /dev/null 2>&1; then
        echo "1. Fix internet connectivity on your VPS"
    fi

    if ! nslookup sts.amazonaws.com > /dev/null 2>&1; then
        echo "2. Fix DNS resolution:"
        echo "   echo 'nameserver 8.8.8.8' | sudo tee /etc/resolv.conf"
        echo "   echo 'nameserver 1.1.1.1' | sudo tee -a /etc/resolv.conf"
    fi

    if ! curl -s -I -m 5 https://sts.amazonaws.com/ > /dev/null 2>&1; then
        echo "3. Fix firewall rules (allow HTTPS outgoing):"
        echo "   sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT"
        echo "   sudo iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT"
    fi

    echo ""
    echo "After fixes, restart CloudWaste:"
    echo "   docker-compose restart backend celery_worker"
fi
echo ""
