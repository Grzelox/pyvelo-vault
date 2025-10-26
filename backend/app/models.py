"""SQLAlchemy ORM models for database tables.

This module defines the database schema using SQLAlchemy's declarative base.
"""

from datetime import datetime, timezone

from database import Base
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship


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

    # Relationship to activities
    activities = relationship("Activity", back_populates="owner")


class Activity(Base):
    """Represents a cycling or fitness activity.

    This model stores information about individual workout activities,
    including distance, time, and elevation data.

    Attributes:
        id: Unique identifier for the activity
        name: Human-readable name/title of the activity
        distance: Total distance covered in meters
        moving_time: Active time in seconds (excluding stops)
        elapsed_time: Total time in seconds (including stops)
        total_elevation_gain: Cumulative elevation climbed in meters
        owner_id: Foreign key to the user who owns this activity
        owner: Relationship to the User model
    """

    __tablename__ = "activities"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    distance = Column(Float)
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    total_elevation_gain = Column(Float)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship to user
    owner = relationship("User", back_populates="activities")
