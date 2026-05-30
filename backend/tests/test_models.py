"""Tests for SQLAlchemy ORM models."""

from datetime import datetime, timezone

import pytest
from app.models import Activity, User


@pytest.mark.unit
class TestUserModel:
    """Tests for the User model."""

    def test_create_user(self, test_db):
        """Test creating a user with all required fields."""
        user = User(
            email="user@example.com",
            username="Test User",
            hashed_password="hashed_password_here",
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.id is not None
        assert user.email == "user@example.com"
        assert user.username == "Test User"
        assert user.hashed_password == "hashed_password_here"
        assert user.created_at is not None
        assert isinstance(user.created_at, datetime)

    def test_user_unique_email_constraint(self, test_db, test_user):
        """Test that email must be unique."""
        duplicate_user = User(
            email=test_user.email,
            username="Another User",
            hashed_password="different_password",
        )
        test_db.add(duplicate_user)

        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            test_db.commit()

    def test_user_strava_tokens_default_none(self, test_db):
        """Test that Strava tokens default to None."""
        user = User(
            email="nostra@example.com",
            username="No Strava",
            hashed_password="password",
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.strava_access_token is None
        assert user.strava_refresh_token is None
        assert user.strava_token_expires_at is None

    def test_user_with_strava_tokens(self, test_db):
        """Test creating a user with Strava tokens."""
        expires_at = datetime(2099, 12, 31, tzinfo=timezone.utc)
        user = User(
            email="strava@example.com",
            username="Strava User",
            hashed_password="password",
            strava_access_token="access_token",
            strava_refresh_token="refresh_token",
            strava_token_expires_at=expires_at,
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.strava_access_token == "access_token"
        assert user.strava_refresh_token == "refresh_token"
        # SQLite doesn't store timezone info, so compare without timezone
        assert user.strava_token_expires_at.replace(tzinfo=timezone.utc) == expires_at
        assert user.strava_connected is True

    def test_user_strava_connected_without_athlete_id(self, test_db):
        """Test legacy Strava connections still report as connected."""
        user = User(
            email="legacy@example.com",
            username="Legacy User",
            hashed_password="password",
            strava_access_token="access_token",
        )
        test_db.add(user)
        test_db.commit()
        test_db.refresh(user)

        assert user.strava_connected is True

    def test_user_activities_relationship(self, test_db, test_user, test_activities):
        """Test the relationship between User and Activities."""
        # Refresh user to load relationships
        test_db.refresh(test_user)

        assert len(test_user.activities) == 2
        assert all(isinstance(activity, Activity) for activity in test_user.activities)
        assert all(activity.owner_id == test_user.id for activity in test_user.activities)


@pytest.mark.unit
class TestActivityModel:
    """Tests for the Activity model."""

    def test_create_activity(self, test_db, test_user):
        """Test creating an activity with all required fields."""
        activity = Activity(
            name="Test Ride",
            distance=10000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=200.0,
            calories=450.0,
            owner_id=test_user.id,
        )
        test_db.add(activity)
        test_db.commit()
        test_db.refresh(activity)

        assert activity.id is not None
        assert activity.name == "Test Ride"
        assert activity.distance == 10000.0
        assert activity.moving_time == 3600
        assert activity.elapsed_time == 3700
        assert activity.total_elevation_gain == 200.0
        assert activity.calories == 450.0
        assert activity.owner_id == test_user.id

    def test_activity_owner_relationship(self, test_db, test_user):
        """Test the relationship between Activity and User."""
        activity = Activity(
            name="Test Ride",
            distance=10000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=200.0,
            owner_id=test_user.id,
        )
        test_db.add(activity)
        test_db.commit()
        test_db.refresh(activity)

        assert activity.owner is not None
        assert isinstance(activity.owner, User)
        assert activity.owner.id == test_user.id
        assert activity.owner.email == test_user.email

    def test_activity_requires_owner(self, test_db):
        """Test that activity requires an owner_id."""
        activity = Activity(
            name="Orphan Ride",
            distance=10000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=200.0,
            owner_id=None,
        )
        test_db.add(activity)

        with pytest.raises(Exception):  # SQLAlchemy will raise IntegrityError
            test_db.commit()

    def test_multiple_activities_for_user(self, test_db, test_user, test_activities):
        """Test that a user can have multiple activities."""
        assert len(test_activities) == 2

        # Query activities from database
        activities = test_db.query(Activity).filter_by(owner_id=test_user.id).all()
        assert len(activities) == 2
        assert all(activity.owner_id == test_user.id for activity in activities)
