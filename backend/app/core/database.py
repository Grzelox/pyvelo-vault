"""Database connection and session management.

This module sets up SQLAlchemy database engine and session factory.
"""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from .config import settings

if os.getenv("TESTING") != "true":
    engine = create_engine(settings.DATABASE_URL)

    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    engine = None
    SessionLocal = None
