"""Data access layer using Repository pattern.

This package provides a clean abstraction over database operations.
"""

from .activity import ActivityRepository
from .base import BaseRepository
from .user import UserRepository

__all__ = ["BaseRepository", "UserRepository", "ActivityRepository"]
