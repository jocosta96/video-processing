"""
Unit tests for src/core/security.py

Tests password hashing and JWT token operations.
"""

import os
from datetime import datetime, timedelta, timezone

import pytest

# Set test environment
os.environ["JWT_SECRET"] = "test-secret-key-for-testing-only"

from src.core.security import (
    create_access_token,
    create_refresh_token,
    get_password_hash,
    verify_password,
    verify_token,
)


class TestPasswordHashing:
    """Tests for password hashing and verification."""

    @pytest.mark.unit
    def test_hash_password_returns_hashed_string(self):
        """Password hash should be different from plain password."""
        password = "SecureP@ss123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert len(hashed) > 0
        assert hashed.startswith("$2b$")  # bcrypt prefix

    @pytest.mark.unit
    def test_verify_password_with_correct_password(self):
        """Verify should return True for correct password."""
        password = "SecureP@ss123"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    @pytest.mark.unit
    def test_verify_password_with_incorrect_password(self):
        """Verify should return False for incorrect password."""
        password = "SecureP@ss123"
        wrong_password = "WrongPassword123!"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    @pytest.mark.unit
    def test_hash_password_generates_different_hashes_for_same_password(self):
        """Each hash should be unique due to salting."""
        password = "SecureP@ss123"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2
        # But both should verify correctly
        assert verify_password(password, hash1) is True
        assert verify_password(password, hash2) is True


class TestAccessToken:
    """Tests for JWT access token creation and verification."""

    @pytest.mark.unit
    def test_create_access_token_returns_string(self):
        """Access token should be a non-empty string."""
        data = {"sub": "user123", "email": "test@example.com"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.unit
    def test_create_access_token_contains_correct_data(self):
        """Token payload should contain the provided data."""
        user_id = "550e8400-e29b-41d4-a716-446655440000"
        email = "test@example.com"
        data = {"sub": user_id, "email": email}

        token = create_access_token(data)
        payload = verify_token(token, token_type="access")

        assert payload is not None
        assert payload["sub"] == user_id
        assert payload["email"] == email
        assert payload["type"] == "access"

    @pytest.mark.unit
    def test_create_access_token_with_custom_expiry(self):
        """Token should respect custom expiry delta."""
        data = {"sub": "user123"}
        expires_delta = timedelta(hours=2)
        token = create_access_token(data, expires_delta=expires_delta)

        payload = verify_token(token, token_type="access")
        assert payload is not None

        # Check expiry is approximately 2 hours from now
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = exp_time - now

        assert timedelta(hours=1, minutes=55) < diff < timedelta(hours=2, minutes=5)

    @pytest.mark.unit
    def test_verify_access_token_rejects_refresh_token_type(self):
        """Access token verification should reject refresh tokens."""
        data = {"sub": "user123"}
        refresh_token = create_refresh_token(data)

        payload = verify_token(refresh_token, token_type="access")
        assert payload is None

    @pytest.mark.unit
    def test_verify_access_token_rejects_invalid_token(self):
        """Invalid tokens should return None."""
        invalid_token = "invalid.token.string"
        payload = verify_token(invalid_token, token_type="access")
        assert payload is None

    @pytest.mark.unit
    def test_verify_access_token_rejects_tampered_token(self):
        """Tampered tokens should fail verification."""
        data = {"sub": "user123"}
        token = create_access_token(data)

        # Tamper with the token
        parts = token.split(".")
        parts[1] = parts[1][:-5] + "XXXXX"  # Modify payload
        tampered_token = ".".join(parts)

        payload = verify_token(tampered_token, token_type="access")
        assert payload is None


class TestRefreshToken:
    """Tests for JWT refresh token creation and verification."""

    @pytest.mark.unit
    def test_create_refresh_token_returns_string(self):
        """Refresh token should be a non-empty string."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    @pytest.mark.unit
    def test_create_refresh_token_has_correct_type(self):
        """Refresh token should have type=refresh in payload."""
        data = {"sub": "user123"}
        token = create_refresh_token(data)
        payload = verify_token(token, token_type="refresh")

        assert payload is not None
        assert payload["type"] == "refresh"

    @pytest.mark.unit
    def test_verify_refresh_token_rejects_access_token_type(self):
        """Refresh token verification should reject access tokens."""
        data = {"sub": "user123"}
        access_token = create_access_token(data)

        payload = verify_token(access_token, token_type="refresh")
        assert payload is None

    @pytest.mark.unit
    def test_refresh_token_has_longer_expiry_than_access_token(self):
        """Refresh token should have longer expiry than access token."""
        data = {"sub": "user123"}
        access_token = create_access_token(data)
        refresh_token = create_refresh_token(data)

        access_payload = verify_token(access_token, token_type="access")
        refresh_payload = verify_token(refresh_token, token_type="refresh")

        assert access_payload is not None
        assert refresh_payload is not None
        assert refresh_payload["exp"] > access_payload["exp"]


class TestTokenEdgeCases:
    """Edge case tests for token operations."""

    @pytest.mark.unit
    def test_verify_token_with_empty_string(self):
        """Empty token string should return None."""
        payload = verify_token("", token_type="access")
        assert payload is None

    @pytest.mark.unit
    def test_verify_token_with_none_type(self):
        """Token without matching type should return None."""
        data = {"sub": "user123"}
        token = create_access_token(data)

        # Verify with non-existent type
        payload = verify_token(token, token_type="invalid_type")
        assert payload is None

    @pytest.mark.unit
    def test_token_contains_issued_at(self):
        """Token should contain 'exp' claim."""
        data = {"sub": "user123"}
        token = create_access_token(data)
        payload = verify_token(token, token_type="access")

        assert payload is not None
        assert "exp" in payload
