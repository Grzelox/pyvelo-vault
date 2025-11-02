"""Activity endpoints."""

from typing import List

from app.core import get_current_user, get_db
from app.models import User
from app.repositories import ActivityRepository
from app.schemas import Activity, ActivityCreate
from app.services import ActivityService
from app.worker import sync_single_user_strava_activities_task
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("", response_model=List[Activity])
def get_activities(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Retrieve all activities for the current user.

    Returns a list of all cycling activities belonging to the authenticated user.
    Uses Repository and Service patterns for data access.

    Args:
        current_user: Current authenticated user (injected dependency)
        db: Database session (injected dependency)

    Returns:
        List[Activity]: List of user's activities
    """
    # Use repository and service patterns
    activity_repo = ActivityRepository(db)
    activity_service = ActivityService(activity_repo)

    return activity_service.get_user_activities(current_user.id)


@router.post("", response_model=Activity)
def create_activity(
    activity: ActivityCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new activity for the current user.

    Uses Service Layer pattern to handle business logic.

    Args:
        activity: Activity data
        current_user: Current authenticated user (injected dependency)
        db: Database session (injected dependency)

    Returns:
        Created activity object
    """
    # Use repository and service patterns
    activity_repo = ActivityRepository(db)
    activity_service = ActivityService(activity_repo)

    return activity_service.create_activity(activity, current_user.id)


@router.post("/sync", status_code=202)
def start_sync(current_user: User = Depends(get_current_user)):
    """Trigger a background task to sync Strava activities for the current user.

    This endpoint schedules a background job that fetches activities from
    the Strava API and saves them to the database. Uses delta sync to only
    fetch new activities since the last sync.

    Args:
        current_user: Current authenticated user (injected dependency)

    Returns:
        dict: A message indicating the sync has been started
    """
    sync_single_user_strava_activities_task.delay(user_id=current_user.id)
    return {"message": "Strava activity sync has been started."}
