"""Strategy pattern for activity sync providers.

This module implements the Strategy pattern to allow different
activity sync providers (Strava, Garmin, Wahoo, etc.) to be
used interchangeably.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional

import models
from factories import StravaClientFactory


class ActivitySyncStrategy(ABC):
    """Abstract base class for activity sync strategies.

    This defines the interface that all sync providers must implement,
    following the Strategy pattern.
    """

    @abstractmethod
    def is_connected(self, user: models.User) -> bool:
        """Check if the user has connected this provider.

        Args:
            user: User to check

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def refresh_token_if_needed(self, user: models.User) -> Optional[Dict]:
        """Refresh the access token if it's expired.

        Args:
            user: User whose token to refresh

        Returns:
            Dictionary with new tokens if refreshed, None otherwise
        """
        pass

    @abstractmethod
    def fetch_activities(self, user: models.User) -> List[Dict]:
        """Fetch activities from the provider's API.

        Args:
            user: User whose activities to fetch

        Returns:
            List of activity dictionaries with standardized format
        """
        pass


class StravaActivitySyncStrategy(ActivitySyncStrategy):
    """Strategy for syncing activities from Strava."""

    def is_connected(self, user: models.User) -> bool:
        """Check if the user has connected their Strava account.

        Args:
            user: User to check

        Returns:
            True if connected, False otherwise
        """
        return bool(user.strava_access_token)

    def refresh_token_if_needed(self, user: models.User) -> Optional[Dict]:
        """Refresh the Strava access token if it's expired.

        Args:
            user: User whose token to refresh

        Returns:
            Dictionary with new tokens if refreshed, None otherwise
        """
        if datetime.now(timezone.utc) > user.strava_token_expires_at:
            print("Strava token expired, refreshing...")
            response = StravaClientFactory.refresh_access_token(user.strava_refresh_token)
            print("Token refreshed.")
            return {
                "access_token": response["access_token"],
                "refresh_token": response["refresh_token"],
                "expires_at": datetime.fromtimestamp(response["expires_at"], tz=timezone.utc),
            }
        return None

    def fetch_activities(self, user: models.User) -> List[Dict]:
        """Fetch activities from Strava API.

        Args:
            user: User whose activities to fetch

        Returns:
            List of activity dictionaries with standardized format
        """
        client = StravaClientFactory.create_authenticated_client(user.strava_access_token)

        activities = client.get_activities()

        # Convert Strava activities to standardized format
        standardized_activities = []
        for activity in activities:
            standardized_activities.append(
                {
                    "id": activity.id,
                    "name": activity.name,
                    "distance": float(activity.distance.magnitude),
                    "moving_time": int(activity.moving_time.total_seconds()),
                    "elapsed_time": int(activity.elapsed_time.total_seconds()),
                    "total_elevation_gain": float(activity.total_elevation_gain.magnitude),
                }
            )

        return standardized_activities


class ActivitySyncContext:
    """Context class for executing activity sync strategies.

    This class acts as a context in the Strategy pattern, allowing
    different sync strategies to be swapped at runtime.
    """

    def __init__(self, strategy: ActivitySyncStrategy):
        """Initialize with a specific sync strategy.

        Args:
            strategy: The sync strategy to use
        """
        self._strategy = strategy

    @property
    def strategy(self) -> ActivitySyncStrategy:
        """Get the current strategy.

        Returns:
            Current activity sync strategy
        """
        return self._strategy

    @strategy.setter
    def strategy(self, strategy: ActivitySyncStrategy):
        """Set a new strategy.

        Args:
            strategy: New sync strategy to use
        """
        self._strategy = strategy

    def sync_activities(self, user: models.User) -> tuple[bool, List[Dict], Optional[Dict]]:
        """Execute the sync using the current strategy.

        Args:
            user: User whose activities to sync

        Returns:
            Tuple of (is_connected, activities_list, token_update_dict)
        """
        # Check if connected
        if not self._strategy.is_connected(user):
            return False, [], None

        # Refresh token if needed
        token_update = self._strategy.refresh_token_if_needed(user)

        # Fetch activities
        activities = self._strategy.fetch_activities(user)

        return True, activities, token_update


# Future providers can be added easily:
#
# class GarminActivitySyncStrategy(ActivitySyncStrategy):
#     """Strategy for syncing activities from Garmin Connect."""
#     ...
#
# class WahooActivitySyncStrategy(ActivitySyncStrategy):
#     """Strategy for syncing activities from Wahoo."""
#     ...
