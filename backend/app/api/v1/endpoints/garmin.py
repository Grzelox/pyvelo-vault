"""Garmin Connect integration endpoints (python-garminconnect).

Uses standard FastAPI dependency injection (not the DI container).
The container is reserved for Celery tasks and other non-request contexts.
"""

from __future__ import annotations

from app.core import get_current_user, get_db
from app.integrations.garmin import GarminClientFactory
from app.models import User
from app.repositories import UserRepository
from app.services import UserService
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

router = APIRouter()


class GarminConnectRequest(BaseModel):
    """Request body for connecting a Garmin Connect account.

    We use credentials only for the initial login to create a tokenstore,
    then discard them and persist tokens on disk.
    """

    email: EmailStr
    password: str = Field(min_length=1)


@router.post("/connect")
def connect_garmin(
    payload: GarminConnectRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Connect Garmin account and persist per-user tokenstore."""
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    try:
        _api, tokenstore_dir = GarminClientFactory.login_with_credentials_and_store_tokens(
            user_id=current_user.id,
            email=str(payload.email),
            password=payload.password,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Garmin login failed: {e}")

    # Store tokenstore path in garmin_access_token field (repurposed).
    user_service.update_garmin_tokens(
        current_user,
        access_token=tokenstore_dir,
        refresh_token=None,
        expires_at=None,
        garmin_user_id=None,
    )

    return {"message": "Garmin account connected successfully"}


@router.post("/disconnect")
def disconnect_garmin(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Disconnect Garmin account from the user."""
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)
    user_service.disconnect_garmin(current_user)
    return {"message": "Garmin account disconnected successfully"}
