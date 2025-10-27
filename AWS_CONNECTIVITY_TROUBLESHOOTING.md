# AWS Connectivity Troubleshooting Guide

## Problem: "Could not connect to the endpoint URL: https://sts.amazonaws.com/"

This error occurs when CloudWaste running on your VPS cannot establish a connection to AWS services.

---

## 🚨 Common Causes

1. **Firewall blocking outbound HTTPS traffic** (Most common on VPS)
2. **DNS resolution failure** for amazonaws.com domains
3. **No internet connectivity** from VPS
4. **Proxy configuration** issues
5. **Docker network** misconfiguration

---

## 🔍 Step 1: Run the Diagnostic Script

CloudWaste includes an automated diagnostic script that will test all connectivity aspects.

### On your VPS (cutcosts.tech):

```bash
# 1. Download the diagnostic script from your local machine
scp diagnose_aws_connectivity.sh user@cutcosts.tech:/path/to/cloudwaste/

# 2. SSH into your VPS
ssh user@cutcosts.tech

# 3. Navigate to CloudWaste directory
cd /path/to/cloudwaste

# 4. Make script executable
chmod +x diagnose_aws_connectivity.sh

# 5. Run diagnostic
./diagnose_aws_connectivity.sh
```

The script will output a detailed report identifying the exact problem.

---

## 🔧 Solutions Based on Diagnostic Results

### Solution 1: Firewall Blocking HTTPS (Most Common)

