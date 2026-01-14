from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from typing import Optional
from .user_model import User
from Audit_module.Profile_audit_crud import log_profile_update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)


def get_user_by_mobile(db: Session, mobile: str) -> Optional[User]:
    """
    Retrieve user by mobile number.
    Searches for plain text phone number match.
    """
    # Normalize mobile number for comparison
    mobile_normalized = str(mobile).strip() if mobile else ""
    
    # Search for exact match
    user = db.query(User).filter(User.mobile == mobile_normalized).first()
    if user:
        logger.debug(f"Found user (ID: {user.id}) with phone number")
        return user
    
    # Try searching all users with normalization (for legacy data or format differences)
    logger.debug(f"User not found with exact match. Searching all users for mobile: {mobile[:3]}***")
    all_users = db.query(User).all()
    
    for u in all_users:
        if u.mobile:
            # Normalize both for comparison
            db_mobile_normalized = str(u.mobile).strip()
            
            # Compare plain text phone numbers (exact match)
            if db_mobile_normalized == mobile_normalized:
                logger.info(f"Found user (ID: {u.id}) by normalized comparison")
                return u
            # Also try last 10 digits match (for numbers with country code)
            elif len(mobile_normalized) > 10 and len(db_mobile_normalized) >= 10:
                if db_mobile_normalized[-10:] == mobile_normalized[-10:]:
                    logger.info(f"Found user (ID: {u.id}) by last 10 digits match")
                    return u
    
    logger.debug(f"No user found for mobile: {mobile[:3]}***")
    return None

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Retrieve user by ID.
    """
    user = db.query(User).filter(User.id == user_id).first()
    return user


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Retrieve user by email.
    """
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, mobile: str, name: Optional[str] = None, email: Optional[str] = None) -> User:
    """
    Create a new user with mobile number.
    Stores phone number as plain text.
    Checks if user already exists by comparing phone numbers.
    """
    # Normalize mobile number (remove whitespace, ensure it's a string)
    mobile = str(mobile).strip() if mobile else ""
    if not mobile:
        raise ValueError("Mobile number cannot be empty")
    
    logger.info(f"create_user called for mobile: {mobile[:3]}*** (masked)")
    
    # Step 1: Check if user already exists with plain text phone number
    existing_user = db.query(User).filter(User.mobile == mobile).first()
    if existing_user:
        logger.info(f"Found existing user (ID: {existing_user.id}) with phone number")
        return existing_user
    
    # Step 2: Try normalized search (for legacy data or format differences)
    mobile_normalized = str(mobile).strip()
    all_users = db.query(User).all()
    
    for u in all_users:
        if u.mobile:
            db_mobile_normalized = str(u.mobile).strip()
            # Compare plain text phone numbers (exact match)
            if db_mobile_normalized == mobile_normalized:
                logger.info(f"Found existing user (ID: {u.id}) by normalized comparison")
                return u
            # Also try last 10 digits match (for numbers with country code)
            elif len(mobile_normalized) > 10 and len(db_mobile_normalized) >= 10:
                if db_mobile_normalized[-10:] == mobile_normalized[-10:]:
                    logger.info(f"Found existing user (ID: {u.id}) by last 10 digits match")
                    return u
    
    # Step 3: No existing user found - create new user
    logger.info(f"No existing user found. Creating new user for mobile: {mobile[:3]}***")
    
    user = User(mobile=mobile, name=name, email=email)
    db.add(user)
    
    try:
        db.commit()
        db.refresh(user)
        logger.info(f"Successfully created new user (ID: {user.id})")
    except IntegrityError as e:
        db.rollback()
        # Unique constraint violation - user exists but we couldn't find it
        logger.warning(
            f"Unique constraint violation for mobile {mobile}. "
            f"User exists but not found. Attempting recovery..."
        )
        
        # Refresh session to get latest data
        db.expire_all()
        
        # Try get_user_by_mobile multiple times with different strategies
        recovery_attempts = [
            lambda: get_user_by_mobile(db, mobile),  # Standard search
            lambda: get_user_by_mobile(db, mobile.strip()),  # With stripped whitespace
        ]
        
        # Try different phone number formats if mobile has country code pattern
        if len(mobile) > 10:
            # Try last 10 digits (common for Indian numbers)
            recovery_attempts.append(lambda: get_user_by_mobile(db, mobile[-10:]))
        
        for attempt_num, recovery_func in enumerate(recovery_attempts, 1):
            try:
                existing_user = recovery_func()
                if existing_user:
                    logger.info(
                        f"Found user (ID: {existing_user.id}) via recovery attempt {attempt_num} "
                        f"after IntegrityError"
                    )
                    return existing_user
            except Exception as recovery_error:
                logger.debug(f"Recovery attempt {attempt_num} failed: {recovery_error}")
                continue
        
        # If still not found, return None instead of raising error
        logger.warning(
            f"Could not find user after IntegrityError for mobile {mobile[:3]}***. "
            f"Returning None - caller should retry get_user_by_mobile."
        )
        return None
    
    return user


def update_user_profile(
    db: Session,
    user_id: int,
    name: Optional[str] = None,
    email: Optional[str] = None,
    mobile: Optional[str] = None,
    profile_photo_url: Optional[str] = None
) -> Optional[User]:

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Store old data
    old_data = {
        "name": user.name,
        "email": user.email,
        "mobile": user.mobile,
        "profile_photo_url": user.profile_photo_url
    }

    # Update only provided fields
    if name is not None:
        user.name = name
    if email is not None:
        user.email = email
    if mobile is not None:
        # Store mobile as plain text
        user.mobile = mobile.strip() if mobile else None
    if profile_photo_url is not None:
        user.profile_photo_url = profile_photo_url

    try:
        db.commit()
        db.refresh(user)

        # Store new data
        new_data = {
            "name": user.name,
            "email": user.email,
            "mobile": user.mobile,
            "profile_photo_url": user.profile_photo_url
        }

        # If nothing changed, no need to log
        if old_data != new_data:
            log_profile_update(db, user.id, old_data, new_data)

        return user

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=400,
            detail="This email or phone number is already registered with another account."
        )

    except Exception as e:
        db.rollback()
        raise e
