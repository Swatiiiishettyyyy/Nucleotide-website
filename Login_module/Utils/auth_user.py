from fastapi import Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import logging
from datetime import datetime, timedelta

from Login_module.Utils import security
from Login_module.Utils.rate_limiter import get_client_ip
from deps import get_db
from Login_module.User.user_session_crud import get_user_by_id
from Login_module.Device.Device_session_crud import get_device_session
from Login_module.Device.Device_session_model import DeviceSession
from Login_module.Utils.datetime_utils import now_ist, to_ist
from Member_module.Member_model import Member

logger = logging.getLogger(__name__)

security_scheme = HTTPBearer(auto_error=False)  # auto_error=False to allow optional token


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db)
):
    """
    Validates JWT token and returns the current authenticated user.
    Supports dual-token strategy:
    - For web: Extracts access token from cookie
    - For mobile: Extracts access token from Authorization header
    
    If access token expired but valid (signature check):
    - Returns 401 with error code "TOKEN_EXPIRED"
    - Frontend/client should call /auth/refresh
    
    Updates session last_active timestamp (throttled to once per minute).
    
    Sets request state with token expiration status for middleware to add response headers.
    """
    # Extract token from cookie (web) or Authorization header (mobile)
    token = None
    is_web = False
    
    # Check cookie: must be non-None and non-empty (strip whitespace)
    cookie_token = access_token_cookie.strip() if access_token_cookie and isinstance(access_token_cookie, str) else None
    if cookie_token:
        # Web: Token from cookie
        token = cookie_token
        is_web = True
    # Check Authorization header: must be non-None and non-empty
    elif credentials and credentials.credentials and credentials.credentials.strip():
        # Mobile: Token from Authorization header
        token = credentials.credentials.strip()
        is_web = False
    
    # No valid token found (neither cookie nor header)
    if not token:
        client_ip = get_client_ip(request)
        logger.warning(
            f"Authentication failed - No access token provided | IP: {client_ip} | "
            f"Cookie present: {access_token_cookie is not None} | "
            f"Cookie value: {repr(access_token_cookie) if access_token_cookie else 'None'} | "
            f"Auth header present: {credentials is not None and credentials.credentials is not None if credentials else False}"
        )
        # Set state for middleware
        request.state.token_expired = False
        request.state.token_invalid = True
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TOKEN", "detail": "Access token required"}
        )
    
    # Decode token with expiry check
    payload, is_expired, is_invalid = security.decode_access_token_with_expiry_check(token)
    client_ip = get_client_ip(request)
    
    # Store token status in request state for middleware to add headers
    request.state.token_expired = is_expired
    request.state.token_invalid = is_invalid
    request.state.token_valid = not is_invalid and not is_expired
    
    # Check for invalid token first
    if is_invalid or not payload:
        # Token is invalid (signature error, malformed, or couldn't decode)
        logger.warning(
            f"Authentication failed - Invalid token | IP: {client_ip} | Is expired: {is_expired} | Is invalid: {is_invalid} | Payload: {payload}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TOKEN", "detail": "Invalid access token"}
        )
    
    # Check for expired token (payload should not be None at this point, but double-check)
    if is_expired:
        # All endpoints (GET, POST, PUT, DELETE) require fresh tokens
        # Expired tokens are rejected - client must refresh using /auth/refresh endpoint
        request_method = request.method.upper() if hasattr(request, 'method') else "GET"
        payload_info = f"Payload keys: {list(payload.keys())}" if payload and isinstance(payload, dict) else f"Payload: {payload}"
        logger.info(
            f"Authentication failed - Access token expired for {request_method} request | IP: {client_ip} | {payload_info}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_EXPIRED", "detail": "Access token expired. Please refresh your token using /auth/refresh endpoint."}
        )
    
    # At this point, payload should be a valid dict (not None, not expired)
    if not isinstance(payload, dict):
        logger.error(
            f"Authentication failed - Payload is not a dict | IP: {client_ip} | Payload type: {type(payload)} | Payload value: {payload}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TOKEN", "detail": "Invalid token payload. Please log in again."}
        )
    
    # Log token payload for debugging
    logger.debug(
        f"Token decoded successfully | Payload keys: {list(payload.keys())} | "
        f"Has session_id: {'session_id' in payload} | IP: {client_ip}"
    )

    user_id = payload.get("sub")
    if not user_id:
        logger.warning(
            f"Authentication failed - Missing user_id in token payload | IP: {client_ip} | Payload keys: {list(payload.keys()) if payload else 'None'}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "INVALID_TOKEN", "detail": "Your account information is missing. Please log in again."}
        )

    # Validate and update session
    session_id = payload.get("session_id")
    
    # Log token payload for debugging (without sensitive data)
    logger.info(
        f"Token decoded | User ID: {user_id} | Session ID: {repr(session_id)} (type: {type(session_id)}) | "
        f"Payload keys: {list(payload.keys())} | IP: {client_ip}"
    )
    
    # Check if session_id exists and is valid in token payload
    if not session_id or session_id == "" or str(session_id).strip() == "" or str(session_id).lower() == "none":
        logger.error(
            f"Authentication failed - Missing or invalid session_id in token payload | "
            f"User ID: {user_id} | Session ID: {repr(session_id)} (type: {type(session_id)}) | "
            f"Token payload keys: {list(payload.keys())} | Full payload (sanitized): {dict((k, v) for k, v in payload.items() if k != 'exp')} | IP: {client_ip}"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "INVALID_TOKEN", "detail": "Session information missing from token. Please log in again."}
        )
    
    # Process session - session_id exists and is not empty/invalid
    try:
        # Convert session_id to int with validation
        logger.info(
            f"Validating session | User ID: {user_id} | Session ID value: {repr(session_id)} | Type: {type(session_id)} | IP: {client_ip}"
        )
        
        try:
            session_id_int = int(session_id)
            logger.debug(f"Successfully converted session_id {repr(session_id)} to int {session_id_int}")
        except (ValueError, TypeError) as e:
            logger.error(
                f"Authentication failed - Cannot convert session_id to int | "
                f"User ID: {user_id} | Session ID: {repr(session_id)} (type: {type(session_id)}) | "
                f"Token payload keys: {list(payload.keys())} | IP: {client_ip} | Error: {str(e)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "INVALID_TOKEN", "detail": "Invalid session information. Please log in again."}
            )
        
        # Query database for session
        try:
            session = get_device_session(db, session_id_int)
        except Exception as db_error:
            logger.error(
                f"Authentication failed - Database error while fetching session | "
                f"User ID: {user_id} | Session ID: {session_id_int} | IP: {client_ip} | Error: {str(db_error)}",
                exc_info=True
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "DATABASE_ERROR", "detail": "Database error while verifying your session. Please try again."}
            )
        
        if not session:
            # Session doesn't exist in database
            logger.warning(
                f"Authentication failed - Session not found in database | "
                f"User ID: {user_id} | Session ID: {session_id_int} | IP: {client_ip} | "
                f"This may indicate the session was deleted, expired, or the token is from an old session. "
                f"Possible causes: session cleanup, manual deletion, or token from previous login."
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "SESSION_NOT_FOUND", "detail": "Your session has expired or been invalidated. Please log in again."}
            )
        
        # Session found - check if active
        if not session.is_active:
            logger.warning(
                f"Authentication failed - Session inactive | "
                f"User ID: {user_id} | Session ID: {session_id_int} | IP: {client_ip} | "
                f"Session logged out at: {session.event_on_logout}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "SESSION_INACTIVE", "detail": "You have been logged out. Please log in again."}
            )
        
        # Verify session belongs to the correct user (security check)
        if session.user_id != int(user_id):
            logger.error(
                f"Authentication failed - Session user mismatch | "
                f"Token User ID: {user_id} | Session User ID: {session.user_id} | Session ID: {session_id_int} | IP: {client_ip}"
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error_code": "SESSION_MISMATCH", "detail": "Session validation failed. Please log in again."}
            )
        
        # Update last_active timestamp (throttled to once per minute)
        # Check if last_active was updated in the last minute
        try:
            last_active_threshold = now_ist() - timedelta(minutes=1)
            
            # Ensure both datetimes are timezone-aware before comparison
            # Convert session.last_active to IST if it's naive or in different timezone
            # This handles cases where database returns naive datetime or different timezone
            session_last_active_ist = to_ist(session.last_active) if session.last_active else None
            
            # Only update if last_active is None or if it's older than 1 minute
            # Both datetimes are now timezone-aware in IST, so comparison should work
            if not session_last_active_ist or session_last_active_ist < last_active_threshold:
                session.last_active = now_ist()
                db.commit()
                db.refresh(session)
                logger.debug(
                    f"Updated session last_active | Session ID: {session_id_int} | "
                    f"Previous: {session_last_active_ist} | New: {session.last_active}"
                )
        except TypeError as tz_error:
            # Handle timezone comparison errors - log and continue (don't fail authentication)
            logger.warning(
                f"Timezone comparison error while updating session last_active | "
                f"Session ID: {session_id_int} | Error: {str(tz_error)} | "
                f"Session last_active type: {type(session.last_active)} | "
                f"Session last_active value: {session.last_active} | "
                f"Will attempt to update with new timestamp"
            )
            # Try to update anyway with a new timestamp (force update to fix timezone issue)
            try:
                session.last_active = now_ist()
                db.commit()
                db.refresh(session)
                logger.info(
                    f"Fixed timezone issue by updating session last_active | Session ID: {session_id_int}"
                )
            except Exception as update_error:
                logger.warning(
                    f"Failed to update session last_active after timezone error | "
                    f"Session ID: {session_id_int} | Error: {str(update_error)}"
                )
                db.rollback()
        except Exception as commit_error:
            logger.warning(
                f"Failed to update session last_active | "
                f"Session ID: {session_id_int} | Error: {str(commit_error)} | "
                f"Error type: {type(commit_error).__name__}"
            )
            # Don't fail authentication if last_active update fails
            db.rollback()
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        logger.error(
            f"Authentication failed - Unexpected session validation error | "
            f"User ID: {user_id} | Session ID: {session_id} | IP: {client_ip} | "
            f"Error Type: {type(e).__name__} | Error: {str(e)} | "
            f"Traceback: {error_traceback}",
            exc_info=True
        )
        # Print to console for immediate visibility
        print(f"\n{'='*80}")
        print(f"EXCEPTION IN SESSION VALIDATION:")
        print(f"Error Type: {type(e).__name__}")
        print(f"Error Message: {str(e)}")
        print(f"User ID: {user_id}")
        print(f"Session ID: {session_id}")
        print(f"Traceback:\n{error_traceback}")
        print(f"{'='*80}\n")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error_code": "SESSION_ERROR", "detail": "An error occurred while verifying your session. Please try again."}
        )

    try:
        user = get_user_by_id(db, int(user_id))
    except ValueError:
        logger.warning(
            f"Authentication failed - Invalid user_id format | User ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="We couldn't verify your account. Please log in again."
        )

    if not user:
        logger.warning(
            f"Authentication failed - User not found | User ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="We couldn't find your account. Please try logging in again."
        )

    if not user.is_active:
        logger.warning(
            f"Authentication failed - User account deactivated | User ID: {user_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account has been deactivated. Please contact support."
        )

    # Authentication successful - ensure state is set correctly
    # If token was expired but allowed (GET requests), state is already set
    # If token is valid, ensure state reflects that
    if not hasattr(request.state, 'token_expired'):
        request.state.token_expired = False
        request.state.token_valid = True
        request.state.token_invalid = False
    elif not request.state.token_expired:
        # Token is not expired, ensure valid flag is set
        request.state.token_valid = True
        request.state.token_invalid = False

    return user


def get_current_member(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
) -> Optional[Member]:
    """
    Extracts and returns the currently selected member from JWT token.
    Returns None if no member is selected in the token.
    Supports dual-token strategy: extracts from cookie (web) or Authorization header (mobile).
    """
    # Extract token from cookie (web) or Authorization header (mobile)
    token = None
    
    if access_token_cookie:
        token = access_token_cookie
    elif credentials and credentials.credentials:
        token = credentials.credentials
    else:
        return None
    
    try:
        # Use decode_access_token_with_expiry_check to handle expired tokens gracefully
        payload, is_expired, is_invalid = security.decode_access_token_with_expiry_check(token)
        
        if is_invalid or is_expired or not payload:
            return None
        
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