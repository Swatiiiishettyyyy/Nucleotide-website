"""
FastAPI router for Google Meet booking and availability APIs.
"""
import os
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from google_auth_oauthlib.flow import Flow

try:
    from .schemas import (
        AvailabilityRequest,
        AvailabilityResponse,
        BookingRequest,
        BookingResponse,
        DeleteAppointmentResponse,
        CounsellorSignupResponse
    )
    from .deps import get_db
    from .models import CounsellorBooking, CounsellorActivityLog, CounsellorToken, CounsellorGmeetList
    from .google_calendar_service import GoogleCalendarService, SCOPES
    from .utils import generate_unique_counsellor_id
except ImportError:
    # Fallback for when running directly (e.g., uvicorn main:app)
    from schemas import (
        AvailabilityRequest,
        AvailabilityResponse,
        BookingRequest,
        BookingResponse,
        DeleteAppointmentResponse,
        CounsellorSignupResponse
    )
    from deps import get_db
    from models import CounsellorBooking, CounsellorActivityLog, CounsellorToken, CounsellorGmeetList
    from google_calendar_service import GoogleCalendarService, SCOPES
    from utils import generate_unique_counsellor_id

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/gmeet", tags=["Google Meet"])

# OAuth Configuration
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')
REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://localhost:8030/gmeet/auth/callback"
)

# Frontend Redirect URLs (optional - if not set, returns JSON)
FRONTEND_SUCCESS_URL = os.getenv("FRONTEND_COUNSELLOR_SUCCESS_URL", None)
FRONTEND_ERROR_URL = os.getenv("FRONTEND_COUNSELLOR_ERROR_URL", None)


def log_activity(
    db: Session,
    counsellor_id: str,
    activity_type: str,
    endpoint: str,
    request_data: Optional[dict] = None,
    response_data: Optional[dict] = None,
    error_message: Optional[str] = None,
    booking_id: Optional[int] = None,
    request: Optional[Request] = None
):
    """Helper function to log activity to database."""
    try:
        log_entry = CounsellorActivityLog(
            booking_id=booking_id,
            counsellor_id=counsellor_id,
            activity_type=activity_type,
            endpoint=endpoint,
            request_data=request_data,
            response_data=response_data,
            error_message=error_message,
            ip_address=request.client.host if request and request.client else None,
            user_agent=request.headers.get("user-agent") if request else None
        )
        db.add(log_entry)
        db.commit()
    except SQLAlchemyError as e:
        logger.error(f"Failed to log activity: {e}")
        db.rollback()


@router.get("/availability", response_model=AvailabilityResponse)
def get_availability(
    request: Request,
    counsellor_id: str,
    start_time: str,
    end_time: str,
    db: Session = Depends(get_db)
):
    """
    Get available time slots for a medical counsellor.
    
    This endpoint fetches the counsellor's calendar and returns available
    time slots between the specified start and end times.
    
    - **counsellor_id**: Unique identifier for the counsellor
    - **start_time**: Start time in ISO format (e.g., 2024-12-10T09:00:00+05:30)
    - **end_time**: End time in ISO format (e.g., 2024-12-10T18:00:00+05:30)
    
    Returns a list of available time slots (default: 30-minute slots).
    """
    try:
        # Validate request using schema
        req = AvailabilityRequest(
            counsellor_id=counsellor_id,
            start_time=start_time,
            end_time=end_time
        )
        
        # Log request
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="availability_check",
            endpoint="/gmeet/availability",
            request_data={
                "counsellor_id": counsellor_id,
                "start_time": start_time,
                "end_time": end_time
            },
            request=request
        )

        # Get availability from Google Calendar
        available_slots = GoogleCalendarService.get_availability(
            counsellor_id=counsellor_id,
            start_time=start_time,
            end_time=end_time,
            db=db,
            slot_duration_minutes=30  # Default 30-minute slots
        )

        response_data = {
            "counsellor_id": counsellor_id,
            "start_time": start_time,
            "end_time": end_time,
            "available_slots": available_slots
        }

        # Log successful response
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="availability_check",
            endpoint="/gmeet/availability",
            response_data=response_data,
            request=request
        )

        return AvailabilityResponse(
            status="success",
            message="Availability fetched successfully",
            counsellor_id=counsellor_id,
            start_time=start_time,
            end_time=end_time,
            available_slots=available_slots
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching availability for counsellor {counsellor_id}: {e}", exc_info=True)
        
        # Log error
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="error",
            endpoint="/gmeet/availability",
            request_data={
                "counsellor_id": counsellor_id,
                "start_time": start_time,
                "end_time": end_time
            },
            error_message=str(e),
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch availability: {str(e)}"
        )


