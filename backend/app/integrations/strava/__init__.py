"""Strava integration for activity synchronization.

This package contains all Strava-related functionality including OAuth,
client factories, sync strategies, and background tasks.
"""

from .client import StravaClientFactory
from .strategies import ActivitySyncContext, ActivitySyncStrategy, StravaActivitySyncStrategy
from .tasks import schedule_all_user_syncs_task, sync_single_user_strava_activities_task

__all__ = [
    "StravaClientFactory",
    "ActivitySyncStrategy",
    "StravaActivitySyncStrategy",
    "ActivitySyncContext",
    "sync_single_user_strava_activities_task",
    "schedule_all_user_syncs_task",
]
