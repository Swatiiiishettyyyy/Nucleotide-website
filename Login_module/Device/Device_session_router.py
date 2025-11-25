"""
Device Session Router - endpoints for managing user sessions.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User
from .Device_session_crud import (
    get_user_active_sessions,
    count_user_active_sessions,
    get_user_active_sessions_count,
    deactivate_session
)
from Login_module.OTP.OTP_router import MAX_ACTIVE_SESSIONS
from Login_module.Utils.rate_limiter import get_client_ip

router = APIRouter(prefix="/sessions", tags=["Sessions"])


class SessionData(BaseModel):
    """Session data model"""
    session_id: int
    device_id: Optional[str] = None
    device_platform: Optional[str] = None
    ip_address: Optional[str] = None
    browser_info: Optional[str] = None
    last_active: datetime
    created_at: datetime
    is_current: bool = False  # Whether this is the current session


class ActiveSessionsResponse(BaseModel):
    """Response for active sessions list"""
    status: str
    message: str
    active_sessions_count: int
    max_sessions: int
    limit_reached: bool
    remaining_slots: int
    sessions: List[SessionData]


class SessionCountResponse(BaseModel):
    """Response for session count"""
    status: str
    message: str
    active_sessions: int
    max_sessions: int
    limit_reached: bool
    remaining_slots: int


class RevokeSessionResponse(BaseModel):
    """Response for revoking a session"""
    status: str
    message: str
    session_id: int


@router.get("/active", response_model=ActiveSessionsResponse)
def get_active_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all active sessions for the current user.
    Shows session count, limit status, and details of each active session.
    """
    # Get current session ID from token
    current_session_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from Login_module.Utils import security
            token = auth_header.split(" ")[1]
            payload = security.decode_access_token(token)
            current_session_id = payload.get("session_id")
            if current_session_id:
                current_session_id = int(current_session_id)
        except Exception:
            pass  # Ignore if we can't get current session
    
    # Get active sessions
    active_sessions = get_user_active_sessions(db, current_user.id)
    session_count_info = get_user_active_sessions_count(db, current_user.id, MAX_ACTIVE_SESSIONS)
    
    # Build session data
    sessions_data = []
    for session in active_sessions:
        sessions_data.append(SessionData(
            session_id=session.id,
            device_id=session.device_id,
            device_platform=session.device_platform,
            ip_address=session.ip_address,
            browser_info=session.browser_info,
            last_active=session.last_active,
            created_at=session.created_at,
            is_current=(current_session_id == session.id) if current_session_id else False
        ))
    
    return ActiveSessionsResponse(
        status="success",
        message=f"Found {len(sessions_data)} active session(s).",
        active_sessions_count=session_count_info["active_sessions"],
        max_sessions=session_count_info["max_sessions"],
        limit_reached=session_count_info["limit_reached"],
        remaining_slots=session_count_info["remaining_slots"],
        sessions=sessions_data
    )


@router.get("/count", response_model=SessionCountResponse)
def get_session_count(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get the count of active sessions for the current user.
    Useful for checking if the 4-session limit is reached.
    """
    session_count_info = get_user_active_sessions_count(db, current_user.id, MAX_ACTIVE_SESSIONS)
    
    return SessionCountResponse(
        status="success",
        message=f"User has {session_count_info['active_sessions']} active session(s) out of {session_count_info['max_sessions']} maximum.",
        active_sessions=session_count_info["active_sessions"],
        max_sessions=session_count_info["max_sessions"],
        limit_reached=session_count_info["limit_reached"],
        remaining_slots=session_count_info["remaining_slots"]
    )


@router.post("/revoke/{session_id}", response_model=RevokeSessionResponse)
def revoke_session(
    session_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke (logout) a specific session.
    Users can only revoke their own sessions.
    """
    # Verify session belongs to user
    from .Device_session_crud import get_device_session
    session = get_device_session(db, session_id)
    
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )
    
    if session.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only revoke your own sessions"
        )
    
    if not session.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Session is already inactive"
        )
    
    # Deactivate session
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    import uuid
    correlation_id = str(uuid.uuid4())
    
    deactivated = deactivate_session(
        db=db,
        session_id=session_id,
        reason="Session revoked by user",
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    
    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to revoke session"
        )
    
    return RevokeSessionResponse(
        status="success",
        message=f"Session {session_id} revoked successfully.",
        session_id=session_id
    )


@router.post("/revoke-all", response_model=RevokeSessionResponse)
def revoke_all_sessions(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Revoke all active sessions for the current user (except current session if specified).
    Useful for logging out from all devices.
    """
    # Get current session ID from token
    current_session_id = None
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from Login_module.Utils import security
            token = auth_header.split(" ")[1]
            payload = security.decode_access_token(token)
            current_session_id = payload.get("session_id")
            if current_session_id:
                current_session_id = int(current_session_id)
        except Exception:
            pass
    
    # Get all active sessions
    active_sessions = get_user_active_sessions(db, current_user.id)
    
    if not active_sessions:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active sessions found"
        )
    
    # Revoke all sessions (or all except current)
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    import uuid
    correlation_id = str(uuid.uuid4())
    
    revoked_count = 0
    for session in active_sessions:
        # Skip current session if we want to keep it
        if current_session_id and session.id == current_session_id:
            continue
        
        deactivated = deactivate_session(
            db=db,
            session_id=session.id,
            reason="All sessions revoked by user",
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        if deactivated:
            revoked_count += 1
    
    if revoked_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No sessions were revoked (only current session exists)"
        )
    
    return RevokeSessionResponse(
        status="success",
        message=f"Revoked {revoked_count} session(s) successfully.",
        session_id=0  # Indicates multiple sessions
    )

