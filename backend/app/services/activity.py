"""Activity service for business logic."""

from typing import List

from app.models import Activity
from app.repositories.activity import ActivityRepository
from app.schemas.activity import ActivityCreate


class ActivityService:
    """Service for activity-related business operations."""

    def __init__(self, activity_repo: ActivityRepository):
        """Initialize the service with required repositories.

        Args:
            activity_repo: Activity repository instance
        """
        self.activity_repo = activity_repo

    def get_user_activities(self, user_id: int) -> List[Activity]:
        """Get all activities for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of user's activities
        """
        return self.activity_repo.get_by_user(user_id)

    def create_activity(self, activity_data: ActivityCreate, user_id: int) -> Activity:
        """Create a new activity for a user.

        Args:
            activity_data: Activity data
            user_id: Owner's user ID

        Returns:
            Created activity object
        """
        new_activity = Activity(**activity_data.model_dump(), owner_id=user_id)
        return self.activity_repo.create(new_activity)

    def import_activities(self, activities_data: List[dict], user_id: int) -> int:
        """Import multiple activities for a user, avoiding duplicates.

        Args:
            activities_data: List of activity data dictionaries
            user_id: Owner's user ID

        Returns:
            Number of new activities created
        """
        new_activities = []

        for activity_data in activities_data:
            # Check if activity already exists
            if not self.activity_repo.exists(activity_data["id"], user_id):
                new_activity = Activity(**activity_data, owner_id=user_id)
                new_activities.append(new_activity)
            elif activity_data.get("activity_type"):
                self.activity_repo.update_activity_type(
                    activity_data["id"],
                    user_id,
                    activity_data["activity_type"],
                )

        if new_activities:
            return self.activity_repo.create_many(new_activities)
        return 0

    def get_activities_missing_calories(
        self, user_id: int, activity_ids: list[int] | None = None
    ) -> List[Activity]:
        """Get user activities that need calorie backfill."""
        return self.activity_repo.get_missing_calories_by_user(user_id, activity_ids=activity_ids)

    def update_activity_calories(self, activity_id: int, user_id: int, calories: float) -> bool:
        """Update calories for one user-owned activity."""
        return self.activity_repo.update_calories(activity_id, user_id, calories)

    def get_activities_missing_activity_type(
        self, user_id: int, activity_ids: list[int] | None = None
    ) -> List[Activity]:
        """Get user activities that need activity type backfill."""
        return self.activity_repo.get_missing_activity_type_by_user(
            user_id,
            activity_ids=activity_ids,
        )

    def update_activity_type(self, activity_id: int, user_id: int, activity_type: str) -> bool:
        """Update activity type for one user-owned activity."""
        return self.activity_repo.update_activity_type(activity_id, user_id, activity_type)
