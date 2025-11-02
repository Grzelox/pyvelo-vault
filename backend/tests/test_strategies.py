"""Tests for strategy pattern implementation."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, Mock, patch

import pytest
from app.integrations.strava.strategies import (
    ActivitySyncContext,
    ActivitySyncStrategy,
    StravaActivitySyncStrategy,
)
from app.models import User


@pytest.mark.unit
class TestStravaActivitySyncStrategy:
    """Tests for StravaActivitySyncStrategy."""

    def test_is_connected_true(self, test_user_with_strava_tokens):
        """Test is_connected returns True when user has Strava tokens."""
        strategy = StravaActivitySyncStrategy()

        assert strategy.is_connected(test_user_with_strava_tokens) is True

    def test_is_connected_false(self, test_user):
        """Test is_connected returns False when user has no Strava tokens."""
        strategy = StravaActivitySyncStrategy()

        assert strategy.is_connected(test_user) is False

    def test_is_connected_false_empty_token(self, test_db):
        """Test is_connected returns False with empty token."""
        user = models.User(
            email="empty@example.com",
            username="Empty Token",
            hashed_password="password",
            strava_access_token="",
        )
        test_db.add(user)
        test_db.commit()

        strategy = StravaActivitySyncStrategy()
        assert strategy.is_connected(user) is False

    @patch("strategies.StravaClientFactory.refresh_access_token")
    def test_refresh_token_if_needed_expired(self, mock_refresh, test_user_with_strava_tokens):
        """Test token refresh when token is expired."""
        # Set token to expired
        test_user_with_strava_tokens.strava_token_expires_at = datetime(
            2020, 1, 1, tzinfo=timezone.utc
        )

        # Mock the refresh response
        mock_refresh.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1735689600,  # Future timestamp
        }

        strategy = StravaActivitySyncStrategy()
        result = strategy.refresh_token_if_needed(test_user_with_strava_tokens)

        assert result is not None
        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"
        assert "expires_at" in result
        mock_refresh.assert_called_once()

    def test_refresh_token_if_needed_not_expired(self, test_user_with_strava_tokens):
        """Test token refresh when token is not expired."""
        # Set token to expire in future (make it timezone-aware)
        from datetime import datetime, timezone

        test_user_with_strava_tokens.strava_token_expires_at = datetime(
            2025, 12, 31, tzinfo=timezone.utc
        )

        strategy = StravaActivitySyncStrategy()
        result = strategy.refresh_token_if_needed(test_user_with_strava_tokens)

        assert result is None

    @patch("strategies.StravaClientFactory.create_authenticated_client")
    def test_fetch_activities(self, mock_create_client, test_user_with_strava_tokens):
        """Test fetching activities from Strava."""
        # Mock the Strava client and activities
        mock_client = Mock()
        mock_activity1 = Mock()
        mock_activity1.id = 1001
        mock_activity1.name = "Morning Ride"
        mock_activity1.distance = Mock(magnitude=15000.0)
        mock_activity1.moving_time = Mock(total_seconds=lambda: 3600)
        mock_activity1.elapsed_time = Mock(total_seconds=lambda: 3700)
        mock_activity1.total_elevation_gain = Mock(magnitude=250.0)

        mock_activity2 = Mock()
        mock_activity2.id = 1002
        mock_activity2.name = "Evening Ride"
        mock_activity2.distance = Mock(magnitude=20000.0)
        mock_activity2.moving_time = Mock(total_seconds=lambda: 4500)
        mock_activity2.elapsed_time = Mock(total_seconds=lambda: 4600)
        mock_activity2.total_elevation_gain = Mock(magnitude=300.0)

        mock_client.get_activities.return_value = [mock_activity1, mock_activity2]
        mock_create_client.return_value = mock_client

        strategy = StravaActivitySyncStrategy()
        activities = strategy.fetch_activities(test_user_with_strava_tokens)

        assert len(activities) == 2
        assert activities[0]["id"] == 1001
        assert activities[0]["name"] == "Morning Ride"
        assert activities[0]["distance"] == 15000.0
        assert activities[1]["id"] == 1002
        assert activities[1]["name"] == "Evening Ride"


@pytest.mark.unit
class TestActivitySyncContext:
    """Tests for ActivitySyncContext."""

    def test_context_initialization(self):
        """Test context initialization with strategy."""
        strategy = StravaActivitySyncStrategy()
        context = ActivitySyncContext(strategy)

        assert context.strategy == strategy

    def test_context_strategy_setter(self):
        """Test changing strategy at runtime."""
        strategy1 = StravaActivitySyncStrategy()
        strategy2 = StravaActivitySyncStrategy()

        context = ActivitySyncContext(strategy1)
        assert context.strategy == strategy1

        context.strategy = strategy2
        assert context.strategy == strategy2

    def test_sync_activities_not_connected(self, test_user):
        """Test sync when user is not connected to provider."""
        strategy = StravaActivitySyncStrategy()
        context = ActivitySyncContext(strategy)

        is_connected, activities, token_update = context.sync_activities(test_user)

        assert is_connected is False
        assert activities == []
        assert token_update is None

    @patch("strategies.StravaClientFactory.create_authenticated_client")
    @patch("strategies.StravaClientFactory.refresh_access_token")
    def test_sync_activities_success(
        self, mock_refresh, mock_create_client, test_user_with_strava_tokens
    ):
        """Test successful activity sync."""
        # Set token to expire in future (make it timezone-aware)
        from datetime import datetime, timezone

        test_user_with_strava_tokens.strava_token_expires_at = datetime(
            2025, 12, 31, tzinfo=timezone.utc
        )

        # Mock client
        mock_client = Mock()
        mock_activity = Mock()
        mock_activity.id = 1001
        mock_activity.name = "Test Ride"
        mock_activity.distance = Mock(magnitude=10000.0)
        mock_activity.moving_time = Mock(total_seconds=lambda: 3600)
        mock_activity.elapsed_time = Mock(total_seconds=lambda: 3700)
        mock_activity.total_elevation_gain = Mock(magnitude=200.0)

        mock_client.get_activities.return_value = [mock_activity]
        mock_create_client.return_value = mock_client

        strategy = StravaActivitySyncStrategy()
        context = ActivitySyncContext(strategy)

        is_connected, activities, token_update = context.sync_activities(
            test_user_with_strava_tokens
        )

        assert is_connected is True
        assert len(activities) == 1
        assert activities[0]["name"] == "Test Ride"
        # Token not expired, so no update
        assert token_update is None

    @patch("strategies.StravaClientFactory.create_authenticated_client")
    @patch("strategies.StravaClientFactory.refresh_access_token")
    def test_sync_activities_with_token_refresh(
        self, mock_refresh, mock_create_client, test_user_with_strava_tokens
    ):
        """Test activity sync with token refresh."""
        # Expire the token
        test_user_with_strava_tokens.strava_token_expires_at = datetime(
            2020, 1, 1, tzinfo=timezone.utc
        )

        # Mock refresh
        mock_refresh.return_value = {
            "access_token": "new_token",
            "refresh_token": "new_refresh",
            "expires_at": 1735689600,
        }

        # Mock client
        mock_client = Mock()
        mock_client.get_activities.return_value = []
        mock_create_client.return_value = mock_client

        strategy = StravaActivitySyncStrategy()
        context = ActivitySyncContext(strategy)

        is_connected, activities, token_update = context.sync_activities(
            test_user_with_strava_tokens
        )

        assert is_connected is True
        assert token_update is not None
        assert token_update["access_token"] == "new_token"
        assert token_update["refresh_token"] == "new_refresh"


@pytest.mark.unit
class TestActivitySyncStrategyInterface:
    """Tests for ActivitySyncStrategy abstract interface."""

    def test_strategy_is_abstract(self):
        """Test that ActivitySyncStrategy cannot be instantiated."""
        with pytest.raises(TypeError):
            ActivitySyncStrategy()

    def test_concrete_strategy_implements_interface(self):
        """Test that StravaActivitySyncStrategy implements the interface."""
        strategy = StravaActivitySyncStrategy()

        assert isinstance(strategy, ActivitySyncStrategy)
        assert hasattr(strategy, "is_connected")
        assert hasattr(strategy, "refresh_token_if_needed")
        assert hasattr(strategy, "fetch_activities")
