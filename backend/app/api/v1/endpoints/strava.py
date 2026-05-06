"""Strava OAuth and integration endpoints.

Uses standard FastAPI dependency injection (not the DI container).
The container is reserved for Celery tasks and other non-request contexts.
"""

from datetime import datetime, timezone

from app.core import get_current_user, get_db
from app.core.config import settings
from app.integrations.strava import StravaClientFactory
from app.models import User
from app.repositories import UserRepository
from app.services import UserService
from fastapi import APIRouter, Depends, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

router = APIRouter()


@router.get("/connect")
def connect_strava(
    user_id: int = Query(None, description="User ID for OAuth state tracking"),
):
    """Redirect the user to Strava's authorization page.

    This initiates the OAuth2 flow by redirecting the user to Strava where they
    can authorize this application to access their data. Uses Factory pattern.

    Note: Authentication is not required for this endpoint as it's accessed via
    browser redirect. The user_id can be passed as a query parameter and will be
    included in the OAuth state parameter for tracking.

    Args:
        user_id: Optional user ID to track through OAuth flow

    Returns:
        RedirectResponse: Redirect to Strava's authorization page
    """
    # Use Factory pattern for Strava client creation
    # Include user_id in state parameter if provided
    state = str(user_id) if user_id else "default"
    authorize_url = StravaClientFactory.get_authorization_url(
        redirect_uri=settings.STRAVA_REDIRECT_URI, state=state
    )
    return RedirectResponse(authorize_url)


@router.get("/callback")
def handle_strava_callback(
    code: str,
    state: str = Query(None, description="OAuth state parameter for user tracking"),
    db: Session = Depends(get_db),
):
    """Handle the OAuth2 callback from Strava.

    This endpoint receives the authorization code from Strava, exchanges it
    for access and refresh tokens, and stores them in the database.
    Uses Factory, Repository, and Service patterns.

    The state parameter is used to identify which user initiated the OAuth flow.
    If state contains a user ID, that user is updated. Otherwise, the most
    recently created user is updated (for backward compatibility).

    Args:
        code: Authorization code from Strava
        state: OAuth state parameter containing user ID
        db: Database session (injected dependency)

    Returns:
        RedirectResponse: Redirect back to the frontend
    """
    # Use Factory pattern to exchange code for tokens
    token_response = StravaClientFactory.exchange_code_for_token(code)

    # Use Repository and Service patterns for data access
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    # Try to get user from state parameter, otherwise use latest user
    user_to_update = None
    if state and state != "default":
        try:
            user_id = int(state)
            user_to_update = user_repo.get_by_id(user_id)
        except (ValueError, TypeError):
            pass

    # Fallback to latest user if state didn't contain a valid user ID
    if not user_to_update:
        user_to_update = user_repo.get_latest()

    if user_to_update:
        athlete_id = token_response.get("athlete", {}).get("id")
        user_service.update_strava_tokens(
            user_to_update,
            token_response["access_token"],
            token_response["refresh_token"],
            datetime.fromtimestamp(token_response["expires_at"], tz=timezone.utc),
            athlete_id=athlete_id,
        )

    # Redirect user back to the frontend
    return RedirectResponse(settings.FRONTEND_URL)


@router.post("/disconnect")
def disconnect_strava(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect Strava account from the user.

    This endpoint removes all Strava OAuth tokens and athlete information
    from the user's account, effectively disconnecting their Strava integration.

    Args:
        current_user: Currently authenticated user (injected dependency)
        db: Database session (injected dependency)

    Returns:
        dict: Success message
    """
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    # Clear Strava tokens and athlete info
    user_service.disconnect_strava(current_user)

    return {"message": "Strava account disconnected successfully"}
