"""Core application functionality.

This package contains core utilities used throughout the application,
including configuration, database, security, and common dependencies.
"""

from .config import Settings, settings
from .database import SessionLocal, engine
from .dependencies import get_current_user, get_db
from .logging_config import get_logger
from .security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS,
    create_access_token,
    get_password_hash,
    verify_password,
)

__all__ = [
    "settings",
    "Settings",
    "engine",
    "SessionLocal",
    "get_db",
    "get_current_user",
    "get_logger",
    "get_password_hash",
    "verify_password",
    "create_access_token",
    "ACCESS_TOKEN_EXPIRE_MINUTES",
    "REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS",
]
