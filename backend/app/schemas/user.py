"""User-related Pydantic schemas for API validation."""

from datetime import datetime

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
