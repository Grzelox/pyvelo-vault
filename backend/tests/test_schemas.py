"""Tests for Pydantic validation schemas."""

from datetime import datetime

import pytest
from app import schemas
from pydantic import ValidationError


@pytest.mark.unit
class TestUserSchemas:
    """Tests for User-related schemas."""

    def test_user_base_valid(self):
        """Test UserBase schema with valid data."""
        user = schemas.UserBase(email="test@example.com", username="Test User")
        assert user.email == "test@example.com"
        assert user.username == "Test User"

    def test_user_base_invalid_email(self):
        """Test UserBase schema rejects invalid email."""
        with pytest.raises(ValidationError):
            schemas.UserBase(email="not-an-email", username="Test User")

    def test_user_create_valid(self):
        """Test UserCreate schema with valid data."""
        user = schemas.UserCreate(
            email="test@example.com", username="Test User", password="securepassword123"
        )
        assert user.email == "test@example.com"
        assert user.username == "Test User"
        assert user.password == "securepassword123"

    def test_user_schema_from_orm(self, test_user):
        """Test User schema can be created from ORM model."""
        user_schema = schemas.User.model_validate(test_user)

        assert user_schema.id == test_user.id
        assert user_schema.email == test_user.email
        assert user_schema.username == test_user.username
        assert isinstance(user_schema.created_at, datetime)

    def test_user_schema_excludes_password(self, test_user):
        """Test that User response schema doesn't include password."""
        user_schema = schemas.User.model_validate(test_user)
        user_dict = user_schema.model_dump()

        assert "password" not in user_dict
        assert "hashed_password" not in user_dict


@pytest.mark.unit
class TestTokenSchemas:
    """Tests for authentication token schemas."""

    def test_token_valid(self):
        """Test Token schema with valid data."""
        token = schemas.Token(access_token="eyJ0eXAiOiJKV1QiLCJhbGc...", token_type="bearer")
        assert token.access_token == "eyJ0eXAiOiJKV1QiLCJhbGc..."
        assert token.token_type == "bearer"

    def test_token_data_valid(self):
        """Test TokenData schema with valid data."""
        token_data = schemas.TokenData(email="user@example.com")
        assert token_data.email == "user@example.com"

    def test_token_data_optional_email(self):
        """Test TokenData schema with optional email."""
        token_data = schemas.TokenData()
        assert token_data.email is None


@pytest.mark.unit
class TestActivitySchemas:
    """Tests for Activity-related schemas."""

    def test_activity_base_valid(self):
        """Test ActivityBase schema with valid data."""
        activity = schemas.ActivityBase(
            name="Morning Ride",
            distance=15000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=250.0,
            calories=500.0,
        )
        assert activity.name == "Morning Ride"
        assert activity.distance == 15000.0
        assert activity.moving_time == 3600
        assert activity.elapsed_time == 3700
        assert activity.total_elevation_gain == 250.0
        assert activity.calories == 500.0

    def test_activity_base_type_validation(self):
        """Test ActivityBase schema validates types."""
        with pytest.raises(ValidationError):
            schemas.ActivityBase(
                name="Invalid",
                distance="not-a-number",  # Should be float
                moving_time=3600,
                elapsed_time=3700,
                total_elevation_gain=250.0,
            )

    def test_activity_create_valid(self):
        """Test ActivityCreate schema with valid data."""
        activity = schemas.ActivityCreate(
            name="Evening Ride",
            distance=20000.0,
            moving_time=4800,
            elapsed_time=5000,
            total_elevation_gain=300.0,
            calories=650.0,
        )
        assert isinstance(activity, schemas.ActivityBase)

    def test_activity_schema_from_orm(self, test_activities):
        """Test Activity schema can be created from ORM model."""
        activity = test_activities[0]
        activity_schema = schemas.Activity.model_validate(activity)

        assert activity_schema.id == activity.id
        assert activity_schema.name == activity.name
        assert activity_schema.distance == activity.distance
        assert activity_schema.moving_time == activity.moving_time
        assert activity_schema.elapsed_time == activity.elapsed_time
        assert activity_schema.total_elevation_gain == activity.total_elevation_gain
        assert activity_schema.calories == activity.calories
        assert activity_schema.owner_id == activity.owner_id

    def test_activity_schema_includes_ids(self, test_activities):
        """Test that Activity response schema includes ID fields."""
        activity = test_activities[0]
        activity_schema = schemas.Activity.model_validate(activity)
        activity_dict = activity_schema.model_dump()

        assert "id" in activity_dict
        assert "owner_id" in activity_dict
        assert "calories" in activity_dict

    def test_activity_negative_values_accepted(self):
        """Test that negative values are accepted (edge case for data)."""
        # Some APIs might return negative values for descents
        activity = schemas.ActivityBase(
            name="Downhill",
            distance=5000.0,
            moving_time=600,
            elapsed_time=650,
            total_elevation_gain=-100.0,  # Descent
        )
        assert activity.total_elevation_gain == -100.0
