"""Base model with common fields and utilities.

This module defines the SQLAlchemy declarative base and common model patterns.
"""

from sqlalchemy.ext.declarative import declarative_base

# Base class for all ORM models
Base = declarative_base()
