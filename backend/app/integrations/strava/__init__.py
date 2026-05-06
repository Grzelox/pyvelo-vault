"""Strava integration for activity synchronization.

This package contains all Strava-related functionality including OAuth,
client factories, sync strategies, and background tasks.

Note: Tasks are not re-exported here to avoid circular imports with
the DI container. Import tasks directly from app.integrations.strava.tasks.
"""

from app.integrations.activity_sync import ActivitySyncContext, ActivitySyncStrategy

from .client import StravaClientFactory
from .strategies import StravaActivitySyncStrategy

__all__ = [
    "StravaClientFactory",
    "ActivitySyncStrategy",
    "StravaActivitySyncStrategy",
    "ActivitySyncContext",
]
