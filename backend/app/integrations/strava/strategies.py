"""Strava activity sync strategy (provider implementation)."""

import time
from datetime import datetime, timezone
from numbers import Real

from app.core import get_logger
from app.integrations.activity_sync import ActivitySyncStrategy
from app.models import User
from stravalib.exc import RateLimitExceeded, RateLimitTimeout

from .client import StravaClientFactory

_RATE_LIMIT_MAX_RETRIES = 6
_RATE_LIMIT_BASE_DELAY_SECONDS = 60
_RATE_LIMIT_MAX_DELAY_SECONDS = 900


class StravaActivitySyncStrategy(ActivitySyncStrategy):
    """Strategy for syncing activities from Strava."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def is_connected(self, user: User) -> bool:
        """Check if the user has connected their Strava account.

        Args:
            user: User to check

        Returns:
            True if connected, False otherwise
        """
        return bool(user.strava_access_token)

    def refresh_token_if_needed(self, user: User) -> dict | None:
        """Refresh the Strava access token if it's expired.

        Args:
            user: User whose token to refresh

        Returns:
            Dictionary with new tokens if refreshed, None otherwise
        """
        expires_at = user.strava_token_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) > expires_at:
            self._logger.info("Strava token expired, refreshing...")
            response = _call_with_rate_limit_backoff(
                self._logger,
                lambda: StravaClientFactory.refresh_access_token(user.strava_refresh_token),
                "refresh Strava access token",
            )
            expires_at = datetime.fromtimestamp(response["expires_at"], tz=timezone.utc)
            user.strava_access_token = response["access_token"]
            user.strava_refresh_token = response["refresh_token"]
            user.strava_token_expires_at = expires_at
            self._logger.info("Token refreshed.")
            return {
                "access_token": user.strava_access_token,
                "refresh_token": user.strava_refresh_token,
                "expires_at": expires_at,
            }
        return None

    def fetch_activities(self, user: User, after: datetime | None = None) -> list[dict]:
        """Fetch activities from Strava API.

        Args:
            user: User whose activities to fetch
            after: Optional datetime to fetch activities after (for delta sync)

        Returns:
            List of activity dictionaries with standardized format matching
            the Strava API DetailedActivity model structure
        """
        token_expires = None
        if user.strava_token_expires_at:
            expires_at = user.strava_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            token_expires = int(expires_at.timestamp())

        client = StravaClientFactory.create_authenticated_client(
            user.strava_access_token,
            refresh_token=user.strava_refresh_token,
            token_expires=token_expires,
        )

        def fetch_activity_list():
            # Materialize the stravalib iterator inside the retry boundary because
            # paging requests are made during iteration, not when the iterator is built.
            if after:
                return list(client.get_activities(after=after))
            return list(client.get_activities())

        activities = _call_with_rate_limit_backoff(
            self._logger,
            fetch_activity_list,
            "fetch Strava activities",
        )
        self._logger.info("Fetched %s raw Strava activities.", len(activities))

        # Convert Strava activities to standardized format
        # Based on Strava API v3 DetailedActivity model:
        # https://developers.strava.com/docs/reference/#api-models-DetailedActivity
        standardized_activities = []
        missing_calorie_count = 0
        for index, activity in enumerate(activities, start=1):
            try:
                if index == 1 or index % 25 == 0 or index == len(activities):
                    self._logger.info("Normalizing Strava activity %s/%s.", index, len(activities))

                # Extract values, handling various object types from stravalib
                # The stravalib library may wrap primitives in custom objects

                # Distance: float in meters
                distance = activity.distance
                distance_num = getattr(distance, "num", None)
                distance_mag = getattr(distance, "magnitude", None)
                if isinstance(distance_num, Real):
                    distance = float(distance_num)
                elif isinstance(distance_mag, Real):
                    distance = float(distance_mag)
                elif isinstance(distance, Real):
                    distance = float(distance)
                else:
                    distance = float(distance) if distance is not None else 0.0

                # Elevation: float in meters
                elevation = activity.total_elevation_gain
                elev_num = getattr(elevation, "num", None)
                elev_mag = getattr(elevation, "magnitude", None)
                if isinstance(elev_num, Real):
                    elevation = float(elev_num)
                elif isinstance(elev_mag, Real):
                    elevation = float(elev_mag)
                elif isinstance(elevation, Real):
                    elevation = float(elevation)
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

                # Start date: datetime (UTC timezone)
                start_date = activity.start_date
                # stravalib returns datetime objects, ensure it's timezone-aware
                if start_date and start_date.tzinfo is None:
                    start_date = start_date.replace(tzinfo=timezone.utc)

                calories = _extract_float(getattr(activity, "calories", None))
                if calories is None:
                    missing_calorie_count += 1

                activity_type = _extract_activity_type(activity)

                standardized_activities.append(
                    {
                        "id": int(activity.id),
                        "name": str(activity.name),
                        "distance": distance,
                        "moving_time": moving_time,
                        "elapsed_time": elapsed_time,
                        "total_elevation_gain": elevation,
                        "calories": calories,
                        "activity_type": activity_type,
                        "start_date": start_date,
                    }
                )
            except Exception:
                # Log error but continue processing other activities
                self._logger.exception(
                    "Error processing activity %s", getattr(activity, "id", "unknown")
                )
                continue

        self._logger.info(
            "Normalized %s/%s Strava activities. Missing calories: %s.",
            len(standardized_activities),
            len(activities),
            missing_calorie_count,
        )
        return standardized_activities

    def fetch_activity_calories_batch(
        self, user: User, activity_ids: list[int]
    ) -> dict[int, float]:
        """Fetch detailed calories for selected Strava activities."""
        token_expires = None
        if user.strava_token_expires_at:
            expires_at = user.strava_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            token_expires = int(expires_at.timestamp())

        client = StravaClientFactory.create_authenticated_client(
            user.strava_access_token,
            refresh_token=user.strava_refresh_token,
            token_expires=token_expires,
        )

        calories_by_activity_id = {}
        for activity_id in activity_ids:
            calories = self._fetch_activity_calories(client, activity_id)
            if calories is not None:
                calories_by_activity_id[int(activity_id)] = calories
        return calories_by_activity_id

    def fetch_activity_types_batch(self, user: User, activity_ids: list[int]) -> dict[int, str]:
        """Fetch activity types from the listing endpoint for missing activities.

        This is far more efficient than calling ``get_activity()`` per activity
        because the list endpoint bundles up to 200 per page and already
        returns ``sport_type`` / ``type`` on every ``SummaryActivity``.
        """
        token_expires = None
        if user.strava_token_expires_at:
            expires_at = user.strava_token_expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            token_expires = int(expires_at.timestamp())

        client = StravaClientFactory.create_authenticated_client(
            user.strava_access_token,
            refresh_token=user.strava_refresh_token,
            token_expires=token_expires,
        )

        wanted = set(int(aid) for aid in activity_ids)
        found: dict[int, str] = {}

        # fetch all pages via the stravalib iterator
        all_activities = _call_with_rate_limit_backoff(
            self._logger,
            lambda: list(client.get_activities()),
            "fetch all Strava activities for type backfill",
        )

        for act in all_activities:
            aid = int(act.id)
            if aid in wanted:
                atype = _extract_activity_type(act)
                if atype:
                    found[aid] = atype
                    wanted.discard(aid)
                    if not wanted:
                        break

        if wanted:
            self._logger.warning(
                "Could not fetch types for %s activities (not returned by list endpoint).",
                len(wanted),
            )

        return found

    def _fetch_activity_calories(self, client, activity_id: int) -> float | None:
        """Fetch detailed Strava activity calories when summary data lacks them."""
        get_activity = getattr(client, "get_activity", None)
        if not callable(get_activity):
            return None

        try:
            detailed_activity = _call_with_rate_limit_backoff(
                self._logger,
                lambda: get_activity(activity_id),
                f"fetch Strava activity detail {activity_id}",
            )
        except Exception:
            self._logger.exception("Failed to fetch Strava activity detail %s", activity_id)
            return None

        return _extract_float(getattr(detailed_activity, "calories", None))

    def _fetch_activity_type(self, client, activity_id: int) -> str | None:
        """Fetch detailed Strava activity type when summary data lacks it."""
        get_activity = getattr(client, "get_activity", None)
        if not callable(get_activity):
            return None

        try:
            detailed_activity = _call_with_rate_limit_backoff(
                self._logger,
                lambda: get_activity(activity_id),
                f"fetch Strava activity detail {activity_id}",
            )
        except Exception:
            self._logger.exception("Failed to fetch Strava activity detail %s", activity_id)
            return None

        return _extract_activity_type(detailed_activity)


def _extract_float(value) -> float | None:
    """Normalize primitive and quantity-like values to float."""
    value_num = getattr(value, "num", None)
    value_mag = getattr(value, "magnitude", None)

    if isinstance(value_num, Real):
        return float(value_num)
    if isinstance(value_mag, Real):
        return float(value_mag)
    if isinstance(value, Real):
        return float(value)
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_activity_type(activity) -> str | None:
    """Normalize Strava activity type preferring sport_type over legacy type."""
    sport_type = getattr(activity, "sport_type", None)
    resolved_sport_type = _normalize_activity_type_value(sport_type)
    if resolved_sport_type:
        return resolved_sport_type

    legacy_type = getattr(activity, "type", None)
    resolved_legacy_type = _normalize_activity_type_value(legacy_type)
    if resolved_legacy_type:
        return resolved_legacy_type

    return None


def _normalize_activity_type_value(value) -> str | None:
    """Normalize Strava activity type across enum/string/pydantic wrappers."""
    if value is None:
        return None

    if isinstance(value, str) and value:
        return value

    enum_value = getattr(value, "value", None)
    if isinstance(enum_value, str) and enum_value:
        return enum_value

    root_value = getattr(value, "root", None)
    if isinstance(root_value, str) and root_value:
        return root_value

    model_dump = getattr(value, "model_dump", None)
    if callable(model_dump):
        try:
            dumped = model_dump()
        except Exception:
            return None

        if isinstance(dumped, str) and dumped:
            return dumped

        if isinstance(dumped, dict):
            dumped_root = dumped.get("root")
            if isinstance(dumped_root, str) and dumped_root:
                return dumped_root

    return None


def _call_with_rate_limit_backoff(logger, operation, description: str):
    """Retry a Strava API operation with exponential backoff on rate limits."""
    total_attempts = _RATE_LIMIT_MAX_RETRIES + 1
    for attempt in range(_RATE_LIMIT_MAX_RETRIES + 1):
        try:
            return operation()
        except Exception as exc:
            if not _is_rate_limit_error(exc) or attempt == _RATE_LIMIT_MAX_RETRIES:
                raise

            delay_seconds = _rate_limit_delay_seconds(exc, attempt)
            retry_number = attempt + 1
            next_attempt = attempt + 2
            logger.warning(
                "Strava rate limit while trying to %s: %s. Retry %s/%s will wait "
                "%s seconds before next attempt %s/%s.",
                description,
                _rate_limit_error_message(exc),
                retry_number,
                _RATE_LIMIT_MAX_RETRIES,
                delay_seconds,
                next_attempt,
                total_attempts,
            )
            time.sleep(delay_seconds)

    raise RuntimeError(f"Strava API operation did not complete: {description}")


def _is_rate_limit_error(exc: Exception) -> bool:
    """Return True for explicit or message-only Strava rate limit failures."""
    if isinstance(exc, (RateLimitExceeded, RateLimitTimeout)):
        return True

    message = str(exc).lower()
    return "rate limit" in message or "too many requests" in message


def _rate_limit_error_message(exc: Exception) -> str:
    """Return a useful message for rate limit exceptions that stringify empty."""
    message = str(exc)
    if message:
        return message

    for arg in getattr(exc, "args", ()):  # stravalib can omit args from __str__.
        if arg:
            return str(arg)

    if isinstance(exc, RateLimitTimeout):
        return "Strava API rate limit timeout"
    if isinstance(exc, RateLimitExceeded):
        return "Strava API rate limit exceeded"

    return exc.__class__.__name__


def _rate_limit_delay_seconds(exc: Exception, attempt: int) -> int:
    """Calculate bounded exponential delay, honoring stravalib timeout if present."""
    timeout = getattr(exc, "timeout", None)
    if isinstance(timeout, Real) and timeout > 0:
        return int(min(timeout, _RATE_LIMIT_MAX_DELAY_SECONDS))

    return min(
        _RATE_LIMIT_BASE_DELAY_SECONDS * (2**attempt),
        _RATE_LIMIT_MAX_DELAY_SECONDS,
    )
