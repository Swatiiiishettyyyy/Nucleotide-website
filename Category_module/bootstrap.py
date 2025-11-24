import logging

from database import SessionLocal
from Product_module.category_service import get_or_create_default_category

logger = logging.getLogger(__name__)


def seed_default_categories() -> None:
    """
    Ensure required seed categories exist.
    Currently seeds the default 'Genetic Testing' category.
    """
    try:
        with SessionLocal() as session:
            get_or_create_default_category(session)
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.warning("Unable to seed default categories: %s", exc)

