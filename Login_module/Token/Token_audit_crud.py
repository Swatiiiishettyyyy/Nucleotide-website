"""
Token Audit Logging - Records token-related security events.
"""
from sqlalchemy.orm import Session
from typing import Optional
from datetime import datetime
import logging
import uuid

logger = logging.getLogger(__name__)

# Event types for token operations
TOKEN_EVENT_TYPES = {
    "TOKEN_REFRESHED": "Token refresh successful",
    "TOKEN_REFRESH_FAILED": "Token refresh failed (expired/invalid)",
    "TOKEN_REUSE_DETECTED": "Token reuse detected (security incident)",
    "REFRESH_TOKEN_REVOKED": "Single refresh token revoked",
    "TOKEN_FAMILY_REVOKED": "Token family revoked",
    "TOKEN_CREATED": "New token pair created",
    "TOKEN_EXPIRED": "Token expired",
    "SESSION_EXPIRED_ABSOLUTE": "Session expired due to maximum lifetime exceeded"
}


def log_token_event(
    db: Session,
    event_type: str,
    user_id: Optional[int],  # Allow None for unknown users (e.g., when token can't be decoded)
    session_id: Optional[int] = None,
    token_family_id: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> None:
    """
    Log token-related security events.
    Uses existing session audit log for consistency.
    """
    try:
        from Login_module.Device.Device_session_audit_crud import create_session_audit_log
        
        # Map token event types to session audit event types
        session_event_type = "ACTIVITY"  # Default
        
        if event_type == "TOKEN_REUSE_DETECTED":
            session_event_type = "SECURITY_INCIDENT"
        elif event_type in ["REFRESH_TOKEN_REVOKED", "TOKEN_FAMILY_REVOKED"]:
            session_event_type = "DELETED"
        
        audit_reason = f"{event_type}"
        if reason:
            audit_reason += f": {reason}"
        if token_family_id:
            audit_reason += f" | Family ID: {token_family_id}"
        
        create_session_audit_log(
            db=db,
            event_type=session_event_type,
            user_id=user_id,
            session_id=session_id,
            reason=audit_reason,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id or str(uuid.uuid4())
        )
    except Exception as e:
        # Log to application logger if database audit fails
        logger.error(
            f"Failed to create token audit log | "
            f"Event Type: {event_type} | User ID: {user_id} | "
            f"Session ID: {session_id} | Error: {str(e)}",
            exc_info=True
        )

