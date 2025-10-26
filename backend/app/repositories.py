"""Repository pattern implementation for data access layer.

This module provides a clean abstraction over database operations,
following the Repository pattern to separate data access logic from
business logic.
"""

from typing import List, Optional

import models
from sqlalchemy.orm import Session


class UserRepository:
    """Repository for User entity operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_id(self, user_id: int) -> Optional[models.User]:
        """Get a user by ID.

        Args:
            user_id: The user's ID

        Returns:
            User object if found, None otherwise
        """
        return self.db.query(models.User).filter(models.User.id == user_id).first()

    def get_by_email(self, email: str) -> Optional[models.User]:
        """Get a user by email address.

        Args:
            email: The user's email address

        Returns:
            User object if found, None otherwise
        """
        return self.db.query(models.User).filter(models.User.email == email).first()

    def get_latest(self) -> Optional[models.User]:
        """Get the most recently created user.

        Returns:
            User object if any exist, None otherwise
        """
        return self.db.query(models.User).order_by(models.User.id.desc()).first()

    def create(self, user: models.User) -> models.User:
        """Create a new user.

        Args:
            user: User model instance to create

        Returns:
            Created user with ID populated
        """
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def update(self, user: models.User) -> models.User:
        """Update an existing user.

        Args:
            user: User model instance to update

        Returns:
            Updated user
        """
        self.db.commit()
        self.db.refresh(user)
        return user

    def count(self) -> int:
        """Get the total count of users.

        Returns:
            Number of users in the database
        """
        return self.db.query(models.User).count()


class ActivityRepository:
    """Repository for Activity entity operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        self.db = db

    def get_by_id(self, activity_id: int) -> Optional[models.Activity]:
        """Get an activity by ID.

        Args:
            activity_id: The activity's ID

        Returns:
            Activity object if found, None otherwise
        """
        return self.db.query(models.Activity).filter(models.Activity.id == activity_id).first()

    def get_by_user(self, user_id: int) -> List[models.Activity]:
        """Get all activities for a specific user.

        Args:
            user_id: The user's ID

        Returns:
            List of activities belonging to the user
        """
        return self.db.query(models.Activity).filter(models.Activity.owner_id == user_id).all()

    def exists(self, activity_id: int, user_id: int) -> bool:
        """Check if an activity exists for a user.

        Args:
            activity_id: The activity's ID
            user_id: The user's ID

        Returns:
            True if activity exists, False otherwise
        """
        return (
            self.db.query(models.Activity).filter_by(id=activity_id, owner_id=user_id).first()
            is not None
        )

    def create(self, activity: models.Activity) -> models.Activity:
        """Create a new activity.

        Args:
            activity: Activity model instance to create

        Returns:
            Created activity with ID populated
        """
        self.db.add(activity)
        self.db.commit()
        self.db.refresh(activity)
        return activity

    def create_many(self, activities: List[models.Activity]) -> int:
        """Create multiple activities in bulk.

        Args:
            activities: List of Activity model instances to create

        Returns:
            Number of activities created
        """
        self.db.add_all(activities)
        self.db.commit()
        return len(activities)
