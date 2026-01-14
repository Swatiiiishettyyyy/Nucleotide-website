"""
Tracking Router - API endpoints for location and analytics tracking
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request, Cookie
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import Optional
import logging
import uuid

from deps import get_db
from .Tracking_schema import TrackingEventRequest, TrackingEventResponse, DeviceInfo
from .Tracking_crud import create_tracking_record
from Login_module.Utils.datetime_utils import now_ist, to_ist_isoformat
from Login_module.Utils.rate_limiter import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tracking", tags=["Tracking"])

# Security scheme for optional authentication
security_scheme = HTTPBearer(auto_error=False)  # Don't raise error if token missing


def extract_user_id_from_token(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
) -> Optional[str]:
    """
    Extract and return user_id from JWT token if present and valid.
    Supports dual-token strategy:
    - For web: Extracts access token from cookie
    - For mobile: Extracts access token from Authorization header
    
    Args:
        request: FastAPI Request object
        credentials: HTTPAuthorizationCredentials from Bearer token
        access_token_cookie: Access token from cookie (web)
        
    Returns:
        User ID string if token is valid, None otherwise (anonymous user)
    """
    token = None
    
    # Check cookie: must be non-None and non-empty (strip whitespace)
    cookie_token = access_token_cookie.strip() if access_token_cookie and isinstance(access_token_cookie, str) else None
    if cookie_token:
        # Web: Token from cookie
        token = cookie_token
        logger.info(f"Token found in cookie | Token length: {len(token)} | IP: {get_client_ip(request)}")
    # Check Authorization header: must be non-None and non-empty
    elif credentials and credentials.credentials and credentials.credentials.strip():
        # Mobile: Token from Authorization header
        token = credentials.credentials.strip()
        logger.info(f"Token found in Authorization header | Token length: {len(token)} | IP: {get_client_ip(request)}")
    else:
        logger.warning(
            f"No token found | "
            f"Cookie present: {access_token_cookie is not None} | "
            f"Credentials present: {credentials is not None} | "
            f"IP: {get_client_ip(request)}"
        )
    
    # No valid token found (neither cookie nor header)
    if not token:
        return None
    
    try:
        from Login_module.Utils import security
        
        # Decode token to get user_id
        payload, is_expired, is_invalid = security.decode_access_token_with_expiry_check(token)
        
        # Log for debugging
        logger.debug(
            f"Token decode result | is_expired: {is_expired} | is_invalid: {is_invalid} | "
            f"has_payload: {payload is not None} | payload_keys: {list(payload.keys()) if payload else None}"
        )
        
        # If token is valid (even if expired), extract user_id
        if not is_invalid and payload:
            user_id = payload.get("sub")
            logger.info(
                f"Token decoded successfully | "
                f"is_expired: {is_expired} | "
                f"user_id from payload: {user_id} | "
                f"payload keys: {list(payload.keys())} | "
                f"IP: {get_client_ip(request)}"
            )
            if user_id:
                user_id_str = str(user_id)
                logger.info(f"Returning user_id: {user_id_str} | IP: {get_client_ip(request)}")
                return user_id_str
            else:
                logger.warning(
                    f"Token payload exists but 'sub' field is missing | "
                    f"payload keys: {list(payload.keys())} | "
                    f"IP: {get_client_ip(request)}"
                )
        else:
            logger.warning(
                f"Token is invalid or missing payload | "
                f"is_invalid: {is_invalid} | "
                f"is_expired: {is_expired} | "
                f"payload: {payload} | "
                f"IP: {get_client_ip(request)}"
            )
    except Exception as e:
        # Token is invalid/expired - return None (anonymous user)
        logger.warning(f"Token extraction failed (anonymous user): {str(e)}", exc_info=True)
        pass
    
    return None


def get_fields_stored_and_null(
    ga_consent: bool,
    location_consent: bool,
    has_user_id: bool,
    has_ga_client_id: bool,
    has_location: bool,
    has_page_data: bool,
    has_device_info: bool
) -> tuple[list, list]:
    """
    Determine which fields were stored and which are null.
    
    Returns:
        Tuple of (fields_stored, fields_null)
    """
    fields_stored = []
    fields_null = []
    
    # Always stored
    if has_user_id:
        fields_stored.append("user_id")
    else:
        fields_null.append("user_id")
    
    if has_ga_client_id:
        fields_stored.append("ga_client_id")
    else:
        fields_null.append("ga_client_id")
    
    # Session ID is always stored if provided
    # Consent flags are always stored
    
    # Location fields
    if location_consent and has_location:
        fields_stored.extend(["latitude", "longitude", "accuracy"])
    else:
        fields_null.extend(["latitude", "longitude", "accuracy"])
    
    # GA/Page fields
    if ga_consent and has_page_data:
        fields_stored.extend(["page_url", "referrer"])
    else:
        fields_null.extend(["page_url", "referrer"])
    
    # Device info
    if ga_consent and has_device_info:
        fields_stored.extend(["user_agent", "device_type", "browser", "operating_system", "language", "timezone", "ip_address"])
    else:
        fields_null.extend(["user_agent", "device_type", "browser", "operating_system", "language", "timezone", "ip_address"])
    
    return fields_stored, fields_null


@router.post(
    "/event",
    response_model=TrackingEventResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record tracking event with consent management",
    description="Record location and analytics tracking data. Supports both anonymous and authenticated users. Data storage is conditional based on consent flags. NO CSRF token required."
)
def track_event(
    request: TrackingEventRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    access_token_cookie: Optional[str] = Cookie(None, alias="access_token")
):
    """
    Record tracking event with consent-based data collection.
    
    - **Authentication**: Optional (accepts both authenticated and anonymous requests)
    - **CSRF Protection**: NOT required for this endpoint
    - **Consent Management**: Data is stored conditionally based on consent flags
    - **User ID**: Hashed with bcrypt for authenticated users
    
    **Consent Behavior:**
    - If ga_consent=false: GA-related fields (ga_client_id, page_url, referrer, device_info, ip_address) are NOT stored
    - If ga_consent=true: GA-related fields ARE stored (if provided)
    - If location_consent=false: Location fields (latitude, longitude, accuracy) are NOT stored
    - If location_consent=true: Location fields ARE stored (if provided)
    """
    request_id = str(uuid.uuid4())
    client_ip = get_client_ip(http_request)
    user_agent_header = http_request.headers.get("user-agent", "unknown")
    
    try:
        # Extract user_id from token if authenticated (checks both cookie and header)
        logger.info(
            f"Tracking event request | "
            f"Has cookie: {access_token_cookie is not None} | "
            f"Cookie length: {len(access_token_cookie) if access_token_cookie else 0} | "
            f"Has credentials: {credentials is not None} | "
            f"Credentials token: {credentials.credentials is not None if credentials else False} | "
            f"IP: {client_ip}"
        )
        user_id = extract_user_id_from_token(
            request=http_request,
            credentials=credentials,
            access_token_cookie=access_token_cookie
        )
        logger.info(
            f"User ID extraction result | "
            f"user_id: {user_id} | "
            f"user_id type: {type(user_id)} | "
            f"IP: {client_ip}"
        )
        user_type = "authenticated" if user_id else "anonymous"
        
        # Extract device info from request
        device_info = request.device_info
        device_user_agent = device_info.user_agent if device_info else None
        device_type = device_info.device_type if device_info else None
        browser = device_info.browser if device_info else None
        operating_system = device_info.os if device_info else None
        language = device_info.language if device_info else None
        timezone = device_info.timezone if device_info else None
        
        # Use device_info user_agent if provided, otherwise fall back to header
        final_user_agent = device_user_agent or user_agent_header
        
        # Determine what data we have
        has_location = request.latitude is not None and request.longitude is not None
        has_page_data = request.page_url is not None or request.referrer is not None
        has_device_info = device_info is not None and (
            device_user_agent or device_type or browser or operating_system or language or timezone
        )
        
        # Log before creating tracking record
        logger.info(
            f"Creating tracking record | "
            f"user_id: {user_id} | "
            f"user_id type: {type(user_id)} | "
            f"user_type: {user_type} | "
            f"ga_consent: {request.ga_consent} | "
            f"location_consent: {request.location_consent} | "
            f"IP: {client_ip}"
        )
        
        # Create tracking record
        tracking_record = create_tracking_record(
            db=db,
            ga_consent=request.ga_consent,
            location_consent=request.location_consent,
            user_id=user_id,
            ga_client_id=request.ga_client_id,
            session_id=request.session_id,
            latitude=request.latitude,
            longitude=request.longitude,
            accuracy=request.accuracy,
            page_url=request.page_url,
            referrer=request.referrer,
            user_agent=final_user_agent if request.ga_consent else None,
            device_type=device_type if request.ga_consent else None,
            browser=browser if request.ga_consent else None,
            operating_system=operating_system if request.ga_consent else None,
            language=language if request.ga_consent else None,
            timezone=timezone if request.ga_consent else None,
            ip_address=client_ip if request.ga_consent else None
        )
        
        # Determine fields stored and null
        has_ga_client_id = tracking_record.ga_client_id is not None
        fields_stored, fields_null = get_fields_stored_and_null(
            ga_consent=request.ga_consent,
            location_consent=request.location_consent,
            has_user_id=user_id is not None,
            has_ga_client_id=has_ga_client_id,
            has_location=has_location,
            has_page_data=has_page_data,
            has_device_info=has_device_info
        )
        
        # Determine message based on consents
        if request.ga_consent and request.location_consent:
            message = "Tracking data recorded successfully"
        elif request.ga_consent and not request.location_consent:
            message = "Analytics tracking enabled, location tracking disabled"
        elif not request.ga_consent and request.location_consent:
            message = "Location tracking enabled, analytics tracking disabled"
        else:
            message = "Consent preferences recorded"
        
        # Build response data
        response_data = {
            "record_id": tracking_record.record_id,
            "user_type": user_type,
            "consents": {
                "ga_consent": request.ga_consent,
                "location_consent": request.location_consent
            },
            "fields_stored": fields_stored,
            "fields_null": fields_null,
            "timestamp": to_ist_isoformat(now_ist())
        }
        
        
        logger.info(
            f"Tracking event recorded | Record ID: {tracking_record.record_id} | "
            f"User Type: {user_type} | GA Consent: {request.ga_consent} | "
            f"Location Consent: {request.location_consent} | Request ID: {request_id}"
        )
        
        return TrackingEventResponse(
            success=True,
            message=message,
            data=response_data
        )
    
    except (ValueError, TypeError) as e:
        # Validation error from Pydantic
        logger.warning(
            f"Tracking event failed - Validation error | "
            f"Error: {str(e)} | IP: {client_ip} | Request ID: {request_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error_code": "VALIDATION_ERROR",
                "message": str(e),
                "request_id": request_id
            }
        )
    except IntegrityError as e:
        # Database constraint violation
        db.rollback()
        logger.error(
            f"Tracking event failed - Database integrity error | "
            f"Error: {str(e)} | IP: {client_ip} | Request ID: {request_id}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An error occurred while recording tracking data. Please try again.",
                "request_id": request_id
            }
        )
    except SQLAlchemyError as e:
        # Database connection or query error
        db.rollback()
        logger.error(
            f"Tracking event failed - Database error | "
            f"Error: {str(e)} | IP: {client_ip} | Request ID: {request_id}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An error occurred while recording tracking data. Please try again.",
                "request_id": request_id
            }
        )
    except Exception as e:
        # Unexpected error
        import traceback
        error_traceback = traceback.format_exc()
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            f"Tracking event failed - Unexpected error | "
            f"Error: {str(e)} | Type: {type(e).__name__} | "
            f"IP: {client_ip} | Request ID: {request_id} | "
            f"Traceback: {error_traceback}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={
                "error_code": "INTERNAL_SERVER_ERROR",
                "message": "An error occurred while recording tracking data. Please try again.",
                "request_id": request_id
            }
        )

