"""Tests for service layer business logic."""

from datetime import datetime, timedelta, timezone

import pytest
from app import schemas
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService, UserService


@pytest.mark.unit
class TestUserService:
    """Tests for UserService."""

    def test_register_user_success(self, test_db):
        """Test successful user registration."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        user_data = schemas.UserCreate(
            email="newuser@example.com", username="New User", password="securepassword"
        )

        user = service.register_user(user_data)

        assert user.id is not None
        assert user.email == "newuser@example.com"
        assert user.username == "New User"
        assert user.hashed_password != "securepassword"  # Should be hashed

    def test_register_user_duplicate_email(self, test_db, test_user):
        """Test registering with an already registered email."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        user_data = schemas.UserCreate(
            email=test_user.email,  # Duplicate email
            username="Another User",
            password="password",
        )

        with pytest.raises(ValueError, match="Email already registered"):
            service.register_user(user_data)

    def test_authenticate_success(self, test_db, test_user):
        """Test successful authentication."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        user = service.authenticate(test_user.email, "testpassword")

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_authenticate_wrong_password(self, test_db, test_user):
        """Test authentication with wrong password."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        user = service.authenticate(test_user.email, "wrongpassword")

        assert user is None

    def test_authenticate_nonexistent_user(self, test_db):
        """Test authentication with nonexistent user."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        user = service.authenticate("nonexistent@example.com", "password")

        assert user is None

    def test_create_access_token(self, test_db, test_user):
        """Test creating an access token for a user."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        token = service.create_access_token(test_user)

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_access_token_with_expiry(self, test_db, test_user):
        """Test creating an access token with custom expiry."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        expires_delta = timedelta(minutes=60)
        token = service.create_access_token(test_user, expires_delta)

        assert token is not None
        assert isinstance(token, str)

    def test_update_strava_tokens(self, test_db, test_user):
        """Test updating Strava OAuth tokens."""
        user_repo = UserRepository(test_db)
        service = UserService(user_repo)

        expires_at = datetime(2099, 12, 31, tzinfo=timezone.utc)
        updated_user = service.update_strava_tokens(
            test_user, "new_access_token", "new_refresh_token", expires_at
        )

        assert updated_user.strava_access_token == "new_access_token"
        assert updated_user.strava_refresh_token == "new_refresh_token"
        # SQLite doesn't store timezone info, so compare without timezone
        assert updated_user.strava_token_expires_at.replace(tzinfo=timezone.utc) == expires_at

        # Verify in database
        db_user = user_repo.get_by_id(test_user.id)
        assert db_user.strava_access_token == "new_access_token"


@pytest.mark.unit
class TestActivityService:
    """Tests for ActivityService."""

    def test_get_user_activities(self, test_db, test_user, test_activities):
        """Test getting all activities for a user."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        activities = service.get_user_activities(test_user.id)

        assert len(activities) == 2
        assert all(activity.owner_id == test_user.id for activity in activities)

    def test_get_user_activities_empty(self, test_db):
        """Test getting activities for a user with no activities."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        activities = service.get_user_activities(99999)

        assert len(activities) == 0

    def test_create_activity(self, test_db, test_user):
        """Test creating a new activity."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        activity_data = schemas.ActivityCreate(
            name="Test Ride",
            distance=15000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=250.0,
            calories=500.0,
        )

        activity = service.create_activity(activity_data, test_user.id)

        assert activity.id is not None
        assert activity.name == "Test Ride"
        assert activity.calories == 500.0
        assert activity.owner_id == test_user.id

    def test_import_activities_new(self, test_db, test_user):
        """Test importing new activities."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        activities_data = [
            {
                "id": 1001,
                "name": "Import 1",
                "distance": 10000.0,
                "moving_time": 3600,
                "elapsed_time": 3700,
                "total_elevation_gain": 200.0,
                "calories": 450.0,
            },
            {
                "id": 1002,
                "name": "Import 2",
                "distance": 12000.0,
                "moving_time": 4000,
                "elapsed_time": 4100,
                "total_elevation_gain": 250.0,
                "calories": 520.0,
            },
        ]

        count = service.import_activities(activities_data, test_user.id)

        assert count == 2

    def test_import_activities_duplicate_prevention(self, test_db, test_user, test_activities):
        """Test that duplicate activities are not imported."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        # Try to import an activity that already exists
        activities_data = [
            {
                "id": test_activities[0].id,  # Existing activity
                "name": "Duplicate",
                "distance": 10000.0,
                "moving_time": 3600,
                "elapsed_time": 3700,
                "total_elevation_gain": 200.0,
                "calories": 450.0,
            }
        ]

        count = service.import_activities(activities_data, test_user.id)

        assert count == 0  # Should not import duplicate

    def test_import_activities_mixed(self, test_db, test_user, test_activities):
        """Test importing a mix of new and existing activities."""
        activity_repo = ActivityRepository(test_db)
        service = ActivityService(activity_repo)

        activities_data = [
            {
                "id": test_activities[0].id,  # Existing
                "name": "Duplicate",
                "distance": 10000.0,
                "moving_time": 3600,
                "elapsed_time": 3700,
                "total_elevation_gain": 200.0,
                "calories": 450.0,
            },
            {
                "id": 2001,  # New
                "name": "New Activity",
                "distance": 15000.0,
                "moving_time": 4500,
                "elapsed_time": 4600,
                "total_elevation_gain": 300.0,
                "calories": 620.0,
            },
        ]

        count = service.import_activities(activities_data, test_user.id)

        assert count == 1  # Only the new one should be imported
