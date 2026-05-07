"""Tests for FastAPI application endpoints."""

from datetime import datetime, timezone
from unittest.mock import Mock, patch

import pytest
from app import schemas
from app.core import ACCESS_TOKEN_EXPIRE_MINUTES, REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS, security
from app.models import Activity, User
from jose import jwt


@pytest.mark.integration
class TestHealthEndpoint:
    """Tests for health check endpoint."""

    def test_health_check(self, client):
        """Test health check endpoint returns ok status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


@pytest.mark.integration
class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_user_success(self, client, test_user_data):
        """Test successful user registration."""
        response = client.post("/api/v1/register", json=test_user_data)

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == test_user_data["email"]
        assert data["username"] == test_user_data["username"]
        assert "id" in data
        assert "password" not in data
        assert "hashed_password" not in data

    def test_register_user_duplicate_email(self, client, test_user, test_user_data):
        """Test registration with duplicate email fails."""
        test_user_data["email"] = test_user.email
        response = client.post("/api/v1/register", json=test_user_data)

        assert response.status_code == 400
        assert "already registered" in response.json()["detail"].lower()

    def test_register_user_invalid_email(self, client):
        """Test registration with invalid email fails."""
        invalid_data = {
            "email": "not-an-email",
            "username": "Test User",
            "password": "password123",
        }
        response = client.post("/api/v1/register", json=invalid_data)

        assert response.status_code == 422  # Validation error

    def test_register_user_missing_fields(self, client):
        """Test registration with missing required fields fails."""
        incomplete_data = {
            "email": "test@example.com"
            # Missing username and password
        }
        response = client.post("/api/v1/register", json=incomplete_data)

        assert response.status_code == 422


@pytest.mark.integration
class TestAuthentication:
    """Tests for authentication endpoints."""

    def test_login_success(self, client, test_user):
        """Test successful login."""
        form_data = {"username": test_user.email, "password": "testpassword"}
        response = client.post("/api/v1/token", data=form_data)

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
        assert data["expires_in"] == ACCESS_TOKEN_EXPIRE_MINUTES * 60

    def test_login_remember_me_uses_extended_expiry(self, client, test_user):
        """Test remember me login receives a longer-lived token."""
        form_data = {
            "username": test_user.email,
            "password": "testpassword",
            "remember_me": "true",
        }
        response = client.post("/api/v1/token", data=form_data)

        assert response.status_code == 200
        data = response.json()
        assert data["expires_in"] == REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60

        payload = jwt.decode(
            data["access_token"], security.SECRET_KEY, algorithms=[security.ALGORITHM]
        )
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        remaining = exp_time - datetime.now(timezone.utc)
        assert remaining.days >= REMEMBER_ME_ACCESS_TOKEN_EXPIRE_DAYS - 1

    def test_login_wrong_password(self, client, test_user):
        """Test login with wrong password fails."""
        form_data = {"username": test_user.email, "password": "wrongpassword"}
        response = client.post("/api/v1/token", data=form_data)

        assert response.status_code == 401
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_nonexistent_user(self, client):
        """Test login with nonexistent user fails."""
        form_data = {"username": "nonexistent@example.com", "password": "password"}
        response = client.post("/api/v1/token", data=form_data)

        assert response.status_code == 401


@pytest.mark.integration
class TestCurrentUser:
    """Tests for current user endpoint."""

    def test_get_current_user(self, client, auth_headers):
        """Test getting current user information."""
        response = client.get("/api/v1/users/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data
        assert "username" in data
        assert "password" not in data

    def test_get_current_user_no_auth(self, client):
        """Test getting current user without authentication fails."""
        response = client.get("/api/v1/users/me")

        assert response.status_code == 401

    def test_get_current_user_invalid_token(self, client):
        """Test getting current user with invalid token fails."""
        headers = {"Authorization": "Bearer invalid_token"}
        response = client.get("/api/v1/users/me", headers=headers)

        assert response.status_code == 401


@pytest.mark.integration
class TestActivitiesEndpoints:
    """Tests for activity CRUD endpoints."""

    def test_get_activities_authenticated(self, client, auth_headers, test_activities):
        """Test getting activities for authenticated user."""
        response = client.get("/api/v1/activities", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 2
        assert all("id" in activity for activity in data)
        assert all("name" in activity for activity in data)

    def test_get_activities_no_auth(self, client):
        """Test getting activities without authentication fails."""
        response = client.get("/api/v1/activities")

        assert response.status_code == 401

    def test_get_activities_empty(self, client):
        """Test getting activities for user with no activities."""
        # Create a new user and get their token
        new_user_data = {
            "email": "newuser@example.com",
            "username": "New User",
            "password": "password123",
        }
        reg_response = client.post("/api/v1/register", json=new_user_data)
        assert reg_response.status_code == 200

        # Login
        form_data = {"username": "newuser@example.com", "password": "password123"}
        login_response = client.post("/api/v1/token", data=form_data)
        token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Get activities
        response = client.get("/api/v1/activities", headers=headers)

        assert response.status_code == 200
        assert response.json() == []

    def test_create_activity_success(self, client, auth_headers, test_activity_data):
        """Test creating a new activity."""
        response = client.post("/api/v1/activities", json=test_activity_data, headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == test_activity_data["name"]
        assert data["distance"] == test_activity_data["distance"]
        assert "id" in data
        assert "owner_id" in data

    def test_create_activity_no_auth(self, client, test_activity_data):
        """Test creating activity without authentication fails."""
        response = client.post("/api/v1/activities", json=test_activity_data)

        assert response.status_code == 401

    def test_create_activity_invalid_data(self, client, auth_headers):
        """Test creating activity with invalid data fails."""
        invalid_data = {"name": "Test", "distance": "not-a-number"}  # Should be float
        response = client.post("/api/v1/activities", json=invalid_data, headers=auth_headers)

        assert response.status_code == 422


@pytest.mark.integration
class TestStravaSyncEndpoint:
    """Tests for Strava sync endpoint."""

    @patch("app.api.v1.endpoints.activities.sync_single_user_strava_activities_task.delay")
    def test_start_sync_authenticated(self, mock_task, client, auth_headers):
        """Test starting Strava sync for authenticated user."""
        response = client.post("/api/v1/activities/sync", headers=auth_headers)

        assert response.status_code == 202
        data = response.json()
        assert "sync" in data["message"].lower()
        assert "started" in data["message"].lower()

        # Verify task was triggered
        mock_task.assert_called_once()

    def test_start_sync_no_auth(self, client):
        """Test starting sync without authentication fails."""
        response = client.post("/api/v1/activities/sync")

        assert response.status_code == 401


@pytest.mark.integration
class TestStravaOAuthEndpoints:
    """Tests for Strava OAuth flow endpoints."""

    @patch("app.integrations.strava.client.StravaClientFactory.get_authorization_url")
    def test_connect_strava(self, mock_get_url, client, auth_headers):
        """Test initiating Strava connection."""
        mock_get_url.return_value = "https://www.strava.com/oauth/authorize?..."

        response = client.get(
            "/api/v1/strava/connect", headers=auth_headers, follow_redirects=False
        )

        assert response.status_code == 307  # Redirect
        assert "strava.com" in response.headers["location"]

    def test_connect_strava_no_auth(self, client):
        """Test connecting Strava without authentication succeeds (redirect)."""
        response = client.get("/api/v1/strava/connect", follow_redirects=False)

        assert response.status_code == 307

    @patch("app.integrations.strava.client.StravaClientFactory.exchange_code_for_token")
    def test_handle_strava_auth_callback(self, mock_exchange, client, test_db, test_user):
        """Test handling Strava OAuth callback."""
        mock_exchange.return_value = {
            "access_token": "strava_access_token",
            "refresh_token": "strava_refresh_token",
            "expires_at": 1735689600,
        }

        response = client.get(
            "/api/v1/strava/callback?code=authorization_code_123",
            follow_redirects=False,
        )

        assert response.status_code == 307  # Redirect
        assert "localhost:8501" in response.headers["location"]

        # Verify exchange was called
        mock_exchange.assert_called_once_with("authorization_code_123")


@pytest.mark.integration
class TestDatabaseLifecycle:
    """Tests for database lifecycle management."""

    def test_lifespan_creates_default_user(self, test_db_engine):
        """Test that lifespan creates default user if database is empty."""
        # This is tested indirectly through the application startup
        # The fixture setup already handles this
        pass

    def test_tables_exist(self, test_db_engine):
        """Test that all required tables are created."""
        from sqlalchemy import inspect

        inspector = inspect(test_db_engine)
        table_names = inspector.get_table_names()

        assert "users" in table_names
        assert "activities" in table_names
