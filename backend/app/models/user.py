"""User model definition."""

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class User(Base):
    """Represents a user account.

    Attributes:
        id: Unique identifier for the user
        email: User's email address (used for login)
        username: User's display name
        hashed_password: Bcrypt-hashed password
        created_at: Account creation timestamp
        strava_access_token: OAuth2 access token for Strava API
        strava_refresh_token: OAuth2 refresh token for Strava API
        strava_token_expires_at: Expiration timestamp for the access token
        activities: Relationship to user's activities
    """

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Strava OAuth tokens
    strava_access_token = Column(String, nullable=True)
    strava_refresh_token = Column(String, nullable=True)
    strava_token_expires_at = Column(DateTime, nullable=True)
    strava_athlete_id = Column(Integer, nullable=True)
    last_strava_sync = Column(DateTime, nullable=True)
    last_sync_source = Column(String, nullable=True)
    last_sync_status = Column(String, nullable=True)
    last_sync_at = Column(DateTime, nullable=True)

    # Garmin Connect OAuth tokens (optional integration)
    garmin_access_token = Column(String, nullable=True)
    garmin_refresh_token = Column(String, nullable=True)
    garmin_token_expires_at = Column(DateTime, nullable=True)
    garmin_user_id = Column(String, nullable=True)
    last_garmin_sync = Column(DateTime, nullable=True)

    # Relationship to activities
    activities = relationship("Activity", back_populates="owner")

    @property
    def strava_connected(self) -> bool:
        """Return True when the user has an active Strava connection."""
        return bool(self.strava_access_token)

    @property
    def garmin_connected(self) -> bool:
        """Return True when the user has an active Garmin connection."""
        return bool(self.garmin_access_token)
