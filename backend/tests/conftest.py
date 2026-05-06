"""Pytest configuration and shared fixtures.

This module provides reusable fixtures for all test modules,
including database setup, test client, and common test data.
"""

import os
import sys
from datetime import datetime, timezone

# Set testing mode BEFORE any app imports
os.environ["TESTING"] = "true"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Add the app directory to the Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from app.core import create_access_token, get_db, get_password_hash
from app.main import app
from app.models import Activity, Base, User


@pytest.fixture(scope="function")
def test_db_engine():
    """Create a SQLite in-memory database engine for testing.

    Returns:
        Engine: SQLAlchemy engine for test database
    """
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def test_db(test_db_engine):
    """Create a database session for testing.

    Args:
        test_db_engine: Test database engine

    Yields:
        Session: SQLAlchemy database session
    """
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(scope="function")
def client(test_db):
    """Create a test client for the FastAPI application.

    Args:
        test_db: Test database session

    Returns:
        TestClient: FastAPI test client
    """

    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    # Override get_db dependency
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def test_user(test_db):
    """Create a test user in the database.

    Args:
        test_db: Test database session

    Returns:
        User: Test user model instance
    """
    user = User(
        email="test@example.com",
        username="Test User",
        hashed_password=get_password_hash("testpassword"),
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_user_with_strava_tokens(test_db):
    """Create a test user with Strava OAuth tokens.

    Args:
        test_db: Test database session

    Returns:
        User: Test user with Strava tokens
    """
    user = User(
        email="strava@example.com",
        username="Strava User",
        hashed_password=get_password_hash("stravapassword"),
        strava_access_token="test_access_token",
        strava_refresh_token="test_refresh_token",
        strava_token_expires_at=datetime(2099, 12, 31, tzinfo=timezone.utc),
    )
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)
    return user


@pytest.fixture
def test_activities(test_db, test_user):
    """Create test activities for a user.

    Args:
        test_db: Test database session
        test_user: Test user to own the activities

    Returns:
        list: List of test activity model instances
    """
    activities = [
        Activity(
            name="Morning Ride",
            distance=15000.0,
            moving_time=3600,
            elapsed_time=3700,
            total_elevation_gain=200.0,
            calories=450.0,
            owner_id=test_user.id,
        ),
        Activity(
            name="Evening Ride",
            distance=25000.0,
            moving_time=5400,
            elapsed_time=5600,
            total_elevation_gain=350.0,
            calories=620.0,
            owner_id=test_user.id,
        ),
    ]
    test_db.add_all(activities)
    test_db.commit()
    for activity in activities:
        test_db.refresh(activity)
    return activities


@pytest.fixture
def auth_headers(test_user):
    """Create authentication headers with JWT token.

    Args:
        test_user: Test user to authenticate

    Returns:
        dict: Headers dictionary with Bearer token
    """
    token = create_access_token(data={"sub": test_user.email})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def test_user_data():
    """Sample user data for testing.

    Returns:
        dict: User registration data
    """
    return {
        "email": "newuser@example.com",
        "username": "New User",
        "password": "newpassword123",
    }


@pytest.fixture
def test_activity_data():
    """Sample activity data for testing.

    Returns:
        dict: Activity creation data
    """
    return {
        "name": "Test Activity",
        "distance": 10000.0,
        "moving_time": 2400,
        "elapsed_time": 2500,
        "total_elevation_gain": 150.0,
        "calories": 320.0,
    }
