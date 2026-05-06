"""Garmin Connect integration.

This package mirrors the Strava integration structure:
- client.py: OAuth + HTTP client factory helpers
- strategies.py: ActivitySyncStrategy implementation + normalization
- tasks.py: Celery-friendly sync tasks (delta sync)

Note: Tasks are not re-exported here to avoid circular imports with
the DI container. Import tasks directly from app.integrations.garmin.tasks.
"""

from .client import GarminClientFactory
from .strategies import GarminActivitySyncStrategy

__all__ = [
    "GarminClientFactory",
    "GarminActivitySyncStrategy",
]
