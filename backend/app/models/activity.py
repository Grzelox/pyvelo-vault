"""Activity model definition."""

from sqlalchemy import BigInteger, Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import relationship

from .base import Base


class Activity(Base):
    """Represents a cycling or fitness activity.

    This model stores information about individual workout activities,
    including distance, time, and elevation data.

    Attributes:
        id: Unique identifier for the activity (uses BigInteger to support Strava's 64-bit IDs)
        name: Human-readable name/title of the activity
        distance: Total distance covered in meters
        moving_time: Active time in seconds (excluding stops)
        elapsed_time: Total time in seconds (including stops)
        total_elevation_gain: Cumulative elevation climbed in meters
        calories: Energy burned in kilocalories, when provided by the source
        activity_type: Provider-specific activity category (e.g., Ride, Run)
        start_date: UTC timestamp when the activity started
        owner_id: Foreign key to the user who owns this activity
        owner: Relationship to the User model
    """

    __tablename__ = "activities"

    # In production (Postgres) we want BIGINT IDs (Strava/Garmin IDs can be 64-bit).
    # In tests we use SQLite; SQLite only auto-increments correctly when the PK type
    # is exactly INTEGER. Use a dialect variant so test fixtures can omit `id`.
    id = Column(
        BigInteger().with_variant(Integer, "sqlite"),
        primary_key=True,
        index=True,
        autoincrement=True,
    )
    name = Column(String, index=True)
    distance = Column(Float)
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    total_elevation_gain = Column(Float)
    calories = Column(Float, nullable=True)
    activity_type = Column(String, nullable=True)
    start_date = Column(DateTime(timezone=True))
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship to user
    owner = relationship("User", back_populates="activities")