@router.post("/book", response_model=BookingResponse)
def book_appointment(
    request: Request,
    req: BookingRequest,
    db: Session = Depends(get_db)
):
    """
    Book a Google Meet appointment with a medical counsellor.
    
    This endpoint:
    1. Creates a Google Calendar event
    2. Generates a Google Meet link
    3. Sends email invitations (if patient email is provided)
    4. Stores booking information in the database
    
    - **counsellor_id**: Unique identifier for the counsellor
    - **counsellor_member_id**: Member ID associated with the counsellor (required)
    - **patient_name**: Patient's full name (required)
    - **patient_email**: Patient's email (optional - if provided, email invite will be sent)
    - **patient_phone**: Patient's phone number (required)
    - **start_time**: Appointment start time in ISO format
    - **end_time**: Appointment end time in ISO format
    
    Returns booking details including Google Meet link and calendar link.
    """
    try:
        # Log request
        log_activity(
            db=db,
            counsellor_id=req.counsellor_id,
            activity_type="booking_request",
            endpoint="/gmeet/book",
            request_data={
                "counsellor_id": req.counsellor_id,
                "counsellor_member_id": req.counsellor_member_id,
                "patient_name": req.patient_name,
                "patient_email": req.patient_email,
                "patient_phone": req.patient_phone,
                "start_time": req.start_time,
                "end_time": req.end_time
            },
            request=request
        )

        # Get counsellor token to link booking
        token_record = db.query(CounsellorToken).filter(
            CounsellorToken.counsellor_id == req.counsellor_id,
            CounsellorToken.is_active == True
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Calendar not connected for counsellor: {req.counsellor_id}"
            )

        # Create Google Calendar event with Meet link
        event_data = GoogleCalendarService.create_meeting(
            counsellor_id=req.counsellor_id,
            patient_name=req.patient_name,
            patient_email=req.patient_email,
            patient_phone=req.patient_phone,
            start_time=req.start_time,
            end_time=req.end_time,
            db=db
        )

        # Save booking to database
        booking = CounsellorBooking(
            counsellor_id=req.counsellor_id,
            counsellor_member_id=req.counsellor_member_id,
            counsellor_token_id=token_record.id,
            patient_name=req.patient_name,
            patient_email=req.patient_email,
            patient_phone=req.patient_phone,
            start_time=event_data['start'],
            end_time=event_data['end'],
            google_event_id=event_data['google_event_id'],
            meet_link=event_data['meet_link'],
            calendar_link=event_data['calendar_link'],
            status="confirmed"
        )

        db.add(booking)
        db.commit()
        db.refresh(booking)

        # Log successful booking
        log_activity(
            db=db,
            counsellor_id=req.counsellor_id,
            activity_type="booking_created",
            endpoint="/gmeet/book",
            response_data={
                "booking_id": booking.id,
                "google_event_id": event_data['google_event_id'],
                "meet_link": event_data['meet_link']
            },
            booking_id=booking.id,
            request=request
        )

        return BookingResponse(
            status="success",
            message="Appointment booked successfully",
            booking_id=booking.id,
            counsellor_id=req.counsellor_id,
            counsellor_member_id=req.counsellor_member_id,
            google_event_id=event_data['google_event_id'],
            meet_link=event_data['meet_link'] or "",
            calendar_link=event_data['calendar_link'] or "",
            start_time=event_data['start'],
            end_time=event_data['end'],
            patient_name=req.patient_name,
            patient_email=req.patient_email,
            patient_phone=req.patient_phone,
            notifications_sent=bool(req.patient_email)
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error while booking appointment: {e}", exc_info=True)
        db.rollback()
        
        # Log error
        log_activity(
            db=db,
            counsellor_id=req.counsellor_id,
            activity_type="error",
            endpoint="/gmeet/book",
            request_data={
                "counsellor_id": req.counsellor_id,
                "counsellor_member_id": req.counsellor_member_id,
                "patient_name": req.patient_name
            },
            error_message=f"Database error: {str(e)}",
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to save booking to database"
        )
    except Exception as e:
        logger.error(f"Error booking appointment for counsellor {req.counsellor_id}: {e}", exc_info=True)
        
        # Log error
        log_activity(
            db=db,
            counsellor_id=req.counsellor_id,
            activity_type="error",
            endpoint="/gmeet/book",
            request_data={
                "counsellor_id": req.counsellor_id,
                "counsellor_member_id": req.counsellor_member_id,
                "patient_name": req.patient_name
            },
            error_message=str(e),
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to book appointment: {str(e)}"
        )


@router.delete("/appointment/{counsellor_id}/{booking_id}", response_model=DeleteAppointmentResponse)
def delete_appointment(
    request: Request,
    counsellor_id: str,
    booking_id: int,
    send_notifications: bool = True,
    db: Session = Depends(get_db)
):
    """
    Cancel/delete an appointment.
    
    This endpoint:
    1. Deletes the event from Google Calendar
    2. Sends cancellation emails to attendees (if send_notifications=True)
    3. Updates booking status to "cancelled" in database
    4. Logs the activity
    
    - **counsellor_id**: Unique identifier for the counsellor
    - **booking_id**: Database ID of the booking to cancel
    - **send_notifications**: Whether to send cancellation emails (default: True)
    
    Returns confirmation of cancellation.
    """
    try:
        # Find the booking
        booking = db.query(CounsellorBooking).filter(
            CounsellorBooking.id == booking_id,
            CounsellorBooking.counsellor_id == counsellor_id
        ).first()

        if not booking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking {booking_id} not found for counsellor {counsellor_id}"
            )

        if booking.status == "cancelled":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Appointment is already cancelled"
            )

        if not booking.google_event_id:
            # If no Google event ID, just update status in database
            logger.warning(f"Booking {booking_id} has no google_event_id, updating status only")
            booking.status = "cancelled"
            db.commit()
            
            log_activity(
                db=db,
                counsellor_id=counsellor_id,
                activity_type="booking_cancelled",
                endpoint="/gmeet/appointment",
                response_data={
                    "booking_id": booking_id,
                    "status": "cancelled",
                    "note": "No Google event to delete"
                },
                booking_id=booking_id,
                request=request
            )

            return DeleteAppointmentResponse(
                status="success",
                message="Appointment cancelled successfully (no Google Calendar event found)",
                booking_id=booking_id,
                counsellor_id=counsellor_id,
                google_event_id="",
                notifications_sent=False
            )

        # Log request
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="booking_cancellation_request",
            endpoint="/gmeet/appointment",
            request_data={
                "booking_id": booking_id,
                "counsellor_id": counsellor_id,
                "send_notifications": send_notifications
            },
            booking_id=booking_id,
            request=request
        )

        # Delete from Google Calendar
        GoogleCalendarService.delete_meeting(
            counsellor_id=counsellor_id,
            google_event_id=booking.google_event_id,
            db=db,
            send_notifications=send_notifications
        )

        # Update booking status in database (don't delete for audit trail)
        booking.status = "cancelled"
        db.commit()
        db.refresh(booking)

        # Log successful cancellation
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="booking_cancelled",
            endpoint="/gmeet/appointment",
            response_data={
                "booking_id": booking_id,
                "google_event_id": booking.google_event_id,
                "status": "cancelled"
            },
            booking_id=booking_id,
            request=request
        )

        return DeleteAppointmentResponse(
            status="success",
            message="Appointment cancelled successfully",
            booking_id=booking_id,
            counsellor_id=counsellor_id,
            google_event_id=booking.google_event_id,
            notifications_sent=send_notifications
        )

    except HTTPException:
        raise
    except SQLAlchemyError as e:
        logger.error(f"Database error while cancelling appointment: {e}", exc_info=True)
        db.rollback()
        
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="error",
            endpoint="/gmeet/appointment",
            request_data={
                "booking_id": booking_id,
                "counsellor_id": counsellor_id
            },
            error_message=f"Database error: {str(e)}",
            booking_id=booking_id,
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel appointment in database"
        )
    except Exception as e:
        logger.error(f"Error cancelling appointment {booking_id} for counsellor {counsellor_id}: {e}", exc_info=True)
        
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="error",
            endpoint="/gmeet/appointment",
            request_data={
                "booking_id": booking_id,
                "counsellor_id": counsellor_id
            },
            error_message=str(e),
            booking_id=booking_id if 'booking_id' in locals() else None,
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel appointment: {str(e)}"
        )


