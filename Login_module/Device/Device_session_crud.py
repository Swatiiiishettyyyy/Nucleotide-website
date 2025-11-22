from sqlalchemy.orm import Session
from sqlalchemy import func, with_for_update
from datetime import datetime, timedelta
import secrets
from typing import Optional
import logging
from .Device_session_model import DeviceSession
from .Device_session_audit_crud import create_session_audit_log

logger = logging.getLogger(__name__)


def create_device_session(
    db: Session,
    user_id: int,
    device_id: Optional[str] = None,
    device_platform: Optional[str] = None,
    device_details: Optional[str] = None,
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    expires_in_seconds: Optional[int] = None,
    max_active_sessions: int = 4,
    correlation_id: Optional[str] = None
) -> DeviceSession:
    """
    Create a new device session for a user.
    If user has more than max_active_sessions, delete the oldest session.
    Uses database-level locking to prevent race conditions.
    """
    try:
        # Use database lock to prevent race conditions
        # Lock the user's sessions to prevent concurrent session creation
        active_sessions = (
            db.query(DeviceSession)
            .filter(
                DeviceSession.user_id == user_id,
                DeviceSession.is_active == True
            )
            .with_for_update()  # Row-level lock
            .order_by(DeviceSession.last_active.asc())
            .all()
        )
        
        # If max sessions reached, delete oldest
        if len(active_sessions) >= max_active_sessions:
            # Delete oldest session(s) to make room
            sessions_to_delete = active_sessions[:len(active_sessions) - max_active_sessions + 1]
            for old_session in sessions_to_delete:
                db.delete(old_session)
            db.flush()  # Flush before commit
        
        # Generate session token (ensure uniqueness)
        session_token = secrets.token_urlsafe(32)
        max_retries = 5
        retry_count = 0
        while retry_count < max_retries:
            existing = db.query(DeviceSession).filter(DeviceSession.session_token == session_token).first()
            if not existing:
                break
            session_token = secrets.token_urlsafe(32)
            retry_count += 1
        
        if retry_count >= max_retries:
            raise Exception("Failed to generate unique session token")
        
        # Use browser_info from user_agent or device_details
        browser_info = user_agent or device_details or None
        
        # Create new session
        ds = DeviceSession(
            user_id=user_id,
            session_token=session_token,
            device_id=device_id,
            device_platform=device_platform,
            ip_address=ip,
            browser_info=browser_info,
            last_active=datetime.utcnow(),
            is_active=True,
            # Legacy fields for backward compatibility
            session_key=session_token,
            device_details=device_details,
            user_agent=user_agent
        )
        db.add(ds)
        db.commit()
        db.refresh(ds)
        
        # Audit log for session creation
        try:
            create_session_audit_log(
                db=db,
                event_type="CREATED",
                user_id=user_id,
                session_id=ds.id,
                device_id=device_id,
                reason="Session created after OTP verification",
                ip_address=ip,
                user_agent=user_agent,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning(f"Failed to create session audit log: {e}")
            # Don't fail session creation if audit log fails
        
        return ds
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating device session: {e}")
        raise


def get_device_session(db: Session, session_id: int) -> Optional[DeviceSession]:
    """
    Retrieve device session by ID.
    """
    return db.query(DeviceSession).filter(DeviceSession.id == session_id).first()


def get_device_session_by_token(db: Session, session_token: str) -> Optional[DeviceSession]:
    """
    Retrieve device session by session token.
    """
    return db.query(DeviceSession).filter(
        DeviceSession.session_token == session_token,
        DeviceSession.is_active == True
    ).first()


def update_last_active(db: Session, session_id: int) -> bool:
    """
    Update the last_active timestamp for a session.
    """
    session = db.query(DeviceSession).filter(DeviceSession.id == session_id).first()
    if session:
        session.last_active = datetime.utcnow()
        db.commit()
        return True
    return False


def deactivate_session(
    db: Session,
    session_id: int,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> bool:
    """
    Deactivate a device session (logout).
    Only deletes this specific session; other sessions remain active.
    """
    session = db.query(DeviceSession).filter(DeviceSession.id == session_id).first()
    if session:
        session.is_active = False
        session.event_on_logout = datetime.utcnow()
        db.commit()
        
        # Audit log for session deletion
        try:
            create_session_audit_log(
                db=db,
                event_type="DELETED",
                user_id=session.user_id,
                session_id=session_id,
                device_id=session.device_id,
                reason=reason or "User logout",
                ip_address=ip_address,
                user_agent=user_agent,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning(f"Failed to create session audit log: {e}")
        
        return True
    return False


def deactivate_session_by_token(db: Session, session_token: str, reason: Optional[str] = None) -> bool:
    """
    Deactivate a device session by token (logout).
    """
    session = get_device_session_by_token(db, session_token)
    if session:
        session.is_active = False
        session.event_on_logout = datetime.utcnow()
        db.commit()
        return True
    return False


def get_user_active_sessions(db: Session, user_id: int) -> list[DeviceSession]:
    """
    Get all active sessions for a user.
    """
    return (
        db.query(DeviceSession)
        .filter(
            DeviceSession.user_id == user_id,
            DeviceSession.is_active == True
        )
        .order_by(DeviceSession.last_active.desc())
        .all()
    )


def cleanup_inactive_sessions(db: Session, hours_inactive: int = 24) -> int:
    """
    Delete inactive or deleted sessions older than specified hours.
    Returns count of deleted sessions.
    """
    cutoff_time = datetime.utcnow() - timedelta(hours=hours_inactive)
    
    # Delete sessions that are inactive and older than cutoff
    deleted_count = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.is_active == False,
            DeviceSession.event_on_logout < cutoff_time
        )
        .delete()
    )
    
    # Also delete sessions that haven't been active for a long time (stale sessions)
    stale_count = (
        db.query(DeviceSession)
        .filter(
            DeviceSession.last_active < cutoff_time,
            DeviceSession.is_active == True
        )
        .delete()
    )
    
    db.commit()
    return deleted_count + stale_count