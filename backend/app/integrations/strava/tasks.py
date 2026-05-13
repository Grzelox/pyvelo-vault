"""Celery tasks for Strava activity synchronization.

This module contains background tasks for syncing activities from Strava.
Dependencies are injected via dependency-injector container.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.container import Container
from app.core import get_logger
from app.models import User
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService
from dependency_injector.wiring import Provide, inject

from .strategies import StravaActivitySyncStrategy

logger = get_logger(__name__)

_CALORIE_BACKFILL_BATCH_SIZE = 10
_CALORIE_BACKFILL_BATCH_DELAY_SECONDS = 60
_ACTIVITY_TYPE_BACKFILL_BATCH_SIZE = 10
_ACTIVITY_TYPE_BACKFILL_BATCH_DELAY_SECONDS = 60


@inject
def sync_single_user_strava_activities_task(
    user_id: int,
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
    activity_repository: type[ActivityRepository] = Provide[Container.activity_repository.provider],
    activity_service: type[ActivityService] = Provide[Container.activity_service.provider],
):
    """Sync ONLY NEW activities from Strava API for a given user (delta sync).

    This task uses the Strategy pattern to fetch activities from Strava
    and the Repository/Service patterns to save them to the database.
    It implements delta sync by fetching activities from the date of
    the latest activity already stored for the user.

    Dependencies are injected via the DI container:
    - db_session: Database session Resource (auto-managed lifecycle)
    - Repositories and services are injected as factory providers

    Args:
        user_id: The ID of the user to sync activities for

    Returns:
        dict: Status information
    """
    logger.info("Starting Strava delta sync for user_id=%s", user_id)

    try:
        with db_session as session:
            logger.info("Strava sync user_id=%s: initializing repositories.", user_id)
            # Initialize repositories and services with injected session
            user_repo = user_repository(db=session)
            activity_repo = activity_repository(db=session)
            act_service = activity_service(activity_repo=activity_repo)

            # Get user
            logger.info("Strava sync user_id=%s: loading user.", user_id)
            user = user_repo.get_by_id(user_id)
            if not user:
                logger.warning("User %s not found during Strava sync.", user_id)
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
                "Fetching activities for user_id=%s from local latest activity date %s",
                user.id,
                sync_after_date.date().isoformat(),
            )

            sync_strategy = StravaActivitySyncStrategy()
            logger.info("Strava sync user_id=%s: checking Strava connection.", user_id)
            if not sync_strategy.is_connected(user):
                logger.warning("User %s not connected to Strava.", user_id)
                return {"status": "error", "message": "User not connected to Strava"}

            logger.info("Strava sync user_id=%s: checking access token freshness.", user_id)
            token_update = sync_strategy.refresh_token_if_needed(user)
            if token_update:
                logger.info("Strava sync user_id=%s: persisting refreshed token.", user_id)
                user_repo.update(user)
            else:
                logger.info("Strava sync user_id=%s: access token still valid.", user_id)

            logger.info("Strava sync user_id=%s: fetching activities from Strava.", user_id)
            activities_data = sync_strategy.fetch_activities(user, after=sync_after_date)
            logger.info(
                "Strava sync user_id=%s: fetched %s normalized activities.",
                user_id,
                len(activities_data),
            )

            logger.info(
                "Strava sync user_id=%s: importing %s activities into database.",
                user_id,
                len(activities_data),
            )
            activity_count = act_service.import_activities(activities_data, user_id)
            logger.info(
                "Strava sync user_id=%s: imported %s new activities.",
                user_id,
                activity_count,
            )

            user.last_strava_sync = datetime.now(timezone.utc)
            logger.info(
                "Strava sync user_id=%s: updating last_strava_sync to %s.",
                user_id,
                user.last_strava_sync,
            )
            user_repo.update(user)

            strava_activity_ids = [int(activity["id"]) for activity in activities_data]
            missing_calorie_activities = act_service.get_activities_missing_calories(
                user_id,
                activity_ids=strava_activity_ids,
            )
            backfill_tasks_dispatched = _dispatch_calorie_backfill_tasks(
                user_id,
                [activity.id for activity in missing_calorie_activities],
            )

            missing_type_activities = act_service.get_activities_missing_activity_type(
                user_id,
                activity_ids=strava_activity_ids,
            )
            activity_type_backfill_tasks_dispatched = _dispatch_activity_type_backfill_tasks(
                user_id,
                [activity.id for activity in missing_type_activities],
            )

            logger.info(
                "Strava sync completed for user_id=%s. Added %s new activities. "
                "Dispatched %s calorie backfill tasks and %s activity type backfill tasks.",
                user_id,
                activity_count,
                backfill_tasks_dispatched,
                activity_type_backfill_tasks_dispatched,
            )
            return {
                "status": "complete",
                "user_id": user_id,
                "activities_added": activity_count,
                "calorie_backfill_tasks": backfill_tasks_dispatched,
                "activity_type_backfill_tasks": activity_type_backfill_tasks_dispatched,
            }

    except Exception as e:
        logger.exception("Error during Strava sync for user_id=%s", user_id)
        return {"status": "error", "message": str(e)}


@inject
def fill_missing_strava_activity_calories_task(
    user_id: int,
    activity_ids: list[int],
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
    activity_repository: type[ActivityRepository] = Provide[Container.activity_repository.provider],
    activity_service: type[ActivityService] = Provide[Container.activity_service.provider],
):
    """Fill missing calories for up to one batch of Strava activities."""
    batch_activity_ids = [int(activity_id) for activity_id in activity_ids][
        :_CALORIE_BACKFILL_BATCH_SIZE
    ]
    logger.info(
        "Starting Strava calorie backfill for user_id=%s, activity_ids=%s.",
        user_id,
        batch_activity_ids,
    )

    try:
        with db_session as session:
            user_repo = user_repository(db=session)
            activity_repo = activity_repository(db=session)
            act_service = activity_service(activity_repo=activity_repo)

            user = user_repo.get_by_id(user_id)
            if not user:
                logger.warning("User %s not found during Strava calorie backfill.", user_id)
                return {"status": "error", "message": "User not found"}

            sync_strategy = StravaActivitySyncStrategy()
            if not sync_strategy.is_connected(user):
                logger.warning("User %s not connected to Strava during calorie backfill.", user_id)
                return {"status": "error", "message": "User not connected to Strava"}

            token_update = sync_strategy.refresh_token_if_needed(user)
            if token_update:
                user_repo.update(user)

            missing_activities = act_service.get_activities_missing_calories(
                user_id,
                activity_ids=batch_activity_ids,
            )
            missing_activity_ids = [activity.id for activity in missing_activities]
            calories_by_activity_id = sync_strategy.fetch_activity_calories_batch(
                user,
                missing_activity_ids,
            )

            updated_count = 0
            for activity_id, calories in calories_by_activity_id.items():
                if act_service.update_activity_calories(activity_id, user_id, calories):
                    updated_count += 1

            logger.info(
                "Strava calorie backfill completed for user_id=%s. Updated %s/%s activities.",
                user_id,
                updated_count,
                len(missing_activity_ids),
            )
            return {
                "status": "complete",
                "user_id": user_id,
                "activities_updated": updated_count,
            }

    except Exception as e:
        logger.exception("Error during Strava calorie backfill for user_id=%s", user_id)
        return {"status": "error", "message": str(e)}


@inject
def fill_missing_strava_activity_type_task(
    user_id: int,
    activity_ids: list[int],
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
    activity_repository: type[ActivityRepository] = Provide[Container.activity_repository.provider],
    activity_service: type[ActivityService] = Provide[Container.activity_service.provider],
):
    """Fill missing activity types for up to one batch of Strava activities."""
    batch_activity_ids = [int(activity_id) for activity_id in activity_ids][
        :_ACTIVITY_TYPE_BACKFILL_BATCH_SIZE
    ]
    logger.info(
        "Starting Strava activity type backfill for user_id=%s, activity_ids=%s.",
        user_id,
        batch_activity_ids,
    )

    try:
        with db_session as session:
            user_repo = user_repository(db=session)
            activity_repo = activity_repository(db=session)
            act_service = activity_service(activity_repo=activity_repo)

            user = user_repo.get_by_id(user_id)
            if not user:
                logger.warning("User %s not found during Strava activity type backfill.", user_id)
                return {"status": "error", "message": "User not found"}

            sync_strategy = StravaActivitySyncStrategy()
            if not sync_strategy.is_connected(user):
                logger.warning(
                    "User %s not connected to Strava during activity type backfill.", user_id
                )
                return {"status": "error", "message": "User not connected to Strava"}

            token_update = sync_strategy.refresh_token_if_needed(user)
            if token_update:
                user_repo.update(user)

            missing_activities = act_service.get_activities_missing_activity_type(
                user_id,
                activity_ids=batch_activity_ids,
            )
            missing_activity_ids = [activity.id for activity in missing_activities]
            activity_type_by_activity_id = sync_strategy.fetch_activity_types_batch(
                user,
                missing_activity_ids,
            )

            updated_count = 0
            for activity_id, activity_type in activity_type_by_activity_id.items():
                if act_service.update_activity_type(activity_id, user_id, activity_type):
                    updated_count += 1

            logger.info(
                "Strava activity type backfill completed for user_id=%s. Updated %s/%s activities.",
                user_id,
                updated_count,
                len(missing_activity_ids),
            )
            return {
                "status": "complete",
                "user_id": user_id,
                "activities_updated": updated_count,
            }

    except Exception as e:
        logger.exception("Error during Strava activity type backfill for user_id=%s", user_id)
        return {"status": "error", "message": str(e)}


@inject
def schedule_all_user_syncs_task(
    db_session=Provide[Container.db_session],
    user_repository: type[UserRepository] = Provide[Container.user_repository.provider],
):
    """Dispatcher task scheduled by Celery Beat.

    Finds all users who have connected their Strava account and dispatches
    individual sync tasks for each one.

    Returns:
        dict: Status information
    """
    logger.info("Scheduler running: dispatching sync tasks for all users.")

    try:
        with db_session as session:
            users_to_sync = session.query(User).filter(User.strava_access_token.isnot(None)).all()

            dispatched_count = 0
            for user in users_to_sync:
                logger.info("Dispatching Strava sync for user_id=%s", user.id)
                # Import the celery task from worker module to dispatch it
                from app.worker import sync_single_user_strava_activities_task as task

                task.delay(user.id)
                dispatched_count += 1

            logger.info("Dispatched %s sync tasks.", dispatched_count)
            return {
                "status": "complete",
                "dispatched_count": dispatched_count,
            }

    except Exception as e:
        logger.exception("Error during sync dispatch.")
        return {"status": "error", "message": str(e)}


def _dispatch_calorie_backfill_tasks(user_id: int, activity_ids: list[int]) -> int:
    """Dispatch missing-calorie backfill tasks in small staggered batches."""
    if not activity_ids:
        return 0

    from app.worker import fill_missing_strava_activity_calories_task as task

    dispatched_count = 0
    for batch_index, batch in enumerate(_chunked(activity_ids, _CALORIE_BACKFILL_BATCH_SIZE)):
        task.apply_async(
            args=(user_id, batch),
            countdown=batch_index * _CALORIE_BACKFILL_BATCH_DELAY_SECONDS,
        )
        dispatched_count += 1
    return dispatched_count


def _dispatch_activity_type_backfill_tasks(user_id: int, activity_ids: list[int]) -> int:
    """Dispatch missing-activity-type backfill tasks in small staggered batches."""
    if not activity_ids:
        return 0

    from app.worker import fill_missing_strava_activity_type_task as task

    dispatched_count = 0
    for batch_index, batch in enumerate(_chunked(activity_ids, _ACTIVITY_TYPE_BACKFILL_BATCH_SIZE)):
        task.apply_async(
            args=(user_id, batch),
            countdown=batch_index * _ACTIVITY_TYPE_BACKFILL_BATCH_DELAY_SECONDS,
        )
        dispatched_count += 1
    return dispatched_count


def _chunked(items: list[int], size: int) -> list[list[int]]:
    """Split a list into fixed-size chunks."""
    return [items[index : index + size] for index in range(0, len(items), size)]
