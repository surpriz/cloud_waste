# CloudWaste Encryption Key Management

## ⚠️ CRITICAL - READ THIS FIRST

**The `ENCRYPTION_KEY` is the MASTER KEY that encrypts ALL cloud account credentials** (AWS access keys, Azure client secrets, etc.) stored in CloudWaste's database.

**IF THIS KEY IS LOST OR CHANGED:**
- ✅ Application continues to run (no crash)
- ❌ **ALL cloud accounts become UNRECOVERABLE**
- ❌ **ALL users must re-enter their cloud credentials**
- ❌ **Complete data loss for encrypted credentials**

This document explains how CloudWaste protects against accidental key loss.

---

## Architecture Overview

### Problem We Solved

**Before (VULNERABLE):**
```
.env file (not versioned in git)
├── ENCRYPTION_KEY=abc123...
└── If .env regenerated → New key → Data loss!
```

**After (PROTECTED):**
```
Persistent storage (.encryption_key volume)
├── Generated ONCE on first startup
├── Persists across container rebuilds
├── Validated on every startup
└── Backed up separately from code
```

---

## How It Works

### 1. Initial Setup (First Time)

When you run `docker-compose up` for the first time:

```bash
# 1. init_encryption.sh runs automatically
./init_encryption.sh

# 2. Detects no existing key
🆕 No encryption key found - generating new one...

# 3. Generates a Fernet key
✅ Generated new encryption key
   Key hash: a4b8c2d6e1f3...
   Saved to: .encryption_key

# 4. Updates .env with generated key
✅ Updated ENCRYPTION_KEY in .env

# 5. Application starts with validated key
🔐 Validating ENCRYPTION_KEY...
✅ ENCRYPTION_KEY validated
```

### 2. Subsequent Startups

On every startup after the first:

```bash
# 1. init_encryption.sh runs
./init_encryption.sh

# 2. Finds existing key
✅ Found existing encryption key file
   Key hash: a4b8c2d6e1f3...

# 3. Validates key consistency
✅ Encryption key loaded and validated

# 4. Application validates key
🔐 Validating ENCRYPTION_KEY...
✅ ENCRYPTION_KEY validated
   Key hash (first 16 chars): a4b8c2d6e1f3...
```

### 3. Protection Mechanisms

#### A. Persistent Docker Volume

```yaml
# docker-compose.yml
volumes:
  encryption_key:  # Named volume persists across rebuilds

services:
  backend:
    volumes:
      - encryption_key:/app/.encryption_key_volume  # Mounted in container
```

**Why:** Docker named volumes persist even if you run `docker-compose down -v` (removes anonymous volumes only).

#### B. Startup Script (`init_encryption.sh`)

**Responsibilities:**
1. Generate key ONCE if missing
2. Verify key consistency on subsequent runs
3. Sync key to `.env` if needed
4. Prevent accidental key changes

**Protection:**
```bash
if [ "$ENV_KEY" != "$EXISTING_KEY" ]; then
    echo "⚠️  WARNING: ENCRYPTION_KEY in .env differs from persistent key!"
    echo "   Overwriting .env with persistent key..."
    # Prevents accidental key change
fi
```

#### C. Application Validation (`app/main.py`)

On every FastAPI startup:
1. Check ENCRYPTION_KEY is set
2. Validate it's not a placeholder
3. Log key hash (audit trail)
4. Warn about key importance

```python
@app.on_event("startup")
async def startup_event() -> None:
    validate_encryption_key()
```

---

## File Structure

```
CloudWaste/
├── .encryption_key              # ⚠️  NEVER commit to git
│                                # Persistent key storage
│
├── .env                         # Sources ENCRYPTION_KEY from .encryption_key
│                                # Auto-synced by init_encryption.sh
│
├── init_encryption.sh           # Key initialization script
│                                # Runs on every container startup
│
├── docker-compose.yml           # Mounts encryption_key volume
│                                # Calls init_encryption.sh before app start
│
└── backend/app/main.py          # Validates key on startup
                                 # Logs key hash for audit
```

