"""Pydantic models for API request/response validation.

This module defines the data schemas used for API endpoints,
ensuring type safety and automatic validation.
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr


class UserBase(BaseModel):
    """Base user schema with common fields."""

    email: EmailStr
    username: str


class UserCreate(UserBase):
    """Schema for user registration."""

    password: str


class User(UserBase):
    """User schema for API responses."""

    id: int
    created_at: datetime

    class Config:
        """Pydantic configuration."""

        from_attributes = True


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    email: Optional[str] = None


class ActivityBase(BaseModel):
    """Base schema for activity data.

    This schema contains the core fields shared across activity
    creation and response models.

    Attributes:
        name: Activity name or title
        distance: Distance in meters
        moving_time: Active time in seconds
        elapsed_time: Total elapsed time in seconds
        total_elevation_gain: Elevation gain in meters
    """

    name: str
    distance: float
    moving_time: int
    elapsed_time: int
    total_elevation_gain: float


class ActivityCreate(ActivityBase):
    """Schema for creating a new activity."""

    pass


class Activity(ActivityBase):
    """Activity schema for API responses.

    Extends ActivityBase with the database ID field for
    returning complete activity records.

    Attributes:
        id: Unique activity identifier from database
        owner_id: ID of the user who owns this activity
    """

    id: int
    owner_id: int

    class Config:
        """Pydantic configuration."""

        from_attributes = True
