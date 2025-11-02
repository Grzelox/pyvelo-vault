"""Strategy pattern for Strava activity sync.

This module implements the Strategy pattern for syncing activities from Strava.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models import User

from .client import StravaClientFactory


class ActivitySyncStrategy(ABC):
    """Abstract base class for activity sync strategies.

    This defines the interface that all sync providers must implement,
    following the Strategy pattern.
    """

    @abstractmethod
    def is_connected(self, user: User) -> bool:
        """Check if the user has connected this provider.

        Args:
            user: User to check

        Returns:
            True if connected, False otherwise
        """
        pass

    @abstractmethod
    def refresh_token_if_needed(self, user: User) -> Optional[Dict]:
        """Refresh the access token if it's expired.

        Args:
            user: User whose token to refresh

        Returns:
            Dictionary with new tokens if refreshed, None otherwise
        """
        pass

    @abstractmethod
    def fetch_activities(self, user: User, after: Optional[datetime] = None) -> List[Dict]:
        """Fetch activities from the provider's API.

        Args:
            user: User whose activities to fetch
            after: Optional datetime to fetch activities after (for delta sync)

        Returns:
            List of activity dictionaries with standardized format
        """
        pass


class StravaActivitySyncStrategy(ActivitySyncStrategy):
    """Strategy for syncing activities from Strava."""

    def is_connected(self, user: User) -> bool:
        """Check if the user has connected their Strava account.

        Args:
            user: User to check

        Returns:
            True if connected, False otherwise
        """
        return bool(user.strava_access_token)

    def refresh_token_if_needed(self, user: User) -> Optional[Dict]:
        """Refresh the Strava access token if it's expired.

        Args:
            user: User whose token to refresh

        Returns:
            Dictionary with new tokens if refreshed, None otherwise
        """
        # Make expiry time timezone-aware if it's naive
        expires_at = user.strava_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            print("Strava token expired, refreshing...")
            response = StravaClientFactory.refresh_access_token(user.strava_refresh_token)
            print("Token refreshed.")
            return {
                "access_token": response["access_token"],
                "refresh_token": response["refresh_token"],
                "expires_at": datetime.fromtimestamp(response["expires_at"], tz=timezone.utc),
            }
        return None

    def fetch_activities(self, user: User, after: Optional[datetime] = None) -> List[Dict]:
        """Fetch activities from Strava API.

        Args:
            user: User whose activities to fetch
            after: Optional datetime to fetch activities after (for delta sync)

        Returns:
            List of activity dictionaries with standardized format matching
            the Strava API DetailedActivity model structure
        """
        client = StravaClientFactory.create_authenticated_client(user.strava_access_token)

        # Fetch activities with optional after parameter for delta sync
        if after:
            activities = client.get_activities(after=after)
        else:
            activities = client.get_activities()

        # Convert Strava activities to standardized format
        # Based on Strava API v3 DetailedActivity model:
        # https://developers.strava.com/docs/reference/#api-models-DetailedActivity
        standardized_activities = []
        for activity in activities:
            try:
                # Extract values, handling various object types from stravalib
                # The stravalib library may wrap primitives in custom objects

                # Distance: float in meters
                distance = activity.distance
                if hasattr(distance, "num") or hasattr(distance, "magnitude"):
                    distance = float(
                        getattr(distance, "num", getattr(distance, "magnitude", distance))
                    )
                else:
                    distance = float(distance) if distance is not None else 0.0

                # Elevation: float in meters
                elevation = activity.total_elevation_gain
                if hasattr(elevation, "num") or hasattr(elevation, "magnitude"):
                    elevation = float(
                        getattr(elevation, "num", getattr(elevation, "magnitude", elevation))
                    )
                else:
                    elevation = float(elevation) if elevation is not None else 0.0

                # Moving time: integer in seconds
                moving_time = activity.moving_time
                if hasattr(moving_time, "total_seconds"):
                    moving_time = int(moving_time.total_seconds())
                elif hasattr(moving_time, "seconds"):
                    moving_time = int(moving_time.seconds)
                else:
                    moving_time = int(moving_time) if moving_time is not None else 0

                # Elapsed time: integer in seconds
                elapsed_time = activity.elapsed_time
                if hasattr(elapsed_time, "total_seconds"):
                    elapsed_time = int(elapsed_time.total_seconds())
                elif hasattr(elapsed_time, "seconds"):
                    elapsed_time = int(elapsed_time.seconds)
                else:
                    elapsed_time = int(elapsed_time) if elapsed_time is not None else 0

                standardized_activities.append(
                    {
                        "id": int(activity.id),
                        "name": str(activity.name),
                        "distance": distance,
                        "moving_time": moving_time,
                        "elapsed_time": elapsed_time,
                        "total_elevation_gain": elevation,
                    }
                )
            except Exception as e:
                # Log error but continue processing other activities
                print(f"Error processing activity {getattr(activity, 'id', 'unknown')}: {str(e)}")
                continue

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

    def sync_activities(
        self, user: User, after: Optional[datetime] = None
    ) -> tuple[bool, List[Dict], Optional[Dict]]:
        """Execute the sync using the current strategy.

        Args:
            user: User whose activities to sync
            after: Optional datetime to fetch activities after (for delta sync)

        Returns:
            Tuple of (is_connected, activities_list, token_update_dict)
        """
        # Check if connected
        if not self._strategy.is_connected(user):
            return False, [], None

        # Refresh token if needed
        token_update = self._strategy.refresh_token_if_needed(user)

        # Fetch activities
        activities = self._strategy.fetch_activities(user, after=after)

        return True, activities, token_update
