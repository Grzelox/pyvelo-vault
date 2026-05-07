"""Celery application instance and task registration.

This module creates and configures the Celery instance used for
background task processing. It's separated from main.py to avoid
circular import issues.

The dependency-injector container is wired here for Celery tasks.
"""

from app.container import container
from app.core.config import settings
from celery import Celery

# Create Celery instance
celery = Celery(__name__, broker=settings.CELERY_BROKER_URL, backend=settings.CELERY_RESULT_BACKEND)

celery.conf.update(
    task_track_started=True,
)

# Configure Celery Beat schedule
celery.conf.beat_schedule = {
    "sync-all-users-every-hour": {
        "task": "app.worker.schedule_all_user_syncs_task",
        "schedule": 3600.0,  # Run every hour (in seconds)
    },
}

# Wire the DI container for Celery tasks
# This enables @inject decorators in task modules
container.wire(
    modules=[
        "app.integrations.strava.tasks",
        "app.integrations.garmin.tasks",
    ]
)


# Register tasks
@celery.task
def sync_single_user_strava_activities_task(user_id: int):
    """Celery task wrapper for Strava activity sync (delta sync).

    Args:
        user_id: The ID of the user to sync activities for

    Returns:
        dict: Status information
    """
    from app.integrations.strava.tasks import sync_single_user_strava_activities_task as sync_func

    return sync_func(user_id)


@celery.task
def fill_missing_strava_activity_calories_task(user_id: int, activity_ids: list[int]):
    """Celery task wrapper for Strava calorie backfill."""
    from app.integrations.strava.tasks import (
        fill_missing_strava_activity_calories_task as fill_func,
    )

    return fill_func(user_id, activity_ids)


@celery.task
def sync_single_user_garmin_activities_task(user_id: int):
    """Celery task wrapper for Garmin activity sync (delta sync)."""
    from app.integrations.garmin.tasks import sync_single_user_garmin_activities_task as sync_func

    return sync_func(user_id)


@celery.task
def schedule_all_user_syncs_task():
    """Celery task wrapper for dispatching sync tasks for all users.

    Returns:
        dict: Status information
    """
    from app.integrations.garmin.tasks import schedule_all_user_garmin_syncs_task as garmin_dispatch
    from app.integrations.strava.tasks import schedule_all_user_syncs_task as strava_dispatch

    strava_result = strava_dispatch()
    garmin_result = garmin_dispatch()
    return {"strava": strava_result, "garmin": garmin_result}
