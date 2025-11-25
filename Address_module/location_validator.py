from functools import lru_cache
from pathlib import Path
from typing import Optional, Set
import logging

logger = logging.getLogger(__name__)

try:
    from openpyxl import load_workbook
except ImportError:  # pragma: no cover
    load_workbook = None  # type: ignore
    logger.error("openpyxl is required to read Locations.xlsx. Please install it.")


LOCATIONS_FILE = Path(__file__).resolve().parents[1] / "Locations.xlsx"


@lru_cache(maxsize=1)
def _load_serviceable_locations() -> Set[str]:
    """Load allowed locations (cities/localities) from Locations.xlsx."""
    allowed: Set[str] = set()
    if load_workbook is None:
        return allowed

    if not LOCATIONS_FILE.exists():
        logger.error("Locations.xlsx file not found at %s", LOCATIONS_FILE)
        return allowed

    try:
        workbook = load_workbook(LOCATIONS_FILE, read_only=True, data_only=True)
    except Exception as exc:  # pragma: no cover
        logger.error("Failed to read Locations.xlsx: %s", exc)
        return allowed

    sheet = workbook.active
    header_row = next(sheet.iter_rows(min_row=1, max_row=1, values_only=True), None)
    if not header_row:
        logger.error("Locations.xlsx is empty.")
        return allowed

    headers = [str(cell).strip().lower() if cell is not None else "" for cell in header_row]
    try:
        location_idx = headers.index("location")
    except ValueError:
        logger.error("'Location' column not found in Locations.xlsx headers.")
        return allowed

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row:
            continue
        value = row[location_idx]
        if value:
            normalized = str(value).strip().lower()
            if normalized:
                allowed.add(normalized)

    logger.info("Loaded %d serviceable locations from Locations.xlsx", len(allowed))
    return allowed


def is_serviceable_location(city: Optional[str], locality: Optional[str]) -> bool:
    """Return True if locality or city is present in the Locations.xlsx list."""
    allowed = _load_serviceable_locations()
    if not allowed:
        # If file missing or empty, be conservative and reject.
        return False

    def normalize(value: Optional[str]) -> Optional[str]:
        return value.strip().lower() if isinstance(value, str) and value.strip() else None

    normalized_locality = normalize(locality)
    normalized_city = normalize(city)

    if normalized_locality and normalized_locality in allowed:
        return True
    if normalized_city and normalized_city in allowed:
        return True
    return False


