"""Service layer for business logic.

This module contains service classes that encapsulate business logic,
following the Service Layer pattern to keep controllers thin and
promote code reuse.
"""

from datetime import timedelta
from typing import List, Optional

import auth
import models
import schemas
from repositories import ActivityRepository, UserRepository


class UserService:
    """Service for user-related business operations."""

    def __init__(self, user_repo: UserRepository):
        """Initialize the service with required repositories.

        Args:
            user_repo: User repository instance
        """
        self.user_repo = user_repo

    def register_user(self, user_data: schemas.UserCreate) -> models.User:
        """Register a new user account.

        Args:
            user_data: User registration data

        Returns:
            Created user object

        Raises:
            ValueError: If email is already registered
        """
        # Check if user already exists
        existing_user = self.user_repo.get_by_email(user_data.email)
        if existing_user:
            raise ValueError("Email already registered")

        # Create new user with hashed password
        hashed_password = auth.get_password_hash(user_data.password)
        new_user = models.User(
            email=user_data.email, username=user_data.username, hashed_password=hashed_password
        )

        return self.user_repo.create(new_user)

    def authenticate(self, email: str, password: str) -> Optional[models.User]:
        """Authenticate a user by email and password.

        Args:
            email: User's email address
            password: Plain text password

        Returns:
            User object if authentication successful, None otherwise
        """
        user = self.user_repo.get_by_email(email)
        if not user:
            return None
        if not auth.verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(
        self, user: models.User, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token for a user.

        Args:
            user: User to create token for
            expires_delta: Optional custom expiration time

        Returns:
            JWT token string
        """
        return auth.create_access_token(data={"sub": user.email}, expires_delta=expires_delta)

    def update_strava_tokens(
        self, user: models.User, access_token: str, refresh_token: str, expires_at
    ) -> models.User:
        """Update a user's Strava OAuth tokens.

        Args:
            user: User to update
            access_token: New Strava access token
            refresh_token: New Strava refresh token
            expires_at: Token expiration datetime

        Returns:
            Updated user object
        """
        user.strava_access_token = access_token
        user.strava_refresh_token = refresh_token
        user.strava_token_expires_at = expires_at
        return self.user_repo.update(user)


class ActivityService:
    """Service for activity-related business operations."""

    def __init__(self, activity_repo: ActivityRepository):
        """Initialize the service with required repositories.

        Args:
            activity_repo: Activity repository instance
        """
        self.activity_repo = activity_repo

    def get_user_activities(self, user_id: int) -> List[models.Activity]:
        """Get all activities for a user.

        Args:
            user_id: The user's ID

        Returns:
            List of user's activities
        """
        return self.activity_repo.get_by_user(user_id)

    def create_activity(
        self, activity_data: schemas.ActivityCreate, user_id: int
    ) -> models.Activity:
        """Create a new activity for a user.

        Args:
            activity_data: Activity data
            user_id: Owner's user ID

        Returns:
            Created activity object
        """
        new_activity = models.Activity(**activity_data.dict(), owner_id=user_id)
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
                new_activity = models.Activity(**activity_data, owner_id=user_id)
                new_activities.append(new_activity)

        if new_activities:
            return self.activity_repo.create_many(new_activities)
        return 0
