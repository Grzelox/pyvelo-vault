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
    It implements delta sync by only fetching activities after the last sync.

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

            # Determine the sync start date (delta sync)
            sync_after_date = user.last_strava_sync or datetime(2000, 1, 1, tzinfo=timezone.utc)
            logger.info("Fetching activities for user_id=%s after %s", user.id, sync_after_date)

            sync_strategy = StravaActivitySyncStrategy()
            logger.info("Strava sync user_id=%s: checking Strava connection.", user_id)
            if not sync_strategy.is_connected(user):
                logger.warning("User %s not connected to Strava.", user_id)
                return {"status": "error", "message": "User not connected to Strava"}

            logger.info("Strava sync user_id=%s: checking access token freshness.", user_id)
            token_update = sync_strategy.refresh_token_if_needed(user)
            if token_update:
                # Strava refresh tokens rotate. Persist immediately so a later
                # activity-fetch failure does not leave us with an invalid token.
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

            # Import activities using service layer
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

            # Update the last sync timestamp
            user.last_strava_sync = datetime.now(timezone.utc)
            logger.info(
                "Strava sync user_id=%s: updating last_strava_sync to %s.",
                user_id,
                user.last_strava_sync,
            )
            user_repo.update(user)

            logger.info(
                "Strava sync completed for user_id=%s. Added %s new activities.",
                user_id,
                activity_count,
            )
            return {
                "status": "complete",
                "user_id": user_id,
                "activities_added": activity_count,
            }

    except Exception as e:
        logger.exception("Error during Strava sync for user_id=%s", user_id)
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
