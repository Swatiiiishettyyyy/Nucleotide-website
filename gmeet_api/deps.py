"""
Dependencies for FastAPI routes.
"""
import sys
from pathlib import Path
from sqlalchemy.orm import Session

# Add parent directory to path to import shared database
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

try:
    # Try importing from parent database module
    from database import SessionLocal
except ImportError:
    # Fallback to local database (shouldn't happen in integrated setup)
    try:
        from .database import SessionLocal
    except ImportError:
        from database import SessionLocal


def get_db():
    """
    Database session dependency.
    Yields a database session and ensures it's closed after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

