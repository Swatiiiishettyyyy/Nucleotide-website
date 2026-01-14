"""
CSRF Middleware - Optionally validates CSRF tokens for state-changing operations (POST/PUT/DELETE).
CSRF token is OPTIONAL - requests proceed even without CSRF token.
If CSRF token is provided, it will be validated. If invalid, a warning is logged but request is allowed.
Exempts /auth/* endpoints from CSRF check.
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from typing import Callable
import logging

from Login_module.Utils.csrf import should_exempt_from_csrf, validate_csrf_token
from Login_module.Utils.rate_limiter import get_client_ip

logger = logging.getLogger(__name__)


class CSRFProtectionMiddleware(BaseHTTPMiddleware):
    """
    CSRF protection middleware for state-changing operations.
    CSRF token is OPTIONAL - validates CSRF token if provided for POST/PUT/DELETE requests.
    If CSRF token is missing or invalid, request proceeds with a warning log (not blocked).
    Exempts certain paths from CSRF check (see should_exempt_from_csrf).
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Skip CSRF check for GET, OPTIONS, HEAD requests
        if request.method in ["GET", "OPTIONS", "HEAD"]:
            return await call_next(request)
        
        # Check if path should be exempted from CSRF check
        path = request.url.path
        if should_exempt_from_csrf(path):
            return await call_next(request)
        
        # For state-changing operations (POST/PUT/DELETE), validate CSRF token if provided
        # CSRF token is OPTIONAL - if not provided, request proceeds without validation
        # Extract CSRF token from header (try multiple header name variations)
        csrf_token = (
            request.headers.get("X-CSRF-Token") or 
            request.headers.get("X-CSRF-TOKEN") or 
            request.headers.get("x-csrf-token") or
            request.headers.get("csrf-token")
        )
        
        # If no CSRF token provided, log and continue (CSRF is optional)
        if not csrf_token:
            client_ip = get_client_ip(request)
            logger.debug(
                f"CSRF token not provided (optional) | "
                f"{request.method} {path} | IP: {client_ip}"
            )
            # Continue without CSRF validation
            return await call_next(request)
        
        # Extract user_id and session_id from access token (cookie or header)
        user_id = None
        session_id = None
        
        # Try cookie first (web)
        access_token = request.cookies.get("access_token")
        if not access_token:
            # Try Authorization header (mobile)
            auth_header = request.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                access_token = auth_header.split(" ")[1]
        
        if access_token:
            try:
                from Login_module.Utils import security
                payload, is_expired, is_invalid = security.decode_access_token_with_expiry_check(access_token)
                # Extract user_id and session_id even from expired tokens (for CSRF validation)
                # Expired tokens still have valid signatures and can be used for CSRF validation
                if payload and not is_invalid:
                    user_id = payload.get("sub")
                    session_id = payload.get("session_id")
            except Exception:
                # Token invalid - will be handled by get_current_user
                pass
        
        if not user_id or not session_id:
            # Cannot validate CSRF without user context - log and continue (CSRF is optional)
            client_ip = get_client_ip(request)
            logger.debug(
                f"CSRF token provided but cannot extract user context (optional) | "
                f"{request.method} {path} | IP: {client_ip}"
            )
            # Continue without CSRF validation
            return await call_next(request)
        
        # Verify session is still active (optional check - log warning but don't block)
        try:
            from Login_module.Device.Device_session_crud import get_device_session
            from deps import get_db
            # Get database session for session validation
            db = next(get_db())
            try:
                session = get_device_session(db, int(session_id))
                if not session or not session.is_active:
                    client_ip = get_client_ip(request)
                    logger.debug(
                        f"CSRF token provided but session is inactive (optional - request allowed) | "
                        f"{request.method} {path} | User ID: {user_id} | Session ID: {session_id} | IP: {client_ip}"
                    )
                    # Continue even with inactive session (CSRF is optional)
            finally:
                db.close()
        except Exception as e:
            # If we can't verify session, still proceed with CSRF validation
            # (session check is a security enhancement, not a hard requirement)
            logger.debug(f"Could not verify session status during CSRF validation: {e}")
        
        # Validate CSRF token if provided (optional - log warning but don't block)
        if not validate_csrf_token(csrf_token, int(user_id), int(session_id)):
            client_ip = get_client_ip(request)
            logger.warning(
                f"CSRF token provided but invalid (optional - request allowed) | "
                f"{request.method} {path} | User ID: {user_id} | Session ID: {session_id} | IP: {client_ip}"
            )
            # Continue even with invalid CSRF token (CSRF is optional)
            return await call_next(request)
        
        # CSRF validation passed (if token was provided)
        logger.debug(
            f"CSRF token validated successfully | "
            f"{request.method} {path} | User ID: {user_id} | Session ID: {session_id}"
        )
        return await call_next(request)

