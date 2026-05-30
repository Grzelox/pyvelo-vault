"""Celery-friendly tasks for Garmin activity synchronization.

Dependencies are injected via dependency-injector container.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.container import Container
from app.core import get_logger
from app.integrations.activity_sync import ActivitySyncContext
from app.models import User
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService, UserService
from dependency_injector.wiring import Provide, inject

from .strategies import GarminActivitySyncStrategy

logger = get_logger(__name__)


@inject
def sync_single_user_garmin_activities_task(
    user_id: int,
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
    activity_repository: type[ActivityRepository] = Provide[Container.activity_repository.provider],
    activity_service: type[ActivityService] = Provide[Container.activity_service.provider],
):
    """Sync ONLY NEW activities from Garmin API for a given user (delta sync).

    Dependencies are injected via the DI container.
    """
    logger.info("Starting Garmin delta sync for user_id=%s", user_id)

    try:
        with db_session as session:
            user_repo = user_repository(db=session)
            activity_repo = activity_repository(db=session)
            act_service = activity_service(activity_repo=activity_repo)
            user_service = UserService(user_repo)

            user = user_repo.get_by_id(user_id)
            if not user:
                logger.warning("User %s not found during Garmin sync.", user_id)
                return {"status": "error", "message": "User not found"}

            latest_activity_start = activity_repo.get_latest_activity_start_date(user.id)
            if latest_activity_start:
                sync_after_date = datetime.combine(
                    latest_activity_start.date(),
                    datetime.min.time(),
                    tzinfo=timezone.utc,
                )
            else:
                sync_after_date = datetime(2000, 1, 1, tzinfo=timezone.utc)
            logger.info(
                "Fetching Garmin activities for user_id=%s from local latest activity date %s",
                user.id,
                sync_after_date.date().isoformat(),
            )

            sync_strategy = GarminActivitySyncStrategy()
            sync_context = ActivitySyncContext(sync_strategy)

            is_connected, activities_data, token_update = sync_context.sync_activities(
                user, after=sync_after_date
            )
            if not is_connected:
                logger.warning("User %s not connected to Garmin.", user_id)
                user_service.record_sync_status(user, source="Garmin", status="failed")
                return {"status": "error", "message": "User not connected to Garmin"}

            try:
                if token_update:
                    user.garmin_access_token = (
                        token_update.get("access_token") or user.garmin_access_token
                    )
                    user.garmin_refresh_token = (
                        token_update.get("refresh_token") or user.garmin_refresh_token
                    )
                    if token_update.get("expires_at"):
                        user.garmin_token_expires_at = token_update["expires_at"]

                activity_count = act_service.import_activities(activities_data, user_id)

                user_service.record_sync_status(user, source="Garmin", status="success")
            except Exception:
                user_service.record_sync_status(user, source="Garmin", status="failed")
                raise

            logger.info(
                "Garmin sync completed for user_id=%s. Added %s new activities.",
                user_id,
                activity_count,
            )
            return {
                "status": "complete",
                "user_id": user_id,
                "activities_added": activity_count,
            }

    except Exception as e:
        logger.exception("Error during Garmin sync for user_id=%s", user_id)
        return {"status": "error", "message": str(e)}


@inject
def schedule_all_user_garmin_syncs_task(
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
):
    """Dispatcher task to schedule Garmin syncs for all connected users."""
    logger.info("Scheduler running: dispatching Garmin sync tasks for all users.")

    try:
        with db_session as session:
            users_to_sync = session.query(User).filter(User.garmin_access_token.isnot(None)).all()

            dispatched_count = 0
            for user in users_to_sync:
                logger.info("Dispatching Garmin sync for user_id=%s", user.id)
                from app.worker import sync_single_user_garmin_activities_task as task

                task.delay(user.id)
                dispatched_count += 1

            logger.info("Dispatched %s Garmin sync tasks.", dispatched_count)
            return {"status": "complete", "dispatched_count": dispatched_count}

    except Exception as e:
        logger.exception("Error during Garmin sync dispatch.")
        return {"status": "error", "message": str(e)}
