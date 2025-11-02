"""Activity model definition."""

from sqlalchemy import BigInteger, Column, Float, ForeignKey, Integer, String
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
        owner_id: Foreign key to the user who owns this activity
        owner: Relationship to the User model
    """

    __tablename__ = "activities"

    id = Column(BigInteger, primary_key=True, index=True)
    name = Column(String, index=True)
    distance = Column(Float)
    moving_time = Column(Integer)
    elapsed_time = Column(Integer)
    total_elevation_gain = Column(Float)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False)

    # Relationship to user
    owner = relationship("User", back_populates="activities")
