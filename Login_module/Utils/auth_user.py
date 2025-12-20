from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional

from Login_module.Utils import security
from deps import get_db
from Login_module.User.user_session_crud import get_user_by_id
from Login_module.Device.Device_session_crud import update_last_active, get_device_session
from Member_module.Member_model import Member

security_scheme = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db)
):
    """
    Validates JWT token and returns the current authenticated user.
    Updates session last_active timestamp on each request.
    """
    token = credentials.credentials

    try:
        payload = security.decode_access_token(token)
    except HTTPException as e:
        # Re-raise the HTTPException from decode_access_token
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired access token: {str(e)}"
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not contain user info"
        )

    # Validate and update session
    session_id = payload.get("session_id")
    if session_id:
        try:
            session = get_device_session(db, int(session_id))
            if not session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session not found"
                )
            if not session.is_active:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been logged out"
                )
            # Update last_active timestamp
            update_last_active(db, int(session_id))
        except HTTPException:
            raise
        except (ValueError, Exception) as e:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid session"
            )

    try:
        user = get_user_by_id(db, int(user_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format in token"
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    return user


def get_current_member(
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Optional[Member]:
    """
    Extracts and returns the currently selected member from JWT token.
    Returns None if no member is selected in the token.
    """
    token = credentials.credentials

    try:
        payload = security.decode_access_token(token)
        selected_member_id = payload.get("selected_member_id")
        
        if not selected_member_id:
            return None
        
        # Validate member exists, belongs to user, and is not deleted
        member = db.query(Member).filter(
            Member.id == int(selected_member_id),
            Member.user_id == current_user.id,
            Member.is_deleted == False
        ).first()
        
        return member
    except (ValueError, KeyError, AttributeError):
        # If token doesn't have selected_member_id or invalid format, return None
        return None
    except Exception:
        # For any other error, return None (member not selected)
        return None