"""Tests for repository pattern implementation."""

from datetime import datetime, timezone

import pytest
from app.models import Activity, User
from app.repositories import ActivityRepository, UserRepository


@pytest.mark.unit
class TestUserRepository:
    """Tests for UserRepository."""

    def test_get_by_id_exists(self, test_db, test_user):
        """Test getting a user by ID when user exists."""
        repo = UserRepository(test_db)
        user = repo.get_by_id(test_user.id)

        assert user is not None
        assert user.id == test_user.id
        assert user.email == test_user.email

    def test_get_by_id_not_exists(self, test_db):
        """Test getting a user by ID when user doesn't exist."""
        repo = UserRepository(test_db)
        user = repo.get_by_id(99999)

        assert user is None

    def test_get_by_email_exists(self, test_db, test_user):
        """Test getting a user by email when user exists."""
        repo = UserRepository(test_db)
        user = repo.get_by_email(test_user.email)

        assert user is not None
        assert user.email == test_user.email
        assert user.id == test_user.id

    def test_get_by_email_not_exists(self, test_db):
        """Test getting a user by email when user doesn't exist."""
        repo = UserRepository(test_db)
        user = repo.get_by_email("nonexistent@example.com")

        assert user is None

    def test_get_latest(self, test_db, test_user):
        """Test getting the most recently created user."""
        # Create another user
        new_user = User(
            email="newest@example.com",
            username="Newest User",
            hashed_password="password",
        )
        test_db.add(new_user)
        test_db.commit()
        test_db.refresh(new_user)

        repo = UserRepository(test_db)
        latest = repo.get_latest()

        assert latest is not None
        assert latest.id == new_user.id

    def test_create_user(self, test_db):
        """Test creating a new user."""
        repo = UserRepository(test_db)
        new_user = User(
            email="created@example.com",
            username="Created User",
            hashed_password="hashed_pass",
        )

        created = repo.create(new_user)

        assert created.id is not None
        assert created.email == "created@example.com"
        assert created.username == "Created User"

    def test_update_user(self, test_db, test_user):
        """Test updating a user."""
        repo = UserRepository(test_db)

        test_user.username = "Updated Name"
        updated = repo.update(test_user)

        assert updated.username == "Updated Name"

        # Verify in database
        db_user = repo.get_by_id(test_user.id)
        assert db_user.username == "Updated Name"

    def test_count(self, test_db, test_user):
        """Test counting total users."""
        repo = UserRepository(test_db)
        count = repo.count()

        assert count >= 1  # At least test_user exists