# ══════════════════════════════════════════════════════════════
# OAUTH ENDPOINTS
# ══════════════════════════════════════════════════════════════

@router.get("/counsellor/connect")
async def universal_counsellor_connect(
    request: Request,
    return_url: Optional[bool] = False,
    db: Session = Depends(get_db)
):
    """
    Universal OAuth endpoint for counsellor self-onboarding.
    
    This endpoint allows any counsellor to connect their Google Calendar
    without requiring a pre-existing counsellor_id. After authorization,
    a unique 6-character counsellor_id is automatically generated.
    
    **Usage:**
    - **Browser**: Call this endpoint directly - it will redirect to Google's OAuth consent screen
    - **API Testing**: Add `?return_url=true` to get JSON response with authorization URL
    
    After authorization, Google redirects to `/gmeet/auth/callback` with
    state="new_counsellor_signup" to identify this flow.
    
    **Query Parameters:**
    - `return_url` (optional): If `true`, returns JSON with authorization URL instead of redirecting
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(CREDENTIALS_FILE):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google credentials.json file not found. Please configure OAuth credentials."
            )

        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Generate authorization URL with special state for universal flow
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Required to get refresh token
            include_granted_scopes='true',
            prompt='consent',  # Force consent screen to get refresh token
            state="new_counsellor_signup"  # Special state to identify universal flow
        )

        # Log OAuth initiation
        log_activity(
            db=db,
            counsellor_id="new_signup",
            activity_type="oauth_universal_initiated",
            endpoint="/gmeet/counsellor/connect",
            request_data={"flow": "universal", "return_url": return_url},
            request=request
        )

        # If return_url=true, return JSON instead of redirecting (for API testing)
        if return_url:
            return {
                "status": "success",
                "message": "Authorization URL generated. Visit this URL in a browser to complete OAuth.",
                "authorization_url": authorization_url,
                "redirect_uri": REDIRECT_URI,
                "note": "This endpoint is designed to be called from a browser. The redirect will take you to Google's OAuth consent screen."
            }

        # Redirect to Google consent screen (default behavior for browsers)
        return RedirectResponse(url=authorization_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating universal OAuth: {e}", exc_info=True)
        
        log_activity(
            db=db,
            counsellor_id="new_signup",
            activity_type="error",
            endpoint="/gmeet/counsellor/connect",
            error_message=str(e),
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/auth/connect/{counsellor_id}")
async def connect_google_calendar(
    counsellor_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Initiate Google OAuth flow for a counsellor.
    
    This endpoint redirects the counsellor to Google's consent screen where they
    grant permission for the application to access their Google Calendar.
    
    After authorization, Google redirects to `/gmeet/auth/callback`.
    
    - **counsellor_id**: Unique identifier for the counsellor
    """
    try:
        # Check if credentials file exists
        if not os.path.exists(CREDENTIALS_FILE):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google credentials.json file not found. Please configure OAuth credentials."
            )

        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Generate authorization URL with counsellor_id as state
        authorization_url, state = flow.authorization_url(
            access_type='offline',  # Required to get refresh token
            include_granted_scopes='true',
            prompt='consent',  # Force consent screen to get refresh token
            state=counsellor_id
        )

        # Log OAuth initiation
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="oauth_initiated",
            endpoint="/gmeet/auth/connect",
            request_data={"counsellor_id": counsellor_id},
            request=request
        )

        # Redirect to Google consent screen
        return RedirectResponse(url=authorization_url)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error initiating OAuth for counsellor {counsellor_id}: {e}", exc_info=True)
        
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="error",
            endpoint="/gmeet/auth/connect",
            request_data={"counsellor_id": counsellor_id},
            error_message=str(e),
            request=request
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initiate OAuth flow: {str(e)}"
        )


