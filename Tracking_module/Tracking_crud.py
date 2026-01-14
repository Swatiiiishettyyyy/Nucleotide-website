"""
Tracking CRUD operations
"""
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from typing import Optional
from decimal import Decimal
import logging
import bcrypt

from .Tracking_model import TrackingRecord
from Login_module.Utils.datetime_utils import now_ist

logger = logging.getLogger(__name__)


def hash_user_id(user_id: str) -> str:
    """
    Hash user_id using bcrypt with 10 rounds.
    
    Args:
        user_id: Plain text user ID from JWT token
        
    Returns:
        Bcrypt hashed user ID string
    """
    # Generate salt and hash
    salt = bcrypt.gensalt(rounds=10)
    hashed = bcrypt.hashpw(user_id.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def determine_record_type(
    ga_consent: bool,
    location_consent: bool,
    has_location: bool,
    has_page_data: bool
) -> str:
    """
    Determine record type based on data provided.
    
    Returns:
        'consent_update', 'location_update', or 'page_view'
    """
    if location_consent and has_location:
        return 'location_update'
    elif ga_consent and has_page_data:
        return 'page_view'
    else:
        return 'consent_update'


def create_tracking_record(
    db: Session,
    ga_consent: bool,
    location_consent: bool,
    user_id: Optional[str] = None,
    ga_client_id: Optional[str] = None,
    session_id: Optional[str] = None,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
    accuracy: Optional[float] = None,
    page_url: Optional[str] = None,
    referrer: Optional[str] = None,
    user_agent: Optional[str] = None,
    device_type: Optional[str] = None,
    browser: Optional[str] = None,
    operating_system: Optional[str] = None,
    language: Optional[str] = None,
    timezone: Optional[str] = None,
    ip_address: Optional[str] = None
) -> TrackingRecord:
    """
    Create a new tracking record with consent-based data storage.
    
    Args:
        db: Database session
        ga_consent: Google Analytics consent flag
        location_consent: Location tracking consent flag
        user_id: User ID from JWT token (stored as-is, not hashed)
        ga_client_id: Google Analytics Client ID (stored only if ga_consent is True)
        session_id: Session identifier
        latitude: Latitude (stored only if location_consent is True)
        longitude: Longitude (stored only if location_consent is True)
        accuracy: Location accuracy (stored only if location_consent is True)
        page_url: Page URL (stored only if ga_consent is True)
        referrer: Referrer URL (stored only if ga_consent is True)
        user_agent: User agent string (stored only if ga_consent is True)
        device_type: Device type (stored only if ga_consent is True)
        browser: Browser name (stored only if ga_consent is True)
        operating_system: OS name (stored only if ga_consent is True)
        language: Language code (stored only if ga_consent is True)
        timezone: Timezone (stored only if ga_consent is True)
        ip_address: IP address (stored only if ga_consent is True)
        
    Returns:
        Created TrackingRecord object
    """
    try:
        
        # Apply consent-based data storage rules
        # GA consent: only store GA-related data if consent is True
        stored_ga_client_id = ga_client_id if ga_consent else None
        stored_page_url = page_url if ga_consent else None
        stored_referrer = referrer if ga_consent else None
        stored_user_agent = user_agent if ga_consent else None
        stored_device_type = device_type if ga_consent else None
        stored_browser = browser if ga_consent else None
        stored_os = operating_system if ga_consent else None
        stored_language = language if ga_consent else None
        stored_timezone = timezone if ga_consent else None
        stored_ip_address = ip_address if ga_consent else None
        
        # Location consent: only store location data if consent is True
        stored_latitude = Decimal(str(latitude)) if (location_consent and latitude is not None) else None
        stored_longitude = Decimal(str(longitude)) if (location_consent and longitude is not None) else None
        stored_accuracy = accuracy if (location_consent and accuracy is not None) else None
        
        # Determine record type
        has_location = stored_latitude is not None and stored_longitude is not None
        has_page_data = stored_page_url is not None or stored_referrer is not None
        record_type = determine_record_type(ga_consent, location_consent, has_location, has_page_data)
        
        # Log before creating record
        logger.info(
            f"Creating TrackingRecord object | "
            f"user_id parameter: {user_id} | "
            f"user_id type: {type(user_id)} | "
            f"user_id is None: {user_id is None}"
        )
        
        # Create tracking record
        tracking_record = TrackingRecord(
            user_id=user_id,
            ga_client_id=stored_ga_client_id,
            session_id=session_id,
            ga_consent=ga_consent,
            location_consent=location_consent,
            latitude=stored_latitude,
            longitude=stored_longitude,
            accuracy=stored_accuracy,
            page_url=stored_page_url,
            referrer=stored_referrer,
            user_agent=stored_user_agent,
            device_type=stored_device_type,
            browser=stored_browser,
            operating_system=stored_os,
            language=stored_language,
            timezone=stored_timezone,
            ip_address=stored_ip_address,
            record_type=record_type,
            consent_updated_at=now_ist()
        )
        
        db.add(tracking_record)
        db.commit()
        db.refresh(tracking_record)
        
        logger.info(
            f"Tracking record created | Record ID: {tracking_record.record_id} | "
            f"User ID parameter: {user_id if user_id else 'None (anonymous)'} | "
            f"User ID stored in DB: {tracking_record.user_id if tracking_record.user_id else 'NULL'} | "
            f"GA Consent: {ga_consent} | Location Consent: {location_consent} | "
            f"Record Type: {record_type}"
        )
        
        return tracking_record
        
    except IntegrityError as e:
        db.rollback()
        logger.error(
            f"Failed to create tracking record - Integrity error | "
            f"Error: {str(e)}",
            exc_info=True
        )
        raise
    except SQLAlchemyError as e:
        db.rollback()
        logger.error(
            f"Failed to create tracking record - Database error | "
            f"Error: {str(e)}",
            exc_info=True
        )
        raise
    except Exception as e:
        db.rollback()
        logger.error(
            f"Failed to create tracking record - Unexpected error | "
            f"Error: {str(e)} | Type: {type(e).__name__}",
            exc_info=True
        )
        raise