@pytest.mark.unit
class TestActivityRepository:
    """Tests for ActivityRepository."""

    def test_get_by_id_exists(self, test_db, test_activities):
        """Test getting an activity by ID when it exists."""
        repo = ActivityRepository(test_db)
        activity = repo.get_by_id(test_activities[0].id)

        assert activity is not None
        assert activity.id == test_activities[0].id
        assert activity.name == test_activities[0].name

    def test_get_by_id_not_exists(self, test_db):
        """Test getting an activity by ID when it doesn't exist."""
        repo = ActivityRepository(test_db)
        activity = repo.get_by_id(99999)

        assert activity is None

    def test_get_by_user(self, test_db, test_user, test_activities):
        """Test getting all activities for a user."""
        repo = ActivityRepository(test_db)
        activities = repo.get_by_user(test_user.id)

        assert len(activities) == 2
        assert all(activity.owner_id == test_user.id for activity in activities)

    def test_get_by_user_no_activities(self, test_db, test_user):
        """Test getting activities for a user with no activities."""
        # Create a new user without activities
        new_user = User(
            email="noactivities@example.com",
            username="No Activities",
            hashed_password="password",
        )
        test_db.add(new_user)
        test_db.commit()
        test_db.refresh(new_user)

        repo = ActivityRepository(test_db)
        activities = repo.get_by_user(new_user.id)

        assert len(activities) == 0

    def test_get_missing_calories_by_user(self, test_db, test_user, test_activities):
        """Test getting activities that need calorie backfill."""
        test_activities[0].calories = None
        test_db.commit()

        repo = ActivityRepository(test_db)
        activities = repo.get_missing_calories_by_user(test_user.id)

        assert [activity.id for activity in activities] == [test_activities[0].id]

    def test_get_missing_calories_by_user_filters_ids(self, test_db, test_user, test_activities):
        """Test missing calorie lookup can be limited to selected activities."""
        test_activities[0].calories = None
        test_activities[1].calories = None
        test_db.commit()

        repo = ActivityRepository(test_db)
        activities = repo.get_missing_calories_by_user(
            test_user.id,
            activity_ids=[test_activities[1].id],
        )

        assert [activity.id for activity in activities] == [test_activities[1].id]

    def test_get_missing_activity_type_by_user(self, test_db, test_user, test_activities):
        """Test getting activities that need activity type backfill."""
        test_activities[0].activity_type = None
        test_activities[1].activity_type = "Ride"
        test_db.commit()

        repo = ActivityRepository(test_db)
        activities = repo.get_missing_activity_type_by_user(test_user.id)

        assert [activity.id for activity in activities] == [test_activities[0].id]

    def test_get_missing_activity_type_by_user_filters_ids(
        self, test_db, test_user, test_activities
    ):
        """Test missing activity type lookup can be limited to selected activities."""
        test_activities[0].activity_type = None
        test_activities[1].activity_type = None
        test_db.commit()

        repo = ActivityRepository(test_db)
        activities = repo.get_missing_activity_type_by_user(
            test_user.id,
            activity_ids=[test_activities[1].id],
        )

        assert [activity.id for activity in activities] == [test_activities[1].id]

    def test_exists_true(self, test_db, test_user, test_activities):
        """Test exists returns True when activity exists for user."""
        repo = ActivityRepository(test_db)
        exists = repo.exists(test_activities[0].id, test_user.id)

        assert exists is True

    def test_exists_false_wrong_user(self, test_db, test_activities):
        """Test exists returns False for wrong user."""
        repo = ActivityRepository(test_db)
        exists = repo.exists(test_activities[0].id, 99999)

        assert exists is False

    def test_exists_false_wrong_activity(self, test_db, test_user):
        """Test exists returns False for non-existent activity."""
        repo = ActivityRepository(test_db)
        exists = repo.exists(99999, test_user.id)

        assert exists is False

    def test_create_activity(self, test_db, test_user):
        """Test creating a new activity."""
        repo = ActivityRepository(test_db)
        new_activity = Activity(
            name="New Ride",
            distance=12000.0,
            moving_time=2400,
            elapsed_time=2500,
            total_elevation_gain=180.0,
            owner_id=test_user.id,
        )

        created = repo.create(new_activity)

        assert created.id is not None
        assert created.name == "New Ride"
        assert created.owner_id == test_user.id

    def test_create_many(self, test_db, test_user):
        """Test creating multiple activities in bulk."""
        repo = ActivityRepository(test_db)
        activities = [
            Activity(
                name=f"Bulk Activity {i}",
                distance=10000.0 + i * 1000,
                moving_time=3600,
                elapsed_time=3700,
                total_elevation_gain=200.0,
                owner_id=test_user.id,
            )
            for i in range(3)
        ]

        count = repo.create_many(activities)

        assert count == 3

        # Verify in database
        db_activities = repo.get_by_user(test_user.id)
        assert len(db_activities) >= 3

    def test_update_calories(self, test_db, test_user, test_activities):
        """Test updating calories for a user-owned activity."""
        test_activities[0].calories = None
        test_db.commit()

        repo = ActivityRepository(test_db)
        updated = repo.update_calories(test_activities[0].id, test_user.id, 555.0)

        assert updated is True
        test_db.refresh(test_activities[0])
        assert test_activities[0].calories == 555.0

    def test_update_calories_wrong_user(self, test_db, test_activities):
        """Test calorie updates are scoped to the owning user."""
        repo = ActivityRepository(test_db)
        updated = repo.update_calories(test_activities[0].id, 99999, 555.0)

        assert updated is False

    def test_update_activity_type(self, test_db, test_user, test_activities):
        """Test updating activity type for a user-owned activity."""
        repo = ActivityRepository(test_db)

        updated = repo.update_activity_type(test_activities[0].id, test_user.id, "Ride")

        assert updated is True
        test_db.refresh(test_activities[0])
        assert test_activities[0].activity_type == "Ride"

    def test_update_activity_type_wrong_user(self, test_db, test_activities):
        """Test activity type updates are scoped to the owning user."""
        repo = ActivityRepository(test_db)

        updated = repo.update_activity_type(test_activities[0].id, 99999, "Ride")

        assert updated is False

    def test_get_latest_activity_start_date(self, test_db, test_user, test_activities):
        """Test latest activity start_date lookup for a user."""
        test_activities[0].start_date = datetime(2025, 1, 1, 9, 0, tzinfo=timezone.utc)
        test_activities[1].start_date = datetime(2025, 1, 2, 18, 30, tzinfo=timezone.utc)
        test_db.commit()

        repo = ActivityRepository(test_db)
        latest_start_date = repo.get_latest_activity_start_date(test_user.id)

        assert latest_start_date == datetime(2025, 1, 2, 18, 30, tzinfo=timezone.utc)

    def test_get_latest_activity_start_date_returns_none_when_missing(
        self,
        test_db,
        test_user,
        test_activities,
    ):
        """Test latest activity start_date returns None when all are null."""
        test_activities[0].start_date = None
        test_activities[1].start_date = None
        test_db.commit()

        repo = ActivityRepository(test_db)

        assert repo.get_latest_activity_start_date(test_user.id) is None
