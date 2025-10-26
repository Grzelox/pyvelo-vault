"""Main FastAPI application for pyvelo-vault API.

This module defines the FastAPI application, including all API endpoints,
database lifecycle management, and dependency injection.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import List

import auth
import models
import schemas
import tasks
from celery_app import celery
from database import SessionLocal, engine
from factories import StravaClientFactory
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from repositories import ActivityRepository, UserRepository
from services import ActivityService, UserService
from settings import settings
from sqlalchemy.orm import Session
from stravalib.client import Client

# Create all tables defined in models.py in the database
models.Base.metadata.create_all(bind=engine)


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
    db = SessionLocal()

    # Create default user if none exists
    if db.query(models.User).count() == 0:
        print("Creating default user...")
        default_user = models.User(
            email="demo@pyvelo-vault.com",
            username="Demo User",
            hashed_password=auth.get_password_hash("demo123"),
        )
        db.add(default_user)
        db.commit()
        db.refresh(default_user)

        # Seed activities for the default user
        print("Seeding activities for default user...")
        mock_activities = [
            models.Activity(
                name="Morning Gravel Ride",
                distance=35200,
                moving_time=5400,
                elapsed_time=5600,
                total_elevation_gain=450,
                owner_id=default_user.id,
            ),
            models.Activity(
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
        print("Database already contains data.")

    db.close()
    yield


app = FastAPI(
    title="pyvelo-vault API",
    description="A self-hosted cycling activity tracking and analytics platform",
    version="0.1.0",
    lifespan=lifespan,
)


def get_db():
    """Database session dependency.

    This dependency function provides a database session to API endpoints.
    It ensures proper session cleanup after each request.

    Yields:
        Session: SQLAlchemy database session
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@app.post("/api/v1/register", response_model=schemas.User, tags=["Authentication"])
def register_user(user: schemas.UserCreate, db: Session = Depends(get_db)):
    """Register a new user account.

    Creates a new user with the provided email, username, and password.
    Password is securely hashed before storage. Uses Service Layer pattern.

    Args:
        user: User registration data
        db: Database session (injected dependency)

    Returns:
        Created user object (without password)

    Raises:
        HTTPException: If email is already registered
    """
    # Use repository and service patterns
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    try:
        return user_service.register_user(user)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/v1/token", response_model=schemas.Token, tags=["Authentication"])
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """Login and receive a JWT access token.

    Authenticates user with email/username and password, returns a JWT token
    that must be included in subsequent requests.

    Args:
        form_data: OAuth2 form with username and password
        db: Database session (injected dependency)

    Returns:
        JWT access token and token type

    Raises:
        HTTPException: If credentials are invalid
    """
    user = auth.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=auth.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = auth.create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.get("/api/v1/users/me", response_model=schemas.User, tags=["Users"])
async def read_users_me(current_user: models.User = Depends(auth.get_current_user)):
    """Get current authenticated user information.

    Returns the profile information of the currently logged-in user.

    Args:
        current_user: Current authenticated user (injected dependency)

    Returns:
        User object
    """
    return current_user


@app.get("/api/v1/health", tags=["System"])
def get_health():
    """Health check endpoint.

    Returns the current health status of the API service.

    Returns:
        dict: A dictionary with the status of the service
    """
    return {"status": "ok"}


@app.get("/api/v1/activities", tags=["Activities"], response_model=List[schemas.Activity])
def get_activities(
    current_user: models.User = Depends(auth.get_current_user), db: Session = Depends(get_db)
):
    """Retrieve all activities for the current user.

    Returns a list of all cycling activities belonging to the authenticated user.
    Uses Repository and Service patterns for data access.

    Args:
        current_user: Current authenticated user (injected dependency)
        db: Database session (injected dependency)

    Returns:
        List[schemas.Activity]: List of user's activities
    """
    # Use repository and service patterns
    activity_repo = ActivityRepository(db)
    activity_service = ActivityService(activity_repo)

    return activity_service.get_user_activities(current_user.id)


@app.post("/api/v1/activities", tags=["Activities"], response_model=schemas.Activity)
def create_activity(
    activity: schemas.ActivityCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """Create a new activity for the current user.

    Uses Service Layer pattern to handle business logic.

    Args:
        activity: Activity data
        current_user: Current authenticated user (injected dependency)
        db: Database session (injected dependency)

    Returns:
        Created activity object
    """
    # Use repository and service patterns
    activity_repo = ActivityRepository(db)
    activity_service = ActivityService(activity_repo)

    return activity_service.create_activity(activity, current_user.id)


@app.post("/api/v1/sync", status_code=202, tags=["Activities"])
def start_sync(current_user: models.User = Depends(auth.get_current_user)):
    """Trigger a background task to sync Strava activities for the current user.

    This endpoint schedules a background job that fetches activities from
    the Strava API and saves them to the database.

    Args:
        current_user: Current authenticated user (injected dependency)

    Returns:
        dict: A message indicating the sync has been started
    """
    tasks.sync_strava_activities_task.delay(user_id=current_user.id)
    return {"message": "Strava activity sync has been started."}


@app.get("/connect/strava", tags=["Strava"])
def connect_strava(current_user: models.User = Depends(auth.get_current_user)):
    """Redirect the user to Strava's authorization page.

    This initiates the OAuth2 flow by redirecting the user to Strava where they
    can authorize this application to access their data. Uses Factory pattern.

    Args:
        current_user: Current authenticated user (injected dependency)

    Returns:
        RedirectResponse: Redirect to Strava's authorization page
    """
    # Use Factory pattern for Strava client creation
    authorize_url = StravaClientFactory.get_authorization_url(
        redirect_uri="http://localhost:8000/auth/strava"
    )
    return RedirectResponse(authorize_url)


@app.get("/auth/strava", tags=["Strava"])
def handle_strava_auth(code: str, db: Session = Depends(get_db)):
    """Handle the OAuth2 callback from Strava.

    This endpoint receives the authorization code from Strava, exchanges it
    for access and refresh tokens, and stores them in the database.
    Uses Factory, Repository, and Service patterns.

    Note: This is a simplified implementation. In production, you should use
    the 'state' parameter to associate the callback with the correct user session.
    For this milestone, we update the most recently created user.

    Args:
        code: Authorization code from Strava
        db: Database session (injected dependency)

    Returns:
        RedirectResponse: Redirect back to the frontend
    """
    # Use Factory pattern to exchange code for tokens
    token_response = StravaClientFactory.exchange_code_for_token(code)

    # Use Repository and Service patterns for data access
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    # For this simple milestone, we update the latest user
    # In production, use the state parameter to identify the correct user
    user_to_update = user_repo.get_latest()

    if user_to_update:
        user_service.update_strava_tokens(
            user_to_update,
            token_response["access_token"],
            token_response["refresh_token"],
            datetime.fromtimestamp(token_response["expires_at"], tz=timezone.utc),
        )

    # Redirect user back to the frontend
    return RedirectResponse("http://localhost:8501")
