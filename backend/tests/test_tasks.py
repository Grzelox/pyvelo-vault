"""Tests for background task functions.

When testing @inject decorated functions, we pass dependencies explicitly
to bypass the container wiring. This is the recommended testing pattern
with dependency-injector.
"""

from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from app.integrations.strava.tasks import (
    fill_missing_strava_activity_calories_task,
    schedule_all_user_syncs_task,
    sync_single_user_strava_activities_task,
)
from app.models import Activity, User
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService


@contextmanager
def db_session_context(session):
    """Context manager wrapper for test session."""
    yield session


@pytest.mark.unit
class TestSyncSingleUserStravaActivitiesTask:
    """Tests for Strava delta sync task function."""

    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_success(self, mock_strategy_class, test_db, test_user_with_strava_tokens):
        user_id = test_user_with_strava_tokens.id

        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = True
        mock_strategy.refresh_token_if_needed.return_value = None
        mock_strategy.fetch_activities.return_value = [
            {
                "id": 1001,
                "name": "Morning Ride",
                "distance": 15000.0,
                "moving_time": 3600,
                "elapsed_time": 3700,
                "total_elevation_gain": 250.0,
                "calories": 450.0,
            }
        ]
        mock_strategy_class.return_value = mock_strategy

        # Pass dependencies explicitly to bypass DI container
        result = sync_single_user_strava_activities_task(
            user_id,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )

        assert result["status"] == "complete"
        assert result["user_id"] == user_id
        assert result["activities_added"] == 1

    def test_user_not_found(self, test_db):
        # Pass dependencies explicitly to bypass DI container
        result = sync_single_user_strava_activities_task(
            99999,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )
        assert result["status"] == "error"
        assert "not found" in result["message"].lower()

    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_not_connected(self, mock_strategy_class, test_db, test_user):
        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = False
        mock_strategy_class.return_value = mock_strategy

        result = sync_single_user_strava_activities_task(
            test_user.id,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )
        assert result["status"] == "error"
        assert "not connected" in result["message"].lower()

    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_token_refresh_updates_user(
        self, mock_strategy_class, test_db, test_user_with_strava_tokens
    ):
        new_expires = datetime(2099, 12, 31, tzinfo=timezone.utc)

        def refresh_token(user):
            user.strava_access_token = "new_access"
            user.strava_refresh_token = "new_refresh"
            user.strava_token_expires_at = new_expires
            return {
                "access_token": "new_access",
                "refresh_token": "new_refresh",
                "expires_at": new_expires,
            }

        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = True
        mock_strategy.refresh_token_if_needed.side_effect = refresh_token
        mock_strategy.fetch_activities.return_value = []
        mock_strategy_class.return_value = mock_strategy

        result = sync_single_user_strava_activities_task(
            test_user_with_strava_tokens.id,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )
        assert result["status"] == "complete"

        updated_user = test_db.query(User).filter_by(id=test_user_with_strava_tokens.id).first()
        assert updated_user.strava_access_token == "new_access"
        assert updated_user.strava_refresh_token == "new_refresh"

    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_imports_new_only(
        self,
        mock_strategy_class,
        test_db,
        test_user_with_strava_tokens,
        test_activities,
    ):
        # Ensure some existing activities are owned by the same user
        user_id = test_user_with_strava_tokens.id
        for activity in test_activities:
            activity.owner_id = user_id
        test_db.commit()

        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = True
        mock_strategy.refresh_token_if_needed.return_value = None
        mock_strategy.fetch_activities.return_value = [
            {
                "id": test_activities[0].id,
                "name": "Existing",
                "distance": 1.0,
                "moving_time": 1,
                "elapsed_time": 1,
                "total_elevation_gain": 1.0,
                "calories": 450.0,
            },
            {
                "id": 9999,
                "name": "New Activity",
                "distance": 2.0,
                "moving_time": 2,
                "elapsed_time": 2,
                "total_elevation_gain": 2.0,
                "calories": 620.0,
            },
        ]
        mock_strategy_class.return_value = mock_strategy

        initial_count = test_db.query(type(test_activities[0])).filter_by(owner_id=user_id).count()
        result = sync_single_user_strava_activities_task(
            user_id,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )
        assert result["status"] == "complete"
        assert (
            test_db.query(type(test_activities[0])).filter_by(owner_id=user_id).count()
            == initial_count + 1
        )

    @patch("app.worker.fill_missing_strava_activity_calories_task.apply_async")
    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_dispatches_calorie_backfill_batches(
        self,
        mock_strategy_class,
        mock_apply_async,
        test_db,
        test_user_with_strava_tokens,
    ):
        user_id = test_user_with_strava_tokens.id
        activities_data = [
            {
                "id": 10000 + index,
                "name": f"Activity {index}",
                "distance": 10000.0,
                "moving_time": 3600,
                "elapsed_time": 3700,
                "total_elevation_gain": 250.0,
                "calories": None,
            }
            for index in range(25)
        ]

        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = True
        mock_strategy.refresh_token_if_needed.return_value = None
        mock_strategy.fetch_activities.return_value = activities_data
        mock_strategy_class.return_value = mock_strategy

        result = sync_single_user_strava_activities_task(
            user_id,
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )

        assert result["status"] == "complete"
        assert result["calorie_backfill_tasks"] == 3
        assert mock_apply_async.call_count == 3
        assert [call.kwargs["countdown"] for call in mock_apply_async.call_args_list] == [
            0,
            60,
            120,
        ]
        assert [len(call.kwargs["args"][1]) for call in mock_apply_async.call_args_list] == [
            10,
            10,
            5,
        ]


@pytest.mark.unit
class TestFillMissingStravaActivityCaloriesTask:
    """Tests for Strava calorie backfill task function."""

    @patch("app.integrations.strava.tasks.StravaActivitySyncStrategy")
    def test_updates_missing_calories(
        self,
        mock_strategy_class,
        test_db,
        test_user_with_strava_tokens,
    ):
        user_id = test_user_with_strava_tokens.id
        activity = Activity(
            id=8888,
            name="Needs Calories",
            distance=12000.0,
            moving_time=2400,
            elapsed_time=2500,
            total_elevation_gain=150.0,
            calories=None,
            owner_id=user_id,
        )
        test_db.add(activity)
        test_db.commit()

        mock_strategy = Mock()
        mock_strategy.is_connected.return_value = True
        mock_strategy.refresh_token_if_needed.return_value = None
        mock_strategy.fetch_activity_calories_batch.return_value = {8888: 555.0}
        mock_strategy_class.return_value = mock_strategy

        result = fill_missing_strava_activity_calories_task(
            user_id,
            [8888],
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
            activity_repository=ActivityRepository,
            activity_service=ActivityService,
        )

        assert result["status"] == "complete"
        assert result["activities_updated"] == 1
        test_db.refresh(activity)
        assert activity.calories == 555.0
        mock_strategy.fetch_activity_calories_batch.assert_called_once_with(
            test_user_with_strava_tokens,
            [8888],
        )


@pytest.mark.unit
class TestScheduleAllUserSyncsTask:
    """Tests for Strava scheduler dispatcher task function."""

    @patch("app.worker.sync_single_user_strava_activities_task.delay")
    def test_dispatches_connected_users(self, mock_delay, test_db, test_user_with_strava_tokens):
        result = schedule_all_user_syncs_task(
            db_session=db_session_context(test_db),
            user_repository=UserRepository,
        )

        assert result["status"] == "complete"
        assert result["dispatched_count"] >= 1
        mock_delay.assert_called()
