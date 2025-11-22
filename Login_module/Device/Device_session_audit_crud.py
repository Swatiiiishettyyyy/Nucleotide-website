"""
Session audit log CRUD operations.
"""
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from .Device_session_audit_model import SessionAuditLog


def create_session_audit_log(
    db: Session,
    event_type: str,  # CREATED, DELETED, EXPIRED, ACTIVITY
    user_id: Optional[int] = None,
    session_id: Optional[int] = None,
    device_id: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> SessionAuditLog:
    """
    Create session audit log entry.
    """
    log = SessionAuditLog(
        user_id=user_id,
        session_id=session_id,
        device_id=device_id,
        event_type=event_type,
        reason=reason,
        timestamp=datetime.utcnow(),
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log

