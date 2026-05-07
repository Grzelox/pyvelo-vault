"""Authentication token schemas."""

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """JWT token response."""

    access_token: str
    token_type: str
    expires_in: int


class TokenData(BaseModel):
    """Data extracted from JWT token."""

    email: Optional[str] = None
