"""Activity repository for data access operations."""

from typing import List

from app.models import Activity
from sqlalchemy.orm import Session

from .base import BaseRepository


class ActivityRepository(BaseRepository[Activity]):
    """Repository for Activity entity operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(Activity, db)

    def get_by_user(self, user_id: int) -> List[Activity]:
        """Get all activities for a specific user.

        Args:
            user_id: The user's ID

        Returns:
            List of activities belonging to the user
        """
        return self.db.query(Activity).filter(Activity.owner_id == user_id).all()

    def get_missing_calories_by_user(
        self, user_id: int, activity_ids: list[int] | None = None
    ) -> List[Activity]:
        """Get user activities that still need calorie backfill."""
        query = self.db.query(Activity).filter(
            Activity.owner_id == user_id,
            Activity.calories.is_(None),
        )
        if activity_ids is not None:
            if not activity_ids:
                return []
            query = query.filter(Activity.id.in_(activity_ids))
        return query.order_by(Activity.start_date.desc()).all()

    def exists(self, activity_id: int, user_id: int) -> bool:
        """Check if an activity exists for a user.

        Args:
            activity_id: The activity's ID
            user_id: The user's ID

        Returns:
            True if activity exists, False otherwise
        """
        return (
            self.db.query(Activity).filter_by(id=activity_id, owner_id=user_id).first() is not None
        )

    def create_many(self, activities: List[Activity]) -> int:
        """Create multiple activities in bulk.

        Args:
            activities: List of Activity model instances to create

        Returns:
            Number of activities created
        """
        self.db.add_all(activities)
        self.db.commit()
        return len(activities)

    def update_calories(self, activity_id: int, user_id: int, calories: float) -> bool:
        """Update calories for a single user-owned activity."""
        activity = (
            self.db.query(Activity)
            .filter(Activity.id == activity_id, Activity.owner_id == user_id)
            .first()
        )
        if activity is None:
            return False

        activity.calories = calories
        self.db.commit()
        return True
