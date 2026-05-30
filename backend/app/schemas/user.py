"""User-related Pydantic schemas for API validation."""

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
    strava_connected: bool = False
    garmin_connected: bool = False
    last_strava_sync: Optional[datetime] = None
    last_garmin_sync: Optional[datetime] = None
    last_sync_source: Optional[str] = None
    last_sync_status: Optional[str] = None
    last_sync_at: Optional[datetime] = None

    class Config:
        """Pydantic configuration."""

        from_attributes = True