@router.get("/auth/callback")
async def oauth_callback(
    request: Request,
    code: str,
    state: str,
    db: Session = Depends(get_db)
):
    """
    Google OAuth callback endpoint.
    
    Handles both:
    1. Universal flow (state="new_counsellor_signup") - creates new counsellor with auto-generated ID
    2. Existing flow (state=counsellor_id) - updates tokens for existing counsellor
    
    - **code**: Authorization code from Google
    - **state**: Either "new_counsellor_signup" or existing counsellor_id
    """
    try:
        if not os.path.exists(CREDENTIALS_FILE):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google credentials.json file not found."
            )

        # Create OAuth flow
        flow = Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=REDIRECT_URI
        )

        # Exchange authorization code for tokens
        flow.fetch_token(code=code)
        credentials = flow.credentials

        # Check if this is universal flow (new counsellor signup)
        if state == "new_counsellor_signup":
            return await handle_universal_flow(
                credentials=credentials,
                db=db,
                request=request
            )
        else:
            # Existing flow with counsellor_id
            return await handle_existing_flow(
                counsellor_id=state,
                credentials=credentials,
                db=db,
                request=request
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in OAuth callback: {e}", exc_info=True)
        
        error_message = "Failed to connect calendar. Please try again."
        
        log_activity(
            db=db,
            counsellor_id=state if 'state' in locals() else "unknown",
            activity_type="error",
            endpoint="/gmeet/auth/callback",
            error_message=str(e),
            request=request
        )

        # Redirect to frontend error page if configured, otherwise return JSON error
        if FRONTEND_ERROR_URL:
            from urllib.parse import urlencode
            
            error_params = urlencode({
                "error": "oauth_failed",
                "message": error_message
            })
            redirect_url = f"{FRONTEND_ERROR_URL}?{error_params}"
            logger.info(f"Redirecting to frontend error page: {redirect_url}")
            return RedirectResponse(url=redirect_url)
        else:
            # Fallback: return JSON error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message
            )


