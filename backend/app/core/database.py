"""Database connection and session management.

This module sets up SQLAlchemy database engine and session factory.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

# Only create engine and session if not in test mode
# Tests will create their own engine with SQLite
if os.getenv("TESTING") != "true":
    # Create database engine from connection URL
    engine = create_engine(settings.DATABASE_URL)

    # Session factory for creating database sessions
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    # Placeholder for tests
    engine = None
    SessionLocal = None
