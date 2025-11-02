"""User repository for data access operations."""

from typing import Optional

from app.models import User
from sqlalchemy.orm import Session

from .base import BaseRepository


class UserRepository(BaseRepository[User]):
    """Repository for User entity operations."""

    def __init__(self, db: Session):
        """Initialize the repository with a database session.

        Args:
            db: SQLAlchemy database session
        """
        super().__init__(User, db)

    def get_by_email(self, email: str) -> Optional[User]:
        """Get a user by email address.

        Args:
            email: The user's email address

        Returns:
            User object if found, None otherwise
        """
        return self.db.query(User).filter(User.email == email).first()

    def get_latest(self) -> Optional[User]:
        """Get the most recently created user.

        Returns:
            User object if any exist, None otherwise
        """
        return self.db.query(User).order_by(User.id.desc()).first()
