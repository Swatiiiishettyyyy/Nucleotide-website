from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional
import logging

from .Newsletter_schema import (
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
    NewsletterSubscribeData
)
from .Newsletter_crud import create_newsletter_subscription
from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/newsletter", tags=["Newsletter"])
security_scheme = HTTPBearer(auto_error=False)  # auto_error=False to allow optional token


def extract_user_id_from_token(
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
) -> Optional[int]:
    """
    Extract user_id from JWT token if present and valid.
    Supports dual-token strategy: checks both cookie (web) and Authorization header (mobile).
    Allows expired tokens to extract user_id (for tracking/newsletter purposes).
    
    Returns:
        User ID integer if token is valid, None otherwise
    """
    token = None
    
    # Check cookie: must be non-None and non-empty (strip whitespace)
    cookie_token = access_token_cookie.strip() if access_token_cookie and isinstance(access_token_cookie, str) else None
    if cookie_token:
        # Web: Token from cookie
        token = cookie_token
    # Check Authorization header: must be non-None and non-empty
    elif credentials and credentials.credentials and credentials.credentials.strip():
        # Mobile: Token from Authorization header
        token = credentials.credentials.strip()
    
    # No valid token found (neither cookie nor header)
    if not token:
        return None
    
    try:
        from Login_module.Utils import security
        
        # Decode token to get user_id (allows expired tokens)
        payload, is_expired, is_invalid = security.decode_access_token_with_expiry_check(token)
        
        # If token is valid (even if expired), extract user_id
        if not is_invalid and payload:
            user_id_str = payload.get("sub")
            if user_id_str:
                try:
                    return int(user_id_str)
                except (ValueError, TypeError):
                    logger.debug(f"Invalid user_id format in token: {user_id_str}")
                    return None
    except Exception as e:
        # Token is invalid/expired - return None (anonymous user)
        logger.debug(f"Token extraction failed (anonymous user): {str(e)}")
        return None
    
    return None


def get_optional_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token"),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """
    Get current user if authenticated, return None if not.
    Does not raise exception if user is not authenticated.
    Supports dual-token strategy: checks both cookie (web) and Authorization header (mobile).
    Allows expired tokens to extract user_id (for tracking/newsletter purposes).
    """
    # Extract user_id directly from token (works even with expired tokens)
    user_id = extract_user_id_from_token(credentials=credentials, access_token_cookie=access_token_cookie)
    
    if not user_id:
        return None
    
    try:
        from Login_module.User.user_session_crud import get_user_by_id
        user = get_user_by_id(db, user_id)
        return user
    except Exception as e:
        logger.debug(f"User not found for user_id {user_id}: {str(e)}")
        return None


@router.post("/subscribe", response_model=NewsletterSubscribeResponse)
def subscribe_to_newsletter(
    request: NewsletterSubscribeRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
):
    """
    Subscribe to newsletter.
    Accepts email address, validates it, and stores subscription.
    Works for both authenticated and anonymous users.
    
    - If user is authenticated: Links subscription to user_id
    - If user is anonymous: Creates subscription without user_id
    """
    try:
        # Get user_id if authenticated (from user object)
        user_id = current_user.id if current_user else None
        logger.info(
            f"Newsletter subscription | "
            f"current_user: {current_user.id if current_user else None} | "
            f"user_id from current_user: {user_id} | "
            f"Has cookie: {access_token_cookie is not None} | "
            f"Has credentials: {credentials is not None}"
        )
        
        # If user lookup failed but token exists, try to extract user_id directly from token
        # This handles cases where token is valid but user doesn't exist in DB
        if not user_id:
            extracted_user_id = extract_user_id_from_token(
                credentials=credentials,
                access_token_cookie=access_token_cookie
            )
            logger.info(
                f"Token extraction fallback | "
                f"extracted_user_id: {extracted_user_id} | "
                f"extracted_user_id type: {type(extracted_user_id)}"
            )
            if extracted_user_id:
                user_id = extracted_user_id
                logger.warning(
                    f"Newsletter subscription: user_id {extracted_user_id} extracted from token "
                    f"but user not found in database - storing user_id anyway"
                )
        
        # Log token extraction details for debugging
        logger.info(
            f"Newsletter subscription final user_id | "
            f"user_id: {user_id} | "
            f"user_id type: {type(user_id)} | "
            f"user_type: {'authenticated' if user_id else 'anonymous'}"
        )
        
        # Validate and normalize email (Pydantic EmailStr already validates format)
        email = request.email.lower().strip()
        
        # Log before creating subscription
        logger.info(
            f"Creating newsletter subscription | "
            f"email: {email} | "
            f"user_id: {user_id} | "
            f"user_id type: {type(user_id)}"
        )
        
        # Create or update subscription
        subscription = create_newsletter_subscription(
            db=db,
            email=email,
            user_id=user_id
        )
        
        logger.info(
            f"Newsletter subscription created | "
            f"subscription.id: {subscription.id} | "
            f"subscription.user_id: {subscription.user_id} | "
            f"user_id parameter was: {user_id}"
        )
        
        # Prepare response data
        response_data = NewsletterSubscribeData(
            user_id=subscription.user_id,
            email=subscription.email
        )
        
        message = "Successfully subscribed to newsletter"
        if subscription.user_id:
            message = "Successfully subscribed to newsletter (linked to your account)"
        
        return NewsletterSubscribeResponse(
            status="success",
            message=message,
            data=response_data
        )
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error subscribing to newsletter: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to subscribe to newsletter. Please try again."
        )

