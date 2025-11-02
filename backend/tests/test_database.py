"""Tests for database connection and session management."""

import pytest
from app.models import Activity, Base, User
from sqlalchemy import inspect
from sqlalchemy.orm import Session


@pytest.mark.unit
class TestDatabaseModule:
    """Tests for database configuration and setup."""

    def test_base_is_declarative_base(self):
        """Test that Base is a declarative base."""
        assert hasattr(Base, "metadata")
        # Base class itself doesn't have __tablename__, only derived classes do
        assert hasattr(Base, "registry")

    def test_models_use_base(self):
        """Test that models inherit from Base."""
        assert issubclass(User, Base)
        assert issubclass(Activity, Base)

    def test_session_local_creates_sessions(self, test_db_engine):
        """Test that SessionLocal can create database sessions."""
        # Create a new session factory for testing
        from sqlalchemy.orm import sessionmaker

        TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_db_engine)

        session = TestSessionLocal()
        assert isinstance(session, Session)
        session.close()

    def test_database_tables_created(self, test_db_engine):
        """Test that all expected tables are created."""
        inspector = inspect(test_db_engine)
        table_names = inspector.get_table_names()

        assert "users" in table_names
        assert "activities" in table_names

    def test_user_table_columns(self, test_db_engine):
        """Test that users table has expected columns."""
        inspector = inspect(test_db_engine)
        columns = [col["name"] for col in inspector.get_columns("users")]

        expected_columns = [
            "id",
            "email",
            "username",
            "hashed_password",
            "created_at",
            "strava_access_token",
            "strava_refresh_token",
            "strava_token_expires_at",
        ]

        for col in expected_columns:
            assert col in columns

    def test_activity_table_columns(self, test_db_engine):
        """Test that activities table has expected columns."""
        inspector = inspect(test_db_engine)
        columns = [col["name"] for col in inspector.get_columns("activities")]

        expected_columns = [
            "id",
            "name",
            "distance",
            "moving_time",
            "elapsed_time",
            "total_elevation_gain",
            "owner_id",
        ]

        for col in expected_columns:
            assert col in columns

    def test_foreign_key_relationship(self, test_db_engine):
        """Test that foreign key relationship exists between tables."""
        inspector = inspect(test_db_engine)
        foreign_keys = inspector.get_foreign_keys("activities")

        assert len(foreign_keys) > 0
        fk = foreign_keys[0]
        assert fk["referred_table"] == "users"
        assert "owner_id" in fk["constrained_columns"]
