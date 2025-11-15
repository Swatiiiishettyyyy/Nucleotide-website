from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from typing import Optional
from .user_model import User



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
    mobile: Optional[str] = None
) -> Optional[User]:
    """
    Update user profile information.
    Only updates fields that are provided (not None).
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None

    # Update only provided fields
    if name is not None:
        user.name = name
    if email is not None:
        user.email = email
    if mobile is not None:
        user.mobile = mobile

    try:
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        db.rollback()
        raise e


