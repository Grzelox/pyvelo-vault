"""Garmin activity sync strategy (python-garminconnect)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.core import get_logger
from app.integrations.activity_sync import ActivitySyncStrategy
from app.models import User

from .client import GarminClientFactory


class GarminActivitySyncStrategy(ActivitySyncStrategy):
    """Strategy for syncing activities from Garmin Connect Activity API."""

    def __init__(self) -> None:
        self._logger = get_logger(__name__)

    def is_connected(self, user: User) -> bool:
        return bool(user.garmin_access_token)

    def refresh_token_if_needed(self, user: User) -> dict | None:
        return None

    def fetch_activities(self, user: User, after: datetime | None = None) -> list[dict]:
        try:
            api = GarminClientFactory.login_with_tokenstore(user.garmin_access_token)
        except Exception:
            self._logger.exception("Garmin login failed (invalid/missing tokenstore).")
            return []

        if after and after.tzinfo is None:
            after = after.replace(tzinfo=timezone.utc)

        start_date = (after or datetime(2000, 1, 1, tzinfo=timezone.utc)).date().isoformat()
        end_date = datetime.now(timezone.utc).date().isoformat()

        try:
            raw_activities = api.get_activities_by_date(start_date, end_date)
        except Exception:
            self._logger.exception("Garmin activities fetch failed.")
            return []

        if not isinstance(raw_activities, list):
            return []

        standardized: list[dict[str, Any]] = []
        for raw in raw_activities:
            if not isinstance(raw, dict):
                continue
            normalized = _normalize_garmin_activity(raw)
            if normalized:
                standardized.append(normalized)
        return standardized


def _normalize_garmin_activity(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Best-effort normalization for common Garmin field names."""
    try:
        activity_id = raw.get("activityId") or raw.get("id")
        if activity_id is None:
            return None
        activity_id = int(activity_id)

        name = raw.get("activityName") or raw.get("name") or "Garmin Activity"

        distance = raw.get("distance") or raw.get("distanceInMeters") or 0.0
        distance = float(distance)

        moving_time = raw.get("movingDuration") or raw.get("movingTime") or raw.get("duration") or 0
        moving_time = int(moving_time)

        elapsed_time = raw.get("elapsedDuration") or raw.get("elapsedTime") or moving_time
        elapsed_time = int(elapsed_time)

        elevation = (
            raw.get("elevationGain")
            or raw.get("totalElevationGain")
            or raw.get("elevationGainInMeters")
            or 0.0
        )
        elevation = float(elevation)

        start_date = (
            raw.get("startTimeGMT")
            or raw.get("startTime")
            or raw.get("start_date")
            or raw.get("startDate")
        )
        if isinstance(start_date, (int, float)):
            start_date_dt = datetime.fromtimestamp(int(start_date), tz=timezone.utc)
        elif isinstance(start_date, str):
            try:
                start_date_dt = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
                if start_date_dt.tzinfo is None:
                    start_date_dt = start_date_dt.replace(tzinfo=timezone.utc)
            except Exception:
                start_date_dt = None
        elif isinstance(start_date, datetime):
            start_date_dt = start_date
            if start_date_dt.tzinfo is None:
                start_date_dt = start_date_dt.replace(tzinfo=timezone.utc)
        else:
            start_date_dt = None

        return {
            "id": activity_id,
            "name": str(name),
            "distance": distance,
            "moving_time": moving_time,
            "elapsed_time": elapsed_time,
            "total_elevation_gain": elevation,
            "start_date": start_date_dt,
        }
    except Exception:
        return None
