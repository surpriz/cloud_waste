#!/bin/bash

##############################################################################
# CloudWaste Encryption Key Initialization Script
#
# ⚠️  CRITICAL: This script ensures ENCRYPTION_KEY persists across restarts
#
# Purpose:
# - Generate ENCRYPTION_KEY ONCE on first run
# - Store in persistent location (.encryption_key file)
# - Verify key consistency on subsequent runs
# - Prevent catastrophic data loss from key changes
#
# Usage:
#   ./init_encryption.sh
#
# Files:
#   .encryption_key - Persistent storage of encryption key (mounted as Docker volume)
#   .env - Environment variables (sources ENCRYPTION_KEY from .encryption_key)
##############################################################################

set -e  # Exit on error

# Use volume-mounted path if available (Docker), otherwise local path
# Docker mounts volume to /encryption_key_data
if [ -d "/encryption_key_data" ]; then
    ENCRYPTION_KEY_FILE="/encryption_key_data/encryption.key"
elif [ -d ".encryption_key_volume" ]; then
    ENCRYPTION_KEY_FILE=".encryption_key_volume/encryption.key"
else
    ENCRYPTION_KEY_FILE=".encryption_key"
fi

ENV_FILE=".env"

echo "🔐 CloudWaste Encryption Key Initialization"
echo "============================================"

# Function to generate a new Fernet key
generate_key() {
    python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
}

# Function to get hash of key (for logging, not security)
hash_key() {
    echo -n "$1" | sha256sum | cut -d' ' -f1
}

# Check if encryption key file exists
if [ -f "$ENCRYPTION_KEY_FILE" ]; then
    echo "✅ Found existing encryption key file"

    # Read existing key
    EXISTING_KEY=$(cat "$ENCRYPTION_KEY_FILE")
    KEY_HASH=$(hash_key "$EXISTING_KEY")

    echo "   Key hash: ${KEY_HASH:0:16}..."

    # Check if .env exists and has ENCRYPTION_KEY
    if [ -f "$ENV_FILE" ]; then
        # Extract ENCRYPTION_KEY from .env
        ENV_KEY=$(grep "^ENCRYPTION_KEY=" "$ENV_FILE" | cut -d'=' -f2)

        if [ -n "$ENV_KEY" ] && [ "$ENV_KEY" != "$EXISTING_KEY" ]; then
            echo "⚠️  WARNING: ENCRYPTION_KEY in .env differs from persistent key!"
            echo "   This will cause data loss. Overwriting .env with persistent key..."

            # Replace ENCRYPTION_KEY in .env with persistent key
            sed -i.bak "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$EXISTING_KEY|" "$ENV_FILE"
            echo "✅ Updated ENCRYPTION_KEY in .env to match persistent key"
        fi
    fi

    # Export for use
    export ENCRYPTION_KEY="$EXISTING_KEY"
    echo "✅ Encryption key loaded and validated"

else
    echo "🆕 No encryption key found - generating new one..."

    # Generate new key
    NEW_KEY=$(generate_key)
    KEY_HASH=$(hash_key "$NEW_KEY")

    # Save to persistent file
    echo "$NEW_KEY" > "$ENCRYPTION_KEY_FILE"
    chmod 600 "$ENCRYPTION_KEY_FILE"  # Secure permissions

    echo "✅ Generated new encryption key"
    echo "   Key hash: ${KEY_HASH:0:16}..."
    echo "   Saved to: $ENCRYPTION_KEY_FILE"

    # Update .env if it exists
    if [ -f "$ENV_FILE" ]; then
        if grep -q "^ENCRYPTION_KEY=" "$ENV_FILE"; then
            # Replace existing ENCRYPTION_KEY
            sed -i.bak "s|^ENCRYPTION_KEY=.*|ENCRYPTION_KEY=$NEW_KEY|" "$ENV_FILE"
        else
            # Add ENCRYPTION_KEY if missing
            echo "ENCRYPTION_KEY=$NEW_KEY" >> "$ENV_FILE"
        fi
        echo "✅ Updated ENCRYPTION_KEY in $ENV_FILE"
    fi

    # Export for use
    export ENCRYPTION_KEY="$NEW_KEY"
fi

echo ""
echo "============================================"
echo "🔐 Encryption initialized successfully!"
echo "============================================"
echo ""
echo "⚠️  IMPORTANT SECURITY NOTES:"
echo "   - .encryption_key contains your master encryption key"
echo "   - NEVER delete this file in production"
echo "   - NEVER commit this file to git"
echo "   - Backup this file in a secure location"
echo "   - If this key is lost, ALL encrypted data is UNRECOVERABLE"
echo ""