async def handle_universal_flow(
    credentials,
    db: Session,
    request: Request
) -> CounsellorSignupResponse:
    """
    Handle universal OAuth flow for new counsellor signup.
    
    Fetches user info, checks if exists, generates unique ID, creates records.
    """
    try:
        # Fetch user information from Google
        user_info = GoogleCalendarService.fetch_user_info(credentials.token)
        
        # Extract all available fields
        google_user_id = user_info['google_user_id']
        email = user_info['email']
        email_verified = user_info.get('email_verified')
        name = user_info.get('name')
        given_name = user_info.get('given_name')
        family_name = user_info.get('family_name')
        profile_picture_url = user_info.get('profile_picture_url')
        locale = user_info.get('locale')

        # Check if counsellor already exists (by google_user_id or email)
        existing_counsellor = db.query(CounsellorGmeetList).filter(
            (CounsellorGmeetList.google_user_id == google_user_id) |
            (CounsellorGmeetList.email == email)
        ).first()

        is_new = False

        if existing_counsellor:
            # Existing counsellor - update ALL their info and tokens
            counsellor_id = existing_counsellor.counsellor_id
            
            # Update ALL counsellor info fields (in case they changed their Google profile)
            existing_counsellor.email = email  # Update email in case it changed
            existing_counsellor.email_verified = email_verified
            existing_counsellor.name = name
            existing_counsellor.given_name = given_name
            existing_counsellor.family_name = family_name
            existing_counsellor.profile_picture_url = profile_picture_url
            existing_counsellor.locale = locale
            existing_counsellor.is_active = True
            # updated_at is automatically set by onupdate trigger
            
            # Update or create token record
            existing_token = db.query(CounsellorToken).filter(
                CounsellorToken.counsellor_id == counsellor_id
            ).first()

            if existing_token:
                existing_token.access_token = credentials.token
                existing_token.refresh_token = credentials.refresh_token
                existing_token.token_uri = credentials.token_uri
                existing_token.client_id = credentials.client_id
                existing_token.client_secret = credentials.client_secret
                existing_token.scopes = list(credentials.scopes) if credentials.scopes else SCOPES
                existing_token.expires_at = credentials.expiry
                existing_token.is_active = True
            else:
                # Create new token record
                token_record = CounsellorToken(
                    counsellor_id=counsellor_id,
                    access_token=credentials.token,
                    refresh_token=credentials.refresh_token,
                    token_uri=credentials.token_uri or "https://oauth2.googleapis.com/token",
                    client_id=credentials.client_id,
                    client_secret=credentials.client_secret,
                    scopes=list(credentials.scopes) if credentials.scopes else SCOPES,
                    expires_at=credentials.expiry,
                    is_active=True
                )
                db.add(token_record)

            db.commit()
            logger.info(f"Updated existing counsellor: {counsellor_id} ({email})")
            message = "Welcome back! Your calendar has been reconnected successfully."

        else:
            # New counsellor - generate unique ID and create records
            is_new = True
            
            # Generate unique 6-character counsellor_id
            counsellor_id = generate_unique_counsellor_id(db)

            # Create counsellor record with ALL available fields
            new_counsellor = CounsellorGmeetList(
                counsellor_id=counsellor_id,
                google_user_id=google_user_id,
                email=email,
                email_verified=email_verified,
                name=name,
                given_name=given_name,
                family_name=family_name,
                profile_picture_url=profile_picture_url,
                locale=locale,
                is_active=True
            )
            db.add(new_counsellor)

            # Create token record
            token_record = CounsellorToken(
                counsellor_id=counsellor_id,
                access_token=credentials.token,
                refresh_token=credentials.refresh_token,
                token_uri=credentials.token_uri or "https://oauth2.googleapis.com/token",
                client_id=credentials.client_id,
                client_secret=credentials.client_secret,
                scopes=list(credentials.scopes) if credentials.scopes else SCOPES,
                expires_at=credentials.expiry,
                is_active=True
            )
            db.add(token_record)

            db.commit()
            db.refresh(new_counsellor)
            logger.info(f"Created new counsellor: {counsellor_id} ({email})")
            message = "Welcome! Your calendar has been connected successfully."

        # Log successful OAuth completion
        log_activity(
            db=db,
            counsellor_id=counsellor_id,
            activity_type="oauth_universal_completed",
            endpoint="/gmeet/auth/callback",
            response_data={
                "success": True,
                "is_new": is_new,
                "email": email
            },
            request=request
        )

        # Redirect to frontend if URL is configured, otherwise return JSON
        if FRONTEND_SUCCESS_URL:
            from urllib.parse import urlencode
            
            # Build query parameters
            query_params = urlencode({
                "counsellor_id": counsellor_id,
                "name": name or "",
                "email": email,
                "is_new": str(is_new).lower()  # "true" or "false"
            })
            
            redirect_url = f"{FRONTEND_SUCCESS_URL}?{query_params}"
            logger.info(f"Redirecting to frontend success page: {redirect_url}")
            return RedirectResponse(url=redirect_url)
        else:
            # Fallback: return JSON response
            return CounsellorSignupResponse(
                status="success",
                message=message,
                counsellor_id=counsellor_id,
                google_user_id=google_user_id,
                email=email,
                email_verified=email_verified,
                name=name,
                given_name=given_name,
                family_name=family_name,
                profile_picture_url=profile_picture_url,
                locale=locale,
                is_new=is_new
            )

    except Exception as e:
        db.rollback()
        logger.error(f"Error in universal flow: {e}", exc_info=True)
        
        # Handle error redirect or JSON fallback
        error_message = "Failed to connect calendar. Please try again."
        
        if FRONTEND_ERROR_URL:
            from urllib.parse import urlencode
            
            error_params = urlencode({
                "error": "oauth_failed",
                "message": error_message
            })
            redirect_url = f"{FRONTEND_ERROR_URL}?{error_params}"
            logger.info(f"Redirecting to frontend error page: {redirect_url}")
            return RedirectResponse(url=redirect_url)
        else:
            # Fallback: return JSON error
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=error_message
            )


