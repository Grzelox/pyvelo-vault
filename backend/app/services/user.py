"""User service for business logic."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models import User
from app.repositories import UserRepository
from app.schemas import UserCreate


class UserService:
    """Service for user-related business operations."""

    def __init__(self, user_repo: UserRepository):
        """Initialize the service with required repositories.

        Args:
            user_repo: User repository instance
        """
        self.user_repo = user_repo

    def register_user(self, user_data: UserCreate) -> User:
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
        hashed_password = get_password_hash(user_data.password)
        new_user = User(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
        )

        return self.user_repo.create(new_user)

    def authenticate(self, email: str, password: str) -> Optional[User]:
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
        if not verify_password(password, user.hashed_password):
            return None
        return user

    def create_access_token(self, user: User, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token for a user.

        Args:
            user: User to create token for
            expires_delta: Optional custom expiration time

        Returns:
            JWT token string
        """
        return create_access_token(data={"sub": user.email}, expires_delta=expires_delta)

    def update_strava_tokens(
        self,
        user: User,
        access_token: str,
        refresh_token: str,
        expires_at: datetime,
        athlete_id: int = None,
    ) -> User:
        """Update a user's Strava OAuth tokens.

        Args:
            user: User to update
            access_token: New Strava access token
            refresh_token: New Strava refresh token
            expires_at: Token expiration datetime
            athlete_id: Optional Strava athlete ID

        Returns:
            Updated user object
        """
        user.strava_access_token = access_token
        user.strava_refresh_token = refresh_token
        user.strava_token_expires_at = expires_at
        if athlete_id:
            user.strava_athlete_id = athlete_id
        return self.user_repo.update(user)

    def disconnect_strava(self, user: User) -> User:
        """Disconnect Strava account by clearing all OAuth tokens.

        Args:
            user: User to disconnect from Strava

        Returns:
            Updated user object with cleared Strava tokens
        """
        user.strava_access_token = None
        user.strava_refresh_token = None
        user.strava_token_expires_at = None
        user.strava_athlete_id = None
        return self.user_repo.update(user)

    def update_garmin_tokens(
        self,
        user: User,
        access_token: str,
        refresh_token: str | None,
        expires_at: datetime | None,
        garmin_user_id: str | None = None,
    ) -> User:
        """Update a user's Garmin OAuth tokens."""
        user.garmin_access_token = access_token
        user.garmin_refresh_token = refresh_token
        user.garmin_token_expires_at = expires_at
        if garmin_user_id:
            user.garmin_user_id = garmin_user_id
        return self.user_repo.update(user)

    def disconnect_garmin(self, user: User) -> User:
        """Disconnect Garmin account by clearing all OAuth tokens."""
        user.garmin_access_token = None
        user.garmin_refresh_token = None
        user.garmin_token_expires_at = None
        user.garmin_user_id = None
        return self.user_repo.update(user)

    def record_sync_status(
        self,
        user: User,
        source: str,
        status: str,
        recorded_at: datetime | None = None,
    ) -> User:
        """Persist the latest sync attempt status for a user."""
        event_time = recorded_at or datetime.now(timezone.utc)

        user.last_sync_source = source
        user.last_sync_status = status
        user.last_sync_at = event_time

        if status == "success":
            if source == "Strava":
                user.last_strava_sync = event_time
            elif source == "Garmin":
                user.last_garmin_sync = event_time

        return self.user_repo.update(user)
