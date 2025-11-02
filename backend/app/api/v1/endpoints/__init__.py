"""API v1 endpoints.

This package contains all version 1 API endpoints organized by resource.
"""

from . import activities, auth, health, strava, users

__all__ = ["auth", "users", "activities", "strava", "health"]
