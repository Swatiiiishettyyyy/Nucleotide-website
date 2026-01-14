from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import Optional
import logging

from .Product_model import Category, DEFAULT_CATEGORY_NAME

logger = logging.getLogger(__name__)


def get_or_create_default_category(db: Session) -> Category:
    """
    Ensure the default category (Genetic Testing) exists
    and return it.
    """
    category = (
        db.query(Category)
        .filter(Category.name.ilike(DEFAULT_CATEGORY_NAME))
        .first()
    )
    if category:
        return category

    category = Category(name=DEFAULT_CATEGORY_NAME)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category


def resolve_category(db: Session, category_id: Optional[int]) -> Category:
    """
    Return the requested category by ID, or the default one when ID is omitted.
    """
    if category_id is None:
        return get_or_create_default_category(db)

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        logger.warning(
            f"Category resolution failed - Category not found | Category ID: {category_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Category with id {category_id} does not exist.",
        )
    return category


def create_category(db: Session, name: str) -> Category:
    """
    Create a new category with the provided name.
    """
    name = name.strip()
    if not name:
        logger.warning(
            f"Category creation failed - Empty category name"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category name cannot be empty.",
        )

    existing = db.query(Category).filter(Category.name.ilike(name)).first()
    if existing:
        logger.warning(
            f"Category creation failed - Category already exists | Category Name: {name} | Existing ID: {existing.id}"
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{name}' already exists.",
        )

    category = Category(name=name)
    db.add(category)
    db.commit()
    db.refresh(category)
    return category

