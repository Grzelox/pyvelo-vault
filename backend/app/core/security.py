"""Authentication and authorization utilities.

This module provides JWT token generation/validation and password hashing.
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

# Security configuration
SECRET_KEY = os.getenv("SECRET_KEY", "mock-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS = 30


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Bcrypt hash to compare against

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password using bcrypt.

    Args:
        password: Plain text password to hash

    Returns:
        Bcrypt hash of the password
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Create a JWT access token.

    Args:
        data: Dictionary of claims to encode in the token
        expires_delta: Optional custom expiration time

    Returns:
        Encoded JWT token string
    """
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token.

    Args:
        token: JWT token string

    Returns:
        Token payload if valid, None otherwise
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except JWTError:
        return None
