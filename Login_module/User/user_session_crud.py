from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from typing import Optional
from .user_model import User
from Profile_module.Profile_audit_crud import log_profile_update
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException


def get_user_by_mobile(db: Session, mobile: str) -> Optional[User]:
    """
    Retrieve user by mobile number.
    """
    return db.query(User).filter(User.mobile == mobile).first()

def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
    """
    Retrieve user by ID.
    """
    return db.query(User).filter(User.id == user_id).first()


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    """
    Retrieve user by email.
    """
    return db.query(User).filter(User.email == email).first()


def create_user(db: Session, mobile: str, name: Optional[str] = None, email: Optional[str] = None) -> User:
    """
    Create a new user with mobile number.
    """
    user = User(mobile=mobile, name=name, email=email)
    db.add(user)
    db.commit()
    db.refresh(user)
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
        user.mobile = mobile
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
            detail="Email or Mobile already exists"
        )

    except Exception as e:
        db.rollback()
        raise e
