"""Authentication endpoints."""

from datetime import timedelta

from app.core import ACCESS_TOKEN_EXPIRE_MINUTES, get_db
from app.repositories import UserRepository
from app.schemas import Token, User, UserCreate
from app.services import UserService
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

router = APIRouter()


@router.post("/register", response_model=User)
def register_user(user: UserCreate, db: Session = Depends(get_db)):
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


@router.post("/token", response_model=Token)
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
    user_repo = UserRepository(db)
    user_service = UserService(user_repo)

    user = user_service.authenticate(form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = user_service.create_access_token(user, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}
