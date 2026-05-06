"""Provider-agnostic activity sync abstractions.

This module contains the provider-independent parts of the integration layer:
- Strategy interface for "is_connected / refresh_token_if_needed / fetch_activities"
- Context that executes a given strategy

Concrete providers (e.g. Strava, Garmin) should implement ActivitySyncStrategy.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.models import User


class ActivitySyncStrategy(ABC):
    """Abstract base class for activity sync strategies.

    Concrete providers must implement the following operations:
    - determine whether a user has connected the provider
    - refresh tokens if needed
    - fetch provider activities and return a standardized list of dicts
    """

    @abstractmethod
    def is_connected(self, user: User) -> bool:
        """Return True if the user has connected this provider."""

    @abstractmethod
    def refresh_token_if_needed(self, user: User) -> dict | None:
        """Refresh provider access token if required.

        Returns:
            A dict containing updated token values (provider-specific keys),
            or None if no refresh was performed.
        """

    @abstractmethod
    def fetch_activities(self, user: User, after: datetime | None = None) -> list[dict]:
        """Fetch activities for the given user.

        Providers should return a standardized dict shape compatible with
        ActivityService.import_activities():
            {
              "id": int,
              "name": str,
              "distance": float,  # meters
              "moving_time": int,  # seconds
              "elapsed_time": int,  # seconds
              "total_elevation_gain": float,  # meters
              "calories": float | None,  # kcal
              "start_date": datetime (timezone-aware preferred)
            }
        """


class ActivitySyncContext:
    """Context class for executing activity sync strategies."""

    def __init__(self, strategy: ActivitySyncStrategy):
        self._strategy = strategy

    @property
    def strategy(self) -> ActivitySyncStrategy:
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: ActivitySyncStrategy):
        self._strategy = strategy

    def sync_activities(
        self, user: User, after: datetime | None = None
    ) -> tuple[bool, list[dict], dict | None]:
        """Execute the sync using the current strategy.

        Returns:
            (is_connected, activities_list, token_update_dict)
        """
        if not self._strategy.is_connected(user):
            return False, [], None

        token_update = self._strategy.refresh_token_if_needed(user)
        activities = self._strategy.fetch_activities(user, after=after)

        return True, activities, token_update
