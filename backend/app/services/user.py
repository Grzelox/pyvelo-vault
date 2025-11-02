"""User service for business logic."""

from datetime import datetime, timedelta
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
        self, user: User, access_token: str, refresh_token: str, expires_at: datetime
    ) -> User:
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
