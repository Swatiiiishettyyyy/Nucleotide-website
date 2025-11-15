from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import secrets
from typing import Optional
from .Device_session_model import DeviceSession


def create_device_session(
    db: Session,
    user_id: int,
    device_id: Optional[str] = None,
    device_platform: Optional[str] = None,
    device_details: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    expires_in_seconds: Optional[int] = None
) -> DeviceSession:
    """
    Create a new device session for a user.
    """
    session_key = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds) if expires_in_seconds else None

    ds = DeviceSession(
        user_id=user_id,
        session_key=session_key,
        device_id=device_id,
        device_platform=device_platform,
        device_details=device_details,
        ip_address=ip,
        user_agent=user_agent,
        expires_at=expires_at,
        is_active=True
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


def get_device_session(db: Session, session_id: int) -> Optional[DeviceSession]:
    """
    Retrieve device session by ID.
    """
    return db.query(DeviceSession).filter(DeviceSession.id == session_id).first()


def deactivate_session(db: Session, session_id: int) -> bool:
    """
    Deactivate a device session.
    """
    session = db.query(DeviceSession).filter(DeviceSession.id == session_id).first()
    if session:
        session.is_active = False
        db.commit()
        return True
    return False