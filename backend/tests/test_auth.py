"""Tests for authentication and authorization utilities."""

from datetime import datetime, timedelta, timezone

import pytest
from app.core import security
from app.models import User
from jose import JWTError, jwt


@pytest.mark.unit
class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_get_password_hash(self):
        """Test password hashing."""
        password = "mysecretpassword"
        hashed = security.get_password_hash(password)

        assert hashed != password
        assert isinstance(hashed, str)
        assert len(hashed) > 0

    def test_verify_password_correct(self):
        """Test password verification with correct password."""
        password = "correctpassword"
        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password."""
        password = "correctpassword"
        wrong_password = "wrongpassword"
        hashed = security.get_password_hash(password)

        assert security.verify_password(wrong_password, hashed) is False

    def test_different_hashes_for_same_password(self):
        """Test that same password produces different hashes (salt)."""
        password = "samepassword"
        hash1 = auth.get_password_hash(password)
        hash2 = auth.get_password_hash(password)

        # Hashes should be different due to random salt
        assert hash1 != hash2
        # But both should verify correctly
        assert auth.verify_password(password, hash1) is True
        assert auth.verify_password(password, hash2) is True


@pytest.mark.unit
class TestAuthentication:
    """Tests for user authentication."""

    def test_authenticate_user_success(self, test_db, test_user):
        """Test successful user authentication."""
        from app.repositories import UserRepository
        from app.services import UserService

        user_repo = UserRepository(test_db)
        user_service = UserService(user_repo)
        user = user_service.authenticate(test_user.email, "testpassword")

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_authenticate_user_wrong_password(self, test_db, test_user):
        """Test authentication with wrong password."""
        from app.repositories import UserRepository
        from app.services import UserService

        user_repo = UserRepository(test_db)
        user_service = UserService(user_repo)
        user = user_service.authenticate(test_user.email, "wrongpassword")

        assert user is None

    def test_authenticate_user_nonexistent(self, test_db):
        """Test authentication with nonexistent user."""
        from app.repositories import UserRepository
        from app.services import UserService

        user_repo = UserRepository(test_db)
        user_service = UserService(user_repo)
        user = user_service.authenticate("nonexistent@example.com", "password")

        assert user is None


@pytest.mark.unit
class TestJWTToken:
    """Tests for JWT token creation and validation."""

    def test_create_access_token(self):
        """Test creating a JWT access token."""
        data = {"sub": "user@example.com"}
        token = security.create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expiry(self):
        """Test creating a token with custom expiry."""
        data = {"sub": "user@example.com"}
        expires_delta = timedelta(minutes=30)
        token = auth.create_access_token(data, expires_delta)

        # Decode token to verify expiry
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])

        assert "exp" in payload
        assert "sub" in payload
        assert payload["sub"] == "user@example.com"

    def test_token_contains_correct_data(self):
        """Test that token contains the encoded data."""
        email = "test@example.com"
        data = {"sub": email}
        token = security.create_access_token(data)

        # Decode and verify
        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])
        assert payload["sub"] == email

    def test_token_expiry_set(self):
        """Test that token has expiry set."""
        data = {"sub": "user@example.com"}
        token = security.create_access_token(data)

        payload = jwt.decode(token, security.SECRET_KEY, algorithms=[security.ALGORITHM])

        assert "exp" in payload
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        now = datetime.now(timezone.utc)

        # Expiry should be in the future
        assert exp_time > now


@pytest.mark.unit
class TestGetCurrentUser:
    """Tests for get_current_user dependency."""

    @pytest.mark.asyncio
    async def test_get_current_user_success(self, test_db, test_user):
        """Test getting current user with valid token."""
        from app.core import get_current_user

        token = security.create_access_token(data={"sub": test_user.email})

        user = await get_current_user(token, test_db)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    @pytest.mark.asyncio
    async def test_get_current_user_invalid_token(self, test_db):
        """Test getting current user with invalid token."""
        from app.core import get_current_user
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user("invalid_token", test_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_nonexistent_user(self, test_db):
        """Test getting current user when user doesn't exist in database."""
        from app.core import get_current_user
        from fastapi import HTTPException

        token = security.create_access_token(data={"sub": "nonexistent@example.com"})

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token, test_db)

        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_get_current_user_missing_sub(self, test_db):
        """Test getting current user when token is missing 'sub' claim."""
        from app.core import get_current_user
        from fastapi import HTTPException

        # Create token without 'sub'
        token = jwt.encode(
            {"some_other_field": "value"},
            security.SECRET_KEY,
            algorithm=security.ALGORITHM,
        )

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(token, test_db)

        assert exc_info.value.status_code == 401


@pytest.mark.unit
class TestGetDB:
    """Tests for get_db dependency."""

    def test_get_db_requires_session(self):
        """Test that get_db requires SessionLocal to be configured."""
        from app.core import get_db

        # In test mode, SessionLocal is None, so get_db should raise RuntimeError
        with pytest.raises(RuntimeError, match="Database not configured"):
            db_gen = get_db()
            next(db_gen)
