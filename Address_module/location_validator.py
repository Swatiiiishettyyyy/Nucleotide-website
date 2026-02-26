from typing import Optional, Set
import logging

from sqlalchemy.orm import Session

from .Address_model import ServiceableLocation

logger = logging.getLogger(__name__)


def _load_serviceable_locations_from_db(db: Session) -> Set[str]:
    """Load allowed locations (cities/localities) from serviceable_locations table."""
    allowed: Set[str] = set()
    try:
        rows = db.query(ServiceableLocation.location).all()
        for (value,) in rows:
            if value:
                normalized = str(value).strip().lower()
                if normalized:
                    allowed.add(normalized)
    except Exception as exc:
        logger.error("Failed to read serviceable_locations table: %s", exc)
        return allowed
    logger.info("Loaded %d serviceable locations from database", len(allowed))
    return allowed


def is_serviceable_location(city: Optional[str], locality: Optional[str], db: Session) -> bool:
    """
    Return True if city name is present in the serviceable_locations table.
    Only city name is validated.
    """
    allowed = _load_serviceable_locations_from_db(db)
    if not allowed:
        logger.warning("Serviceable locations table is empty. Rejecting all locations.")
        return False

    def normalize(value: Optional[str]) -> Optional[str]:
        if not value:
            return None
        if not isinstance(value, str):
            return None
        normalized = value.strip().lower()
        return normalized if normalized else None

    normalized_city = normalize(city)

    logger.info("Validating city name - City: '%s' (normalized: '%s')", city, normalized_city)
    logger.info("Total serviceable locations loaded: %d", len(allowed))

    if normalized_city:
        if normalized_city in allowed:
            logger.info("City '%s' (normalized: '%s') found in serviceable locations.", city, normalized_city)
            return True
        logger.warning("City '%s' (normalized: '%s') NOT found in serviceable locations.", city, normalized_city)
        similar = [loc for loc in allowed if normalized_city in loc or loc in normalized_city]
        if similar:
            logger.info("Similar city names found in serviceable locations: %s", similar[:5])

    logger.warning("Location validation failed - City: '%s' (normalized: '%s')", city, normalized_city)
    return False