---

## What If... (Disaster Scenarios)

### Scenario 1: `docker-compose down -v` (Remove Volumes)

**Risk:** Anonymous volumes deleted, named volumes preserved

**Protection:**
```bash
docker-compose down -v
# ✅ encryption_key volume preserved (named volume)
docker-compose up
# ✅ Key loaded from persistent volume
# ✅ All cloud accounts still accessible
```

### Scenario 2: Someone Manually Changes ENCRYPTION_KEY in .env

**Risk:** Key mismatch causes credential decryption failure

**Protection:**
```bash
docker-compose up
# 1. init_encryption.sh runs
⚠️  WARNING: ENCRYPTION_KEY in .env differs from persistent key!
   Overwriting .env with persistent key...
✅ Updated ENCRYPTION_KEY in .env to match persistent key

# 2. Application starts with correct key
✅ All cloud accounts still accessible
```

### Scenario 3: Accidental Deletion of `.encryption_key` File

**Risk:** Key permanently lost, data unrecoverable

**Protection:**
1. **Prevention:** File stored in Docker volume (not easily deleted)
2. **Detection:** Application fails to start if key missing
3. **Mitigation:** BACKUP strategy (see below)

```bash
# If .encryption_key is deleted:
docker-compose up
🆕 No encryption key found - generating new one...
❌ All existing cloud accounts will fail to decrypt!
```

**Recovery:** Restore from backup (see Backup Strategy below)

### Scenario 4: Docker Image Rebuild

**Risk:** Container rebuilt with fresh filesystem

**Protection:**
```bash
docker-compose build --no-cache
docker-compose up
# ✅ encryption_key volume still mounted
# ✅ Key loaded from persistent volume
# ✅ All cloud accounts still accessible
```

---

## Backup Strategy

### ⚠️ MANDATORY: Backup Your ENCRYPTION_KEY

**Why:** The encryption key is the ONLY way to decrypt cloud credentials. If lost, data is UNRECOVERABLE.

### How to Backup

#### Option 1: Manual Backup (Development)

```bash
# 1. Find the encryption key volume
docker volume inspect cloudwaste_encryption_key

# 2. Copy key from volume to safe location
docker run --rm -v cloudwaste_encryption_key:/data -v $(pwd):/backup \
  alpine cp /data/.encryption_key /backup/encryption_key.backup

# 3. Store backup in secure location
# - Password manager (1Password, Bitwarden)
# - Encrypted USB drive
# - Secure cloud storage (encrypted)
```

#### Option 2: Automated Backup (Production)

```bash
# Add to cron (runs daily at 2 AM)
0 2 * * * /path/to/cloudwaste/backup_encryption_key.sh
```

**Example `backup_encryption_key.sh`:**
```bash
#!/bin/bash
DATE=$(date +%Y%m%d)
docker run --rm \
  -v cloudwaste_encryption_key:/data \
  -v /secure/backup/location:/backup \
  alpine cp /data/.encryption_key /backup/encryption_key.$DATE
```

### How to Restore

**If you need to restore from backup:**

```bash
# 1. Stop all services
docker-compose down

# 2. Restore key to volume
docker run --rm \
  -v cloudwaste_encryption_key:/data \
  -v $(pwd):/backup \
  alpine sh -c "cp /backup/encryption_key.backup /data/.encryption_key && chmod 600 /data/.encryption_key"

# 3. Restart services
docker-compose up -d

# 4. Verify key hash matches
docker-compose logs backend | grep "Key hash"
```

---

## Production Deployment Checklist

Before deploying to production:

- [ ] **Backup Strategy**: Automated daily backups configured
- [ ] **Backup Testing**: Restore procedure tested successfully
- [ ] **Monitoring**: Alerts set up if key hash changes
- [ ] **Access Control**: Only authorized personnel can access backups
- [ ] **Documentation**: Team trained on encryption key importance
- [ ] **Disaster Recovery Plan**: Written procedure for key loss scenarios
- [ ] **Secret Management**: Consider using AWS Secrets Manager / Azure Key Vault for production

