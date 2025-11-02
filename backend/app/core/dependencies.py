"""Common FastAPI dependencies.

This module contains dependency functions used across API endpoints.
"""

from typing import Generator

from app.models import User
from app.schemas import TokenData
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from .database import SessionLocal
from .security import decode_token

# OAuth2 scheme for token authentication
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/token")


def get_db() -> Generator[Session, None, None]:
    """Database session dependency.

    This dependency function provides a database session to API endpoints.
    It ensures proper session cleanup after each request.

    Yields:
        Session: SQLAlchemy database session
    """
    if SessionLocal is None:
        # In test mode, this will be overridden by the test client
        raise RuntimeError("Database not configured. Are you in test mode?")
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
) -> User:
    """Get the current authenticated user from JWT token.

    This dependency can be used in any endpoint that requires authentication.

    Args:
        token: JWT token from Authorization header
        db: Database session

    Returns:
        User object of the authenticated user

    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    email: str = payload.get("sub")
    if email is None:
        raise credentials_exception

    token_data = TokenData(email=email)

    user = db.query(User).filter(User.email == token_data.email).first()
    if user is None:
        raise credentials_exception
    return user