**Symptoms:**
- ✅ Internet connectivity works (ping 8.8.8.8 succeeds)
- ✅ DNS resolution works (nslookup sts.amazonaws.com succeeds)
- ❌ HTTPS connection fails (curl https://sts.amazonaws.com/ fails)

**Fix:**

```bash
# Allow outbound HTTPS traffic
sudo iptables -A OUTPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A OUTPUT -p tcp --dport 80 -j ACCEPT

# Save rules (method depends on your Linux distribution)

# Debian/Ubuntu
sudo iptables-save | sudo tee /etc/iptables/rules.v4

# CentOS/RHEL
sudo service iptables save

# Or use netfilter-persistent
sudo apt-get install iptables-persistent
sudo netfilter-persistent save
```

**For ufw users:**
```bash
sudo ufw allow out 443/tcp
sudo ufw allow out 80/tcp
sudo ufw reload
```

**After fix:**
```bash
# Restart CloudWaste
docker-compose restart backend celery_worker celery_beat
```

---

### Solution 2: DNS Resolution Failure

**Symptoms:**
- ✅ Internet connectivity works
- ❌ nslookup sts.amazonaws.com fails
- ❌ dig sts.amazonaws.com fails

**Fix:**

```bash
# 1. Update /etc/resolv.conf with public DNS servers
sudo bash -c 'cat > /etc/resolv.conf' <<EOF
nameserver 8.8.8.8
nameserver 1.1.1.1
nameserver 8.8.4.4
EOF

# 2. Make it immutable (prevent auto-reset)
sudo chattr +i /etc/resolv.conf

# 3. Restart Docker
sudo systemctl restart docker

# 4. Restart CloudWaste
docker-compose restart backend celery_worker celery_beat
```

**Alternative - Configure Docker DNS:**

Edit `/etc/docker/daemon.json`:
```json
{
  "dns": ["8.8.8.8", "1.1.1.1"]
}
```

Then:
```bash
sudo systemctl restart docker
docker-compose down && docker-compose up -d
```

---

### Solution 3: No Internet Connectivity

**Symptoms:**
- ❌ ping 8.8.8.8 fails
- ❌ All external connections fail

**Fix:**

This is a VPS infrastructure issue. Contact your VPS provider:
- OVH
- DigitalOcean
- Hetzner
- AWS EC2
- etc.

Check:
1. VPS is running
2. Network interface is up: `ip addr show`
3. Default gateway is set: `ip route show`
4. VPS firewall settings in provider's control panel

---

### Solution 4: Proxy Configuration

**Symptoms:**
- `env | grep -i proxy` shows proxy variables
- Direct connections fail but proxy is required

**Fix:**

Add proxy configuration to `docker-compose.yml`:

```yaml
services:
  backend:
    environment:
      - HTTP_PROXY=http://your-proxy:port
      - HTTPS_PROXY=http://your-proxy:port
      - NO_PROXY=localhost,127.0.0.1,postgres,redis

  celery_worker:
    environment:
      - HTTP_PROXY=http://your-proxy:port
      - HTTPS_PROXY=http://your-proxy:port
      - NO_PROXY=localhost,127.0.0.1,postgres,redis

  celery_beat:
    environment:
      - HTTP_PROXY=http://your-proxy:port
      - HTTPS_PROXY=http://your-proxy:port
      - NO_PROXY=localhost,127.0.0.1,postgres,redis
```

Then:
```bash
docker-compose down && docker-compose up -d
```

---

### Solution 5: Docker Network Issues

**Symptoms:**
- Host can connect to AWS
- Docker container cannot connect to AWS

**Fix:**

```bash
# 1. Restart Docker
sudo systemctl restart docker

# 2. Recreate Docker networks
docker-compose down
docker network prune -f
docker-compose up -d

# 3. Check container DNS
docker exec cloudwaste_backend cat /etc/resolv.conf

# 4. Test from container
docker exec cloudwaste_backend ping -c 3 8.8.8.8
docker exec cloudwaste_backend curl -I https://sts.amazonaws.com/
```

---

## 📋 Verification Steps

After applying any fix, verify connectivity:

### 1. Test from VPS host:
```bash
curl -I https://sts.amazonaws.com/
# Expected: HTTP/1.1 403 Forbidden (or any HTTP response)
```

### 2. Test from Docker container:
```bash
docker exec cloudwaste_backend curl -I https://sts.amazonaws.com/
# Expected: HTTP response (not connection error)
```

### 3. Test boto3 connectivity:
```bash
docker exec cloudwaste_backend python3 <<'EOF'
import boto3
from botocore.config import Config

config = Config(connect_timeout=10, read_timeout=10)
sts = boto3.client('sts', region_name='us-east-1', config=config)

try:
    # This will fail with auth error, but that's OK - it means connectivity works!
    sts.get_caller_identity()
except Exception as e:
    if 'Could not connect' in str(e):
        print("❌ FAIL: Cannot connect to AWS")
    elif 'Unable to locate credentials' in str(e):
        print("✅ SUCCESS: Connectivity works! (auth error is expected)")
    else:
        print(f"Error: {e}")
EOF
```

### 4. Check CloudWaste logs:
```bash
# Watch backend logs for AWS connection attempts
docker logs -f cloudwaste_backend

# Watch celery worker logs
docker logs -f cloudwaste_celery_worker
```

Look for these log messages:
- ✅ `🔍 Starting AWS credential validation...`
- ✅ `✅ STS client created successfully`
- ✅ `✅ AWS credentials validated successfully!`

Or error messages:
- ❌ `❌ ENDPOINT CONNECTION ERROR: Cannot connect to AWS STS`
- ❌ `❌ CONNECTION ERROR: Network issue connecting to AWS`

---

## 📊 Enhanced Logging

CloudWaste now includes detailed debug logging for AWS connectivity issues.

When you create a scan, check the logs:

```bash
docker logs cloudwaste_celery_worker 2>&1 | grep -A 20 "AWS credential validation"
```

You should see detailed output like:
```
🔍 Starting AWS credential validation...
📍 Attempting to connect to AWS STS endpoint (us-east-1)
✅ STS client created successfully
📞 Calling sts.get_caller_identity()...
✅ AWS credentials validated successfully!
   Account ID: 123456789012
   ARN: arn:aws:iam::123456789012:user/cloudwaste-scanner
```

Or detailed error messages if it fails.

---

## 🆘 Still Not Working?

If you've tried all solutions and still have issues:

### 1. Collect diagnostic information:

```bash
# Run full diagnostic
./diagnose_aws_connectivity.sh > aws_diagnostic_report.txt 2>&1

# Collect CloudWaste logs
docker logs cloudwaste_backend > backend_logs.txt 2>&1
docker logs cloudwaste_celery_worker > worker_logs.txt 2>&1

# System information
uname -a > system_info.txt
docker version >> system_info.txt
docker-compose version >> system_info.txt
```

### 2. Check common VPS restrictions:

Some VPS providers restrict outbound connections by default:
- **OVHcloud**: May require enabling outbound traffic in firewall
- **Hetzner**: Check Cloud Firewall settings
- **DigitalOcean**: Check Cloud Firewalls in control panel
- **AWS EC2**: Check Security Group outbound rules

### 3. Provider-specific fixes:

**OVHcloud:**
```bash
# Check if OVH firewall is blocking
sudo iptables -L -n -v | grep -i ovh
```

**Hetzner Cloud:**
- Go to Cloud Console → Firewalls
- Ensure outbound HTTPS is allowed

**DigitalOcean:**
- Go to Networking → Firewalls
- Add outbound rule: HTTPS (port 443), All IPv4, All IPv6

---

## 📞 Contact Support

If you still cannot resolve the issue, provide:
1. Output of `./diagnose_aws_connectivity.sh`
2. VPS provider name
3. CloudWaste logs (`docker logs cloudwaste_backend`)
4. Whether the problem started after a specific change

---

## ✅ Quick Fix Checklist

- [ ] Run `./diagnose_aws_connectivity.sh`
- [ ] Allow outbound HTTPS (port 443) in firewall
- [ ] Configure public DNS servers (8.8.8.8, 1.1.1.1)
- [ ] Restart Docker and CloudWaste
- [ ] Verify with `curl -I https://sts.amazonaws.com/`
- [ ] Test AWS scan from CloudWaste UI
- [ ] Check logs for success messages

---

## 🎯 Expected Behavior After Fix

Once connectivity is fixed:
1. AWS account validation succeeds
2. Scans complete successfully
3. Resources are detected
4. No "Could not connect" errors in logs

**Test a scan:**
- Go to cutcosts.tech dashboard
- Create/select an AWS account
- Click "Scan Now"
- Wait 2-5 minutes
- Check scan status should be "Completed" (not "Failed")
