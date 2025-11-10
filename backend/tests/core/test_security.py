"""Tests for security utilities (password hashing, JWT tokens, encryption)."""

import time
from datetime import timedelta
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet, InvalidToken

from app.core.security import (
    CredentialEncryption,
    create_access_token,
    create_refresh_token,
    credential_encryption,
    decode_token,
    get_password_hash,
    verify_password,
)


class TestPasswordHashing:
    """Test bcrypt password hashing and verification."""

    def test_get_password_hash(self):
        """Test that password hashing returns a valid bcrypt hash."""
        password = "Test123!@#"
        hashed = get_password_hash(password)

        # Bcrypt hashes start with $2b$ or $2a$
        assert hashed.startswith("$2") or hashed.startswith("$2b$")
        # Bcrypt hashes are 60 characters long
        assert len(hashed) == 60

    def test_verify_password_correct(self):
        """Test that correct password verification returns True."""
        password = "Test123!@#"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test that incorrect password verification returns False."""
        password = "Test123!@#"
        wrong_password = "Wrong123!@#"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_password_hash_uniqueness(self):
        """Test that hashing the same password twice produces different hashes (salt randomization)."""
        password = "Test123!@#"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True

    def test_password_72_byte_limit(self):
        """Test that passwords longer than 72 bytes are truncated (bcrypt limitation)."""
        # Create a password longer than 72 bytes
        long_password = "A" * 80  # 80 characters = 80 bytes (ASCII)
        truncated_password = "A" * 72  # First 72 bytes

        hashed = get_password_hash(long_password)

        # Both should verify successfully (bcrypt truncates at 72 bytes)
        assert verify_password(long_password, hashed) is True
        assert verify_password(truncated_password, hashed) is True

    def test_empty_password(self):
        """Test hashing and verifying empty password."""
        password = ""
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True
        assert verify_password("not-empty", hashed) is False

    def test_unicode_password(self):
        """Test hashing and verifying Unicode password."""
        password = "Test123!@#🔐🚀"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True
        assert verify_password("Test123!@#", hashed) is False


class TestJWTTokens:
    """Test JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating an access token with default expiration."""
        data = {"sub": "user@example.com"}
        token = create_access_token(data)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify payload
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "access"
        assert "exp" in payload

    def test_create_refresh_token(self):
        """Test creating a refresh token with default expiration."""
        data = {"sub": "user@example.com"}
        token = create_refresh_token(data)

        # Token should be a non-empty string
        assert isinstance(token, str)
        assert len(token) > 0

        # Decode and verify payload
        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"
        assert payload["type"] == "refresh"
        assert "exp" in payload

    def test_create_token_with_custom_expiration(self):
        """Test creating a token with custom expiration delta."""
        data = {"sub": "user@example.com"}
        expires_delta = timedelta(hours=1)
        token = create_access_token(data, expires_delta=expires_delta)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"

    def test_decode_valid_token(self):
        """Test decoding a valid JWT token."""
        data = {"sub": "user@example.com", "role": "admin"}
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user@example.com"
        assert payload["role"] == "admin"
        assert payload["type"] == "access"

    def test_decode_invalid_token(self):
        """Test decoding an invalid JWT token returns None."""
        invalid_token = "invalid.jwt.token"

        payload = decode_token(invalid_token)
        assert payload is None

    def test_decode_expired_token(self):
        """Test decoding an expired JWT token returns None."""
        data = {"sub": "user@example.com"}
        # Create token with negative expiration (already expired)
        expires_delta = timedelta(seconds=-1)
        token = create_access_token(data, expires_delta=expires_delta)

        # Wait a bit to ensure token is expired
        time.sleep(0.1)

        payload = decode_token(token)
        assert payload is None

    def test_token_contains_correct_type(self):
        """Test that access and refresh tokens have correct 'type' field."""
        data = {"sub": "user@example.com"}

        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)

        access_payload = decode_token(access_token)
        refresh_payload = decode_token(refresh_token)

        assert access_payload["type"] == "access"
        assert refresh_payload["type"] == "refresh"

    def test_token_with_empty_data(self):
        """Test creating a token with empty data."""
        data = {}
        token = create_access_token(data)

        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"
        assert "exp" in payload


class TestCredentialEncryption:
    """Test Fernet encryption/decryption for cloud credentials."""

    def test_encrypt_decrypt_roundtrip(self):
        """Test that encryption and decryption roundtrip works correctly."""
        encryption = credential_encryption
        original_data = "my-aws-secret-key-12345"

        # Encrypt
        encrypted = encryption.encrypt(original_data)
        assert isinstance(encrypted, bytes)
        assert encrypted != original_data.encode()

        # Decrypt
        decrypted = encryption.decrypt(encrypted)
        assert decrypted == original_data

    def test_encrypt_unicode_data(self):
        """Test encrypting and decrypting Unicode data."""
        encryption = credential_encryption
        original_data = "my-secret-🔐-unicode-data"

        encrypted = encryption.encrypt(original_data)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original_data

    def test_encrypt_empty_string(self):
        """Test encrypting and decrypting empty string."""
        encryption = credential_encryption
        original_data = ""

        encrypted = encryption.encrypt(original_data)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original_data

    def test_encrypt_long_string(self):
        """Test encrypting and decrypting a long string."""
        encryption = credential_encryption
        original_data = "A" * 10000  # 10KB string

        encrypted = encryption.encrypt(original_data)
        decrypted = encryption.decrypt(encrypted)

        assert decrypted == original_data

    def test_decrypt_with_wrong_key(self):
        """Test that decrypting with wrong key raises InvalidToken."""
        # Create encryption with test key
        encryption = credential_encryption
        original_data = "my-secret-key"
        encrypted = encryption.encrypt(original_data)

        # Create new encryption instance with different key
        different_key = Fernet.generate_key()
        wrong_encryption = CredentialEncryption()

        # Mock the cipher with different key
        with patch.object(wrong_encryption, "cipher", Fernet(different_key)):
            with pytest.raises(InvalidToken):
                wrong_encryption.decrypt(encrypted)

    def test_decrypt_invalid_data(self):
        """Test that decrypting invalid data raises InvalidToken."""
        encryption = credential_encryption
        invalid_encrypted_data = b"not-a-valid-fernet-token"

        with pytest.raises(InvalidToken):
            encryption.decrypt(invalid_encrypted_data)

    def test_credential_encryption_singleton(self):
        """Test that credential_encryption is a singleton instance."""
        from app.core.security import credential_encryption as encryption1
        from app.core.security import credential_encryption as encryption2

        # Both imports should reference the same instance
        assert encryption1 is encryption2

    def test_encryption_produces_different_ciphertexts(self):
        """Test that encrypting the same data twice produces different ciphertexts (Fernet uses random IV)."""
        encryption = credential_encryption
        original_data = "my-secret-key"

        encrypted1 = encryption.encrypt(original_data)
        encrypted2 = encryption.encrypt(original_data)

        # Ciphertexts should be different (Fernet uses random IV)
        assert encrypted1 != encrypted2

        # But both should decrypt to the same original data
        assert encryption.decrypt(encrypted1) == original_data
        assert encryption.decrypt(encrypted2) == original_data