---

## Migration to Production Secret Management (Future - Phase 2)

For production deployments, consider migrating to cloud-native secret management:

### AWS Secrets Manager

```python
# Example: Load ENCRYPTION_KEY from AWS Secrets Manager
import boto3

def get_encryption_key():
    client = boto3.client('secretsmanager')
    response = client.get_secret_value(SecretId='cloudwaste/encryption-key')
    return response['SecretString']
```

### Azure Key Vault

```python
# Example: Load ENCRYPTION_KEY from Azure Key Vault
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

def get_encryption_key():
    credential = DefaultAzureCredential()
    client = SecretClient(vault_url="https://cloudwaste-kv.vault.azure.net/", credential=credential)
    secret = client.get_secret("encryption-key")
    return secret.value
```

**Benefits:**
- Automatic key rotation
- Audit logging
- Fine-grained access control
- Built-in redundancy

---

## Key Rotation (Advanced - Phase 3)

**IMPORTANT:** Currently, CloudWaste does NOT support key rotation. Changing the key will break all existing data.

**Future implementation** will support:
1. Multiple key versions
2. Gradual re-encryption
3. Zero-downtime rotation

**Current workaround for key rotation:**
1. Export all cloud accounts (decrypted)
2. Change ENCRYPTION_KEY
3. Re-import all cloud accounts (encrypted with new key)
4. Validate all accounts work correctly

---

## Troubleshooting

### Error: "ENCRYPTION_KEY not set in environment"

**Cause:** `.env` file missing or `ENCRYPTION_KEY` variable missing

**Fix:**
```bash
# Run initialization script manually
./init_encryption.sh
```

### Error: "ENCRYPTION_KEY appears to be a placeholder"

**Cause:** `.env` still has template value like `your-fernet-encryption-key-base64-encoded`

**Fix:**
```bash
# Let init_encryption.sh generate a proper key
./init_encryption.sh

# Or generate manually:
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

### Error: Cloud accounts fail to decrypt

**Symptoms:**
```
cryptography.fernet.InvalidToken
```

**Cause:** ENCRYPTION_KEY changed since accounts were created

**Diagnosis:**
```bash
# Check current key hash
docker-compose logs backend | grep "Key hash"

# Compare with expected hash (from audit logs or backup)
```

**Fix:**
1. Restore correct ENCRYPTION_KEY from backup
2. If no backup: Users must re-enter cloud credentials (DATA LOSS)

---

## Security Best Practices

1. **Never commit `.encryption_key` to git** ✅ Already in `.gitignore`
2. **Never log the actual key** ✅ We only log hash
3. **Restrict file permissions** ✅ Script sets `chmod 600`
4. **Backup regularly** ⚠️ Set up automated backups
5. **Test restores** ⚠️ Regularly test backup recovery
6. **Monitor key changes** ⚠️ Alert on key hash changes
7. **Least privilege access** ⚠️ Limit who can access backups

---

## Summary

### What We Built (Phase 1)

✅ **Persistent Storage**: Docker volume survives rebuilds
✅ **Auto-Initialization**: Key generated once, validated always
✅ **Startup Validation**: Application blocks if key invalid
✅ **Sync Protection**: Script prevents accidental key changes
✅ **Documentation**: Comprehensive guide (this document)

### What's Still Needed (Future Phases)

⏳ **Phase 2**: Automated backups, cloud secret management
⏳ **Phase 3**: Key rotation without data loss

### Bottom Line

**You will NEVER lose cloud accounts due to ENCRYPTION_KEY changes** as long as:
1. Docker volume `cloudwaste_encryption_key` exists
2. You have backups of `.encryption_key` file
3. You never manually delete the volume

**If both are lost:** Users must re-enter credentials (acceptable in development, UNACCEPTABLE in production - hence Phase 2/3).
