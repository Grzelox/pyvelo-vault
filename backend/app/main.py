"""Main FastAPI application for pyvelo-vault API.

This module defines the FastAPI application and includes all API routers.
Database lifecycle and seeding are handled in the lifespan context manager.
"""

import os
from contextlib import asynccontextmanager

from app.api.v1 import api_router
from app.container import Container
from app.core import engine, get_logger, get_password_hash
from app.core.database import SessionLocal
from app.models import Activity, Base, User
from fastapi import FastAPI

# Configure module logger
logger = get_logger(__name__)

# Create all tables defined in models in the database (skip in test mode)
if os.getenv("TESTING") != "true" and engine is not None:
    Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle events.

    This context manager handles startup and shutdown events for the FastAPI
    application. On startup, it creates a default user and seeds activities
    if the database is empty.

    Args:
        app: The FastAPI application instance

    Yields:
        None: Control returns to the application during its runtime
    """
    # Skip database initialization in test mode
    if os.getenv("TESTING") == "true" or SessionLocal is None:
        yield
        return

    db = SessionLocal()

    # Create default user if none exists
    if db.query(User).count() == 0:
        logger.info("Creating default user...")
        default_user = User(
            email="demo@pyvelo-vault.com",
            username="Demo User",
            hashed_password=get_password_hash("demo123"),
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)

        # Seed activities for the default user
        logger.info("Seeding activities for default user...")
        mock_activities = [
            Activity(
                name="Morning Gravel Ride",
                distance=35200,
                moving_time=5400,
                elapsed_time=5600,
                total_elevation_gain=450,
                owner_id=default_user.id,
            ),
            Activity(
                name="Lunchtime Virtual Ride",
                distance=25000,
                moving_time=3600,
                elapsed_time=3650,
                total_elevation_gain=150,
                owner_id=default_user.id,
            ),
        ]
        db.add_all(mock_activities)
        db.commit()
    else:
        logger.info("Database already contains data.")

    db.close()
    yield


# Create FastAPI application
app = FastAPI(
    title="pyvelo-vault API",
    description="A self-hosted cycling activity tracking and analytics platform",
    version="0.1.0",
    lifespan=lifespan,
)

# Dependency Injector container (used for wiring dependencies in endpoints)
container = Container()
container.wire()
app.container = container  # type: ignore[attr-defined]

# Include API v1 router
app.include_router(api_router, prefix="/api/v1")
