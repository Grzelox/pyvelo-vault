"""Base repository with common database operations.

This module provides a generic base repository class that can be extended
for specific entity types.
"""

from typing import Generic, List, Optional, Type, TypeVar

from app.models.base import Base
from sqlalchemy.orm import Session

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Generic base repository for common CRUD operations.

    This class provides reusable database operations that work with any model type.
    """

    def __init__(self, model: Type[ModelType], db: Session):
        """Initialize the repository.

        Args:
            model: The SQLAlchemy model class
            db: Database session
        """
        self.model = model
        self.db = db

    def get_by_id(self, entity_id: int) -> Optional[ModelType]:
        """Get an entity by ID.

        Args:
            entity_id: The entity's ID

        Returns:
            Entity object if found, None otherwise
        """
        return self.db.query(self.model).filter(self.model.id == entity_id).first()

    def get_all(self) -> List[ModelType]:
        """Get all entities.

        Returns:
            List of all entities
        """
        return self.db.query(self.model).all()

    def create(self, entity: ModelType) -> ModelType:
        """Create a new entity.

        Args:
            entity: Model instance to create

        Returns:
            Created entity with ID populated
        """
        self.db.add(entity)
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def update(self, entity: ModelType) -> ModelType:
        """Update an existing entity.

        Args:
            entity: Model instance to update

        Returns:
            Updated entity
        """
        self.db.commit()
        self.db.refresh(entity)
        return entity

    def delete(self, entity: ModelType) -> None:
        """Delete an entity.

        Args:
            entity: Model instance to delete
        """
        self.db.delete(entity)
        self.db.commit()

    def count(self) -> int:
        """Get the total count of entities.

        Returns:
            Number of entities in the database
        """
        return self.db.query(self.model).count()
