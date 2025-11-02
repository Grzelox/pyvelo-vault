"""Celery tasks for Strava activity synchronization.

This module contains background tasks for syncing activities from Strava.
"""

from datetime import datetime, timezone

from app.core.database import SessionLocal
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService

from .strategies import ActivitySyncContext, StravaActivitySyncStrategy


def sync_single_user_strava_activities_task(user_id: int):
    """Sync ONLY NEW activities from Strava API for a given user (delta sync).

    This task uses the Strategy pattern to fetch activities from Strava
    and the Repository/Service patterns to save them to the database.
    It implements delta sync by only fetching activities after the last sync.

    Args:
        user_id: The ID of the user to sync activities for

    Returns:
        dict: Status information
    """
    print(f"Starting Strava delta sync for user_id: {user_id}")
    db = SessionLocal()

    try:
        # Initialize repositories and services
        user_repo = UserRepository(db)
        activity_repo = ActivityRepository(db)
        activity_service = ActivityService(activity_repo)

        # Get user
        user = user_repo.get_by_id(user_id)
        if not user:
            print(f"User {user_id} not found.")
            return {"status": "error", "message": "User not found"}

        # Determine the sync start date (delta sync)
        sync_after_date = user.last_strava_sync or datetime(2000, 1, 1, tzinfo=timezone.utc)
        print(f"Fetching activities for user {user.id} after {sync_after_date}")

        # Use Strategy pattern for syncing
        sync_strategy = StravaActivitySyncStrategy()
        sync_context = ActivitySyncContext(sync_strategy)

        # Execute sync with delta sync parameter
        is_connected, activities_data, token_update = sync_context.sync_activities(
            user, after=sync_after_date
        )

        if not is_connected:
            print(f"User {user_id} not connected to Strava.")
            return {"status": "error", "message": "User not connected to Strava"}

        # Update tokens if refreshed
        if token_update:
            user.strava_access_token = token_update["access_token"]
            user.strava_refresh_token = token_update["refresh_token"]
            user.strava_token_expires_at = token_update["expires_at"]

        # Import activities using service layer
        activity_count = activity_service.import_activities(activities_data, user_id)

        # Update the last sync timestamp
        user.last_strava_sync = datetime.now(timezone.utc)
        user_repo.update(user)

        print(
            f"Strava sync completed for user_id: {user_id}. Added {activity_count} new activities."
        )
        return {
            "status": "complete",
            "user_id": user_id,
            "activities_added": activity_count,
        }

    except Exception as e:
        print(f"Error during Strava sync for user_id {user_id}: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()


def schedule_all_user_syncs_task():
    """Dispatcher task scheduled by Celery Beat.

    Finds all users who have connected their Strava account and dispatches
    individual sync tasks for each one.

    Returns:
        dict: Status information
    """
    print("Scheduler running: Dispatching sync tasks for all users.")
    db = SessionLocal()

    try:
        # Find all users who have connected their Strava account
        user_repo = UserRepository(db)
        users_to_sync = (
            db.query(user_repo.model).filter(user_repo.model.strava_access_token.isnot(None)).all()
        )

        dispatched_count = 0
        for user in users_to_sync:
            print(f"Dispatching sync for user_id: {user.id}")
            # Import the celery task from worker module to dispatch it
            from app.worker import sync_single_user_strava_activities_task as task

            task.delay(user.id)
            dispatched_count += 1

        print(f"Dispatched {dispatched_count} sync tasks.")
        return {
            "status": "complete",
            "dispatched_count": dispatched_count,
        }

    except Exception as e:
        print(f"Error during sync dispatch: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
