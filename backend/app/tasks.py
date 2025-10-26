"""Background tasks for asynchronous processing.

This module contains Celery tasks for long-running operations
such as syncing activities from external services.
"""

import random
import time
from datetime import datetime, timezone

import models
from celery_app import celery
from database import SessionLocal
from repositories import ActivityRepository, UserRepository
from services import ActivityService
from strategies import ActivitySyncContext, StravaActivitySyncStrategy


@celery.task
def create_dummy_activity_task(user_id: int):
    """Create a dummy activity for testing the background task pipeline.

    This task simulates a long-running process (5 seconds) and then creates
    a fake cycling activity for the specified user.

    Args:
        user_id: The ID of the user to create the activity for

    Returns:
        dict: Status information with 'status' and 'user_id' keys
    """
    print(f"Starting dummy activity sync for user_id: {user_id}")
    time.sleep(5)  # Simulate a 5-second API call

    # Each task is a separate process, so it needs its own DB session
    db = SessionLocal()
    try:
        owner = db.query(models.User).filter(models.User.id == user_id).first()
        if not owner:
            print(f"User with id {user_id} not found.")
            return {"status": "error", "message": f"User {user_id} not found"}

        # Create a new dummy activity
        new_activity = models.Activity(
            name=f"Dummy Activity {random.randint(1, 1000)}",
            distance=random.uniform(10000, 50000),
            moving_time=random.randint(3600, 7200),
            elapsed_time=random.randint(7200, 9000),
            total_elevation_gain=random.uniform(100, 1000),
            owner_id=user_id,
        )
        db.add(new_activity)
        db.commit()
        print(f"Successfully created dummy activity for user_id: {user_id}")
    finally:
        db.close()

    return {"status": "complete", "user_id": user_id}


@celery.task
def sync_strava_activities_task(user_id: int):
    """Sync activities from Strava API for a given user.

    This task uses the Strategy pattern to fetch activities from Strava
    and the Repository/Service patterns to save them to the database.

    Args:
        user_id: The ID of the user to sync activities for

    Returns:
        dict: Status information
    """
    print(f"Starting Strava sync for user_id: {user_id}")
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

        # Use Strategy pattern for syncing
        sync_strategy = StravaActivitySyncStrategy()
        sync_context = ActivitySyncContext(sync_strategy)

        # Execute sync
        is_connected, activities_data, token_update = sync_context.sync_activities(user)

        if not is_connected:
            print(f"User {user_id} not connected to Strava.")
            return {"status": "error", "message": "User not connected to Strava"}

        # Update tokens if refreshed
        if token_update:
            user.strava_access_token = token_update["access_token"]
            user.strava_refresh_token = token_update["refresh_token"]
            user.strava_token_expires_at = token_update["expires_at"]
            user_repo.update(user)

        # Import activities using service layer
        activity_count = activity_service.import_activities(activities_data, user_id)

        print(
            f"Strava sync completed for user_id: {user_id}. Added {activity_count} new activities."
        )
        return {"status": "complete", "user_id": user_id, "activities_added": activity_count}

    except Exception as e:
        print(f"Error during Strava sync for user_id {user_id}: {str(e)}")
        return {"status": "error", "message": str(e)}
    finally:
        db.close()
