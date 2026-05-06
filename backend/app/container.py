"""Dependency Injector container.

We use Dependency Injector to centralize object assembly and make it easy to
override dependencies in tests or alternate deployments.

FastAPI endpoints continue to use FastAPI's built-in DI for request-scoped
dependencies (db sessions, current user). This container is used for:
- Celery background tasks
- Integration strategies
- Any non-request context where DI is beneficial

Docs: https://python-dependency-injector.ets-labs.org/introduction/di_in_python.html
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

from app.core.config import settings
from app.core.database import SessionLocal
from app.integrations.garmin.client import GarminClientFactory
from app.integrations.strava.client import StravaClientFactory
from app.repositories import ActivityRepository, UserRepository
from app.services import ActivityService, UserService
from dependency_injector import containers, providers
from sqlalchemy.orm import Session


@contextmanager
def create_db_session() -> Generator[Session, None, None]:
    """Create a database session for use outside request context.

    This is used by Celery tasks and other non-request contexts.
    The session is properly closed after use.

    Yields:
        SQLAlchemy database session
    """
    if SessionLocal is None:
        raise RuntimeError("Database not configured")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class Container(containers.DeclarativeContainer):
    """Application dependency container.

    This container provides dependencies for non-FastAPI contexts:
    - Celery background tasks use db_session Resource
    - Strategies and services can be injected where needed
    """

    wiring_config = containers.WiringConfiguration(
        modules=[
            # Celery tasks - main users of DI outside FastAPI
            "app.integrations.strava.tasks",
            "app.integrations.garmin.tasks",
        ]
    )

    config = providers.Object(settings)

    # Database session as a Resource (for Celery tasks / background jobs)
    # Usage: with container.db_session() as session: ...
    db_session = providers.Resource(create_db_session)

    # External integration factories (stateless helpers)
    strava_client_factory = providers.Object(StravaClientFactory)
    garmin_client_factory = providers.Object(GarminClientFactory)

    # Repositories - require a db session, provided as Factory
    # In tasks, pass the session explicitly: container.user_repository(db=session)
    user_repository = providers.Factory(UserRepository)
    activity_repository = providers.Factory(ActivityRepository)

    # Services - require repositories
    user_service = providers.Factory(UserService)
    activity_service = providers.Factory(
        ActivityService,
        activity_repo=activity_repository,
    )


# Global container instance - initialized in main.py / worker.py
container = Container()
