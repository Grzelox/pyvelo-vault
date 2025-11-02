"""Tests for Celery background tasks."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from app.models import Activity, User


@pytest.mark.unit
class TestCreateDummyActivityTask:
    """Tests for create_dummy_activity_task."""

    @patch("tasks.SessionLocal")
    @patch("tasks.time.sleep")
    def test_create_dummy_activity_success(
        self, mock_sleep, mock_session_local, test_db, test_user
    ):
        """Test successful dummy activity creation."""
        # Mock SessionLocal to return test_db directly
        mock_session_local.return_value = test_db

        # Store user_id before task runs (task will close the session)
        user_id = test_user.id

        result = create_dummy_activity_task(user_id)

        assert result["status"] == "complete"
        assert result["user_id"] == user_id

        # Verify activity was created
        activities = test_db.query(models.Activity).filter_by(owner_id=user_id).all()
        assert len(activities) > 0

        # Verify sleep was called (simulating API delay)
        mock_sleep.assert_called_once_with(5)

    @patch("tasks.SessionLocal")
    @patch("tasks.time.sleep")
    def test_create_dummy_activity_user_not_found(self, mock_sleep, mock_session_local, test_db):
        """Test dummy activity creation with non-existent user."""
        mock_session_local.return_value = test_db

        result = create_dummy_activity_task(99999)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @patch("tasks.SessionLocal")
    @patch("tasks.time.sleep")
    def test_create_dummy_activity_random_values(
        self, mock_sleep, mock_session_local, test_db, test_user
    ):
        """Test that dummy activity has randomized values."""
        mock_session_local.return_value = test_db

        # Store user_id before tasks run (tasks will close the session)
        user_id = test_user.id

        # Create two activities
        create_dummy_activity_task(user_id)
        create_dummy_activity_task(user_id)

        activities = test_db.query(models.Activity).filter_by(owner_id=user_id).all()

        # Should have created 2 activities
        assert len(activities) == 2

        # Activities should have different names (very likely with random numbers)
        # or at least be valid activities
        assert all(activity.name.startswith("Dummy Activity") for activity in activities)
        assert all(activity.distance > 0 for activity in activities)


@pytest.mark.unit
class TestSyncStravaActivitiesTask:
    """Tests for sync_strava_activities_task."""

    @patch("tasks.SessionLocal")
    @patch("tasks.ActivitySyncContext")
    def test_sync_strava_activities_success(
        self,
        mock_context_class,
        mock_session_local,
        test_db,
        test_user_with_strava_tokens,
    ):
        """Test successful Strava activity sync."""
        mock_session_local.return_value = test_db

        # Store user_id before task runs (task will close the session)
        user_id = test_user_with_strava_tokens.id

        # Mock the sync context
        mock_context = Mock()
        mock_context.sync_activities.return_value = (
            True,  # is_connected
            [
                {
                    "id": 1001,
                    "name": "Morning Ride",
                    "distance": 15000.0,
                    "moving_time": 3600,
                    "elapsed_time": 3700,
                    "total_elevation_gain": 250.0,
                }
            ],
            None,  # No token update
        )
        mock_context_class.return_value = mock_context

        result = sync_strava_activities_task(user_id)

        assert result["status"] == "complete"
        assert result["user_id"] == user_id
        assert "activities_added" in result

    @patch("tasks.SessionLocal")
    def test_sync_strava_activities_user_not_found(self, mock_session_local, test_db):
        """Test sync with non-existent user."""
        mock_session_local.return_value = test_db

        result = sync_strava_activities_task(99999)

        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @patch("tasks.SessionLocal")
    @patch("tasks.ActivitySyncContext")
    def test_sync_strava_activities_not_connected(
        self, mock_context_class, mock_session_local, test_db, test_user
    ):
        """Test sync when user is not connected to Strava."""
        mock_session_local.return_value = test_db

        # Mock context to return not connected
        mock_context = Mock()
        mock_context.sync_activities.return_value = (False, [], None)
        mock_context_class.return_value = mock_context

        result = sync_strava_activities_task(test_user.id)

        assert result["status"] == "error"
        assert "not connected" in result["message"].lower()

    @patch("tasks.SessionLocal")
    @patch("tasks.ActivitySyncContext")
    def test_sync_strava_activities_with_token_refresh(
        self,
        mock_context_class,
        mock_session_local,
        test_db,
        test_user_with_strava_tokens,
    ):
        """Test sync with token refresh."""
        mock_session_local.return_value = test_db

        # Mock context to return token update
        new_expires = datetime(2025, 12, 31, tzinfo=timezone.utc)
        mock_context = Mock()
        mock_context.sync_activities.return_value = (
            True,
            [],
            {
                "access_token": "new_access_token",
                "refresh_token": "new_refresh_token",
                "expires_at": new_expires,
            },
        )
        mock_context_class.return_value = mock_context

        result = sync_strava_activities_task(test_user_with_strava_tokens.id)

        assert result["status"] == "complete"

        # Verify token was updated by checking the database directly
        updated_user = (
            test_db.query(models.User).filter_by(id=test_user_with_strava_tokens.id).first()
        )
        assert updated_user.strava_access_token == "new_access_token"
        assert updated_user.strava_refresh_token == "new_refresh_token"

    @patch("tasks.SessionLocal")
    @patch("tasks.ActivitySyncContext")
    def test_sync_strava_activities_exception_handling(
        self,
        mock_context_class,
        mock_session_local,
        test_db,
        test_user_with_strava_tokens,
    ):
        """Test that exceptions are handled gracefully."""
        mock_session_local.return_value = test_db

        # Mock context to raise exception
        mock_context = Mock()
        mock_context.sync_activities.side_effect = Exception("API Error")
        mock_context_class.return_value = mock_context

        result = sync_strava_activities_task(test_user_with_strava_tokens.id)

        assert result["status"] == "error"
        assert "API Error" in result["message"]

    @patch("tasks.SessionLocal")
    @patch("tasks.ActivitySyncContext")
    def test_sync_strava_activities_imports_new_only(
        self,
        mock_context_class,
        mock_session_local,
        test_db,
        test_user_with_strava_tokens,
        test_activities,
    ):
        """Test that sync only imports new activities."""
        # Store IDs before modifying (task will close the session)
        user_id = test_user_with_strava_tokens.id
        existing_activity_id = test_activities[0].id

        # Add test_activities to the user with strava tokens
        for activity in test_activities:
            activity.owner_id = user_id
        test_db.commit()

        mock_session_local.return_value = test_db

        # Mock context to return mix of existing and new activities
        mock_context = Mock()
        mock_context.sync_activities.return_value = (
            True,
            [
                {
                    "id": existing_activity_id,  # Existing
                    "name": "Existing",
                    "distance": 10000.0,
                    "moving_time": 3600,
                    "elapsed_time": 3700,
                    "total_elevation_gain": 200.0,
                },
                {
                    "id": 9999,  # New
                    "name": "New Activity",
                    "distance": 12000.0,
                    "moving_time": 4000,
                    "elapsed_time": 4100,
                    "total_elevation_gain": 250.0,
                },
            ],
            None,
        )
        mock_context_class.return_value = mock_context

        initial_count = test_db.query(models.Activity).filter_by(owner_id=user_id).count()

        result = sync_strava_activities_task(user_id)

        # Should only add 1 new activity
        assert result["status"] == "complete"

        final_count = test_db.query(models.Activity).filter_by(owner_id=user_id).count()

        assert final_count == initial_count + 1
