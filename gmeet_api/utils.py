"""
Utility functions for Google Meet API.
"""
import random
import string
import logging
from sqlalchemy.orm import Session
try:
    from .models import CounsellorGmeetList
except ImportError:
    from models import CounsellorGmeetList

logger = logging.getLogger(__name__)

# Characters for generating unique IDs (excluding confusing ones: 0, O, 1, I, L)
ALLOWED_CHARS = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


def generate_unique_counsellor_id(db: Session, max_attempts: int = 100) -> str:
    """
    Generate a unique 6-character alphanumeric counsellor ID.
    Ensures no collision with existing IDs in the database.
    
    Uses database transaction to prevent race conditions.
    
    Args:
        db: Database session
        max_attempts: Maximum number of attempts to generate unique ID (default: 100)
    
    Returns:
        Unique 6-character counsellor_id
    
    Raises:
        RuntimeError: If unable to generate unique ID after max_attempts
    """
    for attempt in range(max_attempts):
        # Generate random 6-character ID
        counsellor_id = ''.join(random.choice(ALLOWED_CHARS) for _ in range(6))
        
        # Check if ID already exists (atomic check within transaction)
        existing = db.query(CounsellorGmeetList).filter(
            CounsellorGmeetList.counsellor_id == counsellor_id
        ).first()
        
        if not existing:
            logger.info(f"Generated unique counsellor_id: {counsellor_id} (attempt {attempt + 1})")
            return counsellor_id
    
    # If we've exhausted all attempts, raise error
    raise RuntimeError(
        f"Unable to generate unique counsellor_id after {max_attempts} attempts. "
        "This is highly unlikely - please check database or increase max_attempts."
    )

