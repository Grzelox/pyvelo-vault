"""Database connection and session management.

This module sets up SQLAlchemy database engine, session factory,
and declarative base for ORM models.
"""

from settings import settings
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Create database engine from connection URL
engine = create_engine(settings.DATABASE_URL)

# Session factory for creating database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all ORM models
Base = declarative_base()