async def handle_existing_flow(
    counsellor_id: str,
    credentials,
    db: Session,
    request: Request
):
    """
    Handle existing OAuth flow for known counsellor_id.
    Updates tokens for existing counsellor.
    """
    # Check if token already exists for this counsellor
    existing_token = db.query(CounsellorToken).filter(
        CounsellorToken.counsellor_id == counsellor_id
    ).first()

    if existing_token:
        # Update existing token
        existing_token.access_token = credentials.token
        existing_token.refresh_token = credentials.refresh_token
        existing_token.token_uri = credentials.token_uri
        existing_token.client_id = credentials.client_id
        existing_token.client_secret = credentials.client_secret
        existing_token.scopes = list(credentials.scopes) if credentials.scopes else SCOPES
        existing_token.expires_at = credentials.expiry
        existing_token.is_active = True
        db.commit()
        db.refresh(existing_token)
        logger.info(f"Updated OAuth token for counsellor: {counsellor_id}")
    else:
        # Create new token record
        token_record = CounsellorToken(
            counsellor_id=counsellor_id,
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_uri=credentials.token_uri or "https://oauth2.googleapis.com/token",
            client_id=credentials.client_id,
            client_secret=credentials.client_secret,
            scopes=list(credentials.scopes) if credentials.scopes else SCOPES,
            expires_at=credentials.expiry,
            is_active=True
        )
        db.add(token_record)
        db.commit()
        db.refresh(token_record)
        logger.info(f"Stored new OAuth token for counsellor: {counsellor_id}")

    # Log successful OAuth completion
    log_activity(
        db=db,
        counsellor_id=counsellor_id,
        activity_type="oauth_completed",
        endpoint="/gmeet/auth/callback",
        response_data={"success": True},
        request=request
    )

    # Redirect to frontend if URL is configured, otherwise return JSON
    if FRONTEND_SUCCESS_URL:
        from urllib.parse import urlencode
        
        # For existing flow, we don't have full user info, so use minimal params
        query_params = urlencode({
            "counsellor_id": counsellor_id,
            "is_new": "false"
        })
        
        redirect_url = f"{FRONTEND_SUCCESS_URL}?{query_params}"
        logger.info(f"Redirecting to frontend success page: {redirect_url}")
        return RedirectResponse(url=redirect_url)
    else:
        # Fallback: return JSON response
        return {
            "status": "success",
            "message": f"Google Calendar connected successfully for counsellor: {counsellor_id}",
            "counsellor_id": counsellor_id
        }

