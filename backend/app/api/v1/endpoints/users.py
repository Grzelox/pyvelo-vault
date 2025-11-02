"""User endpoints."""

from app.core import get_current_user
from app.models import User
from app.schemas import User as UserSchema
from fastapi import APIRouter, Depends

router = APIRouter()


@router.get("/me", response_model=UserSchema)
async def read_users_me(current_user: User = Depends(get_current_user)):
    """Get current authenticated user information.

    Returns the profile information of the currently logged-in user.

    Args:
        current_user: Current authenticated user (injected dependency)

    Returns:
        User object
    """
    return current_user
