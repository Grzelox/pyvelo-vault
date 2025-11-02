"""Tests for factory pattern implementations."""

from unittest.mock import Mock, patch

import pytest
from app.integrations.strava import StravaClientFactory
from stravalib.client import Client


@pytest.mark.unit
class TestStravaClientFactory:
    """Tests for StravaClientFactory."""

    def test_create_client(self):
        """Test creating a basic Strava client."""
        client = StravaClientFactory.create_client()

        assert isinstance(client, Client)
        assert client.access_token is None

    def test_create_authenticated_client(self):
        """Test creating an authenticated Strava client."""
        access_token = "test_access_token_123"
        client = StravaClientFactory.create_authenticated_client(access_token)

        assert isinstance(client, Client)
        assert client.access_token == access_token

    @patch.object(Client, "authorization_url")
    def test_get_authorization_url_default_scope(self, mock_auth_url):
        """Test getting authorization URL with default scope."""
        mock_auth_url.return_value = "https://strava.com/oauth/authorize?..."

        redirect_uri = "http://localhost:8000/callback"
        url = StravaClientFactory.get_authorization_url(redirect_uri)

        mock_auth_url.assert_called_once()
        call_kwargs = mock_auth_url.call_args[1]
        assert call_kwargs["redirect_uri"] == redirect_uri
        assert "read_all" in call_kwargs["scope"]
        assert "activity:read_all" in call_kwargs["scope"]

    @patch.object(Client, "authorization_url")
    def test_get_authorization_url_custom_scope(self, mock_auth_url):
        """Test getting authorization URL with custom scope."""
        mock_auth_url.return_value = "https://strava.com/oauth/authorize?..."

        redirect_uri = "http://localhost:8000/callback"
        custom_scope = ["read", "write"]
        url = StravaClientFactory.get_authorization_url(redirect_uri, custom_scope)

        mock_auth_url.assert_called_once()
        call_kwargs = mock_auth_url.call_args[1]
        assert call_kwargs["scope"] == custom_scope

    @patch.object(Client, "exchange_code_for_token")
    def test_exchange_code_for_token(self, mock_exchange):
        """Test exchanging authorization code for tokens."""
        mock_exchange.return_value = {
            "access_token": "new_access_token",
            "refresh_token": "new_refresh_token",
            "expires_at": 1735689600,
        }

        code = "authorization_code_123"
        result = StravaClientFactory.exchange_code_for_token(code)

        assert result["access_token"] == "new_access_token"
        assert result["refresh_token"] == "new_refresh_token"
        assert result["expires_at"] == 1735689600
        mock_exchange.assert_called_once()

    @patch.object(Client, "refresh_access_token")
    def test_refresh_access_token(self, mock_refresh):
        """Test refreshing an expired access token."""
        mock_refresh.return_value = {
            "access_token": "refreshed_access_token",
            "refresh_token": "refreshed_refresh_token",
            "expires_at": 1735689600,
        }

        refresh_token = "old_refresh_token"
        result = StravaClientFactory.refresh_access_token(refresh_token)

        assert result["access_token"] == "refreshed_access_token"
        assert result["refresh_token"] == "refreshed_refresh_token"
        mock_refresh.assert_called_once()

    def test_factory_methods_are_static(self):
        """Test that all factory methods are static."""
        # Should be able to call without instantiating
        client = StravaClientFactory.create_client()
        assert isinstance(client, Client)

        # Verify they're static methods
        assert isinstance(StravaClientFactory.__dict__["create_client"], staticmethod)
        assert isinstance(StravaClientFactory.__dict__["create_authenticated_client"], staticmethod)
        assert isinstance(StravaClientFactory.__dict__["get_authorization_url"], staticmethod)
        assert isinstance(StravaClientFactory.__dict__["exchange_code_for_token"], staticmethod)
        assert isinstance(StravaClientFactory.__dict__["refresh_access_token"], staticmethod)

    @patch.object(Client, "exchange_code_for_token")
    def test_exchange_code_uses_settings(self, mock_exchange):
        """Test that exchange_code_for_token uses settings credentials."""
        mock_exchange.return_value = {"access_token": "token"}

        code = "test_code"
        StravaClientFactory.exchange_code_for_token(code)

        # Verify it was called with client_id and client_secret
        call_kwargs = mock_exchange.call_args[1]
        assert "client_id" in call_kwargs
        assert "client_secret" in call_kwargs
        assert call_kwargs["code"] == code

    @patch.object(Client, "refresh_access_token")
    def test_refresh_uses_settings(self, mock_refresh):
        """Test that refresh_access_token uses settings credentials."""
        mock_refresh.return_value = {"access_token": "token"}

        refresh_token = "test_refresh"
        StravaClientFactory.refresh_access_token(refresh_token)

        # Verify it was called with credentials
        call_kwargs = mock_refresh.call_args[1]
        assert "client_id" in call_kwargs
        assert "client_secret" in call_kwargs
        assert call_kwargs["refresh_token"] == refresh_token
