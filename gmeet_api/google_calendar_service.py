"""
Google Calendar API service for managing calendar operations.
"""
import os
import uuid
import requests
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
import sys
from pathlib import Path
# Add parent directory to path to import datetime_utils
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
from Login_module.Utils.datetime_utils import to_ist_isoformat
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google.auth.exceptions import RefreshError
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

try:
    from google.auth.transport.requests import Request as GoogleRequest
except ImportError:
    GoogleRequest = None
    logging.getLogger(__name__).warning("google.auth.transport.requests not available. Token refresh may not work.")

try:
    from .models import CounsellorToken
except ImportError:
    from models import CounsellorToken

logger = logging.getLogger(__name__)

# OAuth scopes
SCOPES = [
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'openid'
]

# Path to credentials.json (should be in the project root directory)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CREDENTIALS_FILE = os.path.join(BASE_DIR, 'credentials.json')

# Get redirect URI from environment or use default (port 8030 for Nucleotide-website_v11)
REDIRECT_URI = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI",
    "http://localhost:8030/gmeet/auth/callback"
)

# Allow OAuth over HTTP for local development (remove in production)
if os.getenv("ENVIRONMENT", "development") == "development":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


class GoogleCalendarService:
    """Service class for Google Calendar operations."""

    @staticmethod
    def get_flow(redirect_uri: str) -> Flow:
        """Create OAuth flow instance."""
        if not os.path.exists(CREDENTIALS_FILE):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Google credentials.json file not found. Please configure OAuth credentials."
            )
        
        return Flow.from_client_secrets_file(
            CREDENTIALS_FILE,
            scopes=SCOPES,
            redirect_uri=redirect_uri
        )

    @staticmethod
    def get_calendar_service(counsellor_id: str, db: Session):
        """
        Build Google Calendar service for a counsellor using stored tokens.
        Refreshes token if expired.
        """
        token_record = db.query(CounsellorToken).filter(
            CounsellorToken.counsellor_id == counsellor_id,
            CounsellorToken.is_active == True
        ).first()

        if not token_record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Calendar not connected for counsellor: {counsellor_id}. Please connect Google Calendar first."
            )

        # Build credentials from stored token
        credentials = Credentials(
            token=token_record.access_token,
            refresh_token=token_record.refresh_token,
            token_uri=token_record.token_uri or "https://oauth2.googleapis.com/token",
            client_id=token_record.client_id,
            client_secret=token_record.client_secret,
            scopes=token_record.scopes or SCOPES
        )

        # Refresh token if expired
        if credentials.expired and credentials.refresh_token:
            if GoogleRequest is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Token refresh not available. Please install google-auth-httplib2."
                )
            try:
                credentials.refresh(GoogleRequest())
                # Update stored token
                token_record.access_token = credentials.token
                if credentials.expiry:
                    token_record.expires_at = credentials.expiry
                db.commit()
                logger.info(f"Refreshed token for counsellor: {counsellor_id}")
            except RefreshError as e:
                logger.error(f"Failed to refresh token for counsellor {counsellor_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token expired and refresh failed. Please reconnect Google Calendar."
                )

        return build('calendar', 'v3', credentials=credentials)

    @staticmethod
    def get_availability(
        counsellor_id: str,
        start_time: str,
        end_time: str,
        db: Session,
        slot_duration_minutes: int = 30
    ) -> List[Dict[str, str]]:
        """
        Get available time slots for a counsellor.
        
        Args:
            counsellor_id: Unique identifier for the counsellor
            start_time: Start time in ISO format
            end_time: End time in ISO format
            db: Database session
            slot_duration_minutes: Duration of each slot in minutes (default: 30)
        
        Returns:
            List of available slots with start and end times
        """
        service = GoogleCalendarService.get_calendar_service(counsellor_id, db)

        # Query busy slots using FreeBusy API
        freebusy_query = {
            "timeMin": start_time,
            "timeMax": end_time,
            "timeZone": "Asia/Kolkata",
            "items": [{"id": "primary"}]
        }

        try:
            result = service.freebusy().query(body=freebusy_query).execute()
            busy_slots = result['calendars']['primary']['busy']
        except Exception as e:
            logger.error(f"Error fetching busy slots for counsellor {counsellor_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch calendar availability: {str(e)}"
            )

        # Calculate available slots
        available_slots = GoogleCalendarService._calculate_free_slots(
            start_time, end_time, busy_slots, slot_duration_minutes
        )

        return available_slots

    @staticmethod
    def _calculate_free_slots(
        start_time: str,
        end_time: str,
        busy_slots: List[Dict[str, str]],
        duration_mins: int
    ) -> List[Dict[str, str]]:
        """
        Calculate available slots from busy periods.
        """
        # Parse datetime strings
        tz = timezone(timedelta(hours=5, minutes=30))  # Asia/Kolkata
        
        try:
            work_start = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            if work_start.tzinfo is None:
                work_start = work_start.replace(tzinfo=tz)
            work_end = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
            if work_end.tzinfo is None:
                work_end = work_end.replace(tzinfo=tz)
        except ValueError as e:
            logger.error(f"Invalid datetime format: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid datetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS+TZ:TZ"
            )

        slot_duration = timedelta(minutes=duration_mins)

        # Parse busy periods
        busy_periods = []
        for slot in busy_slots:
            try:
                start = datetime.fromisoformat(slot['start'].replace('Z', '+00:00'))
                end = datetime.fromisoformat(slot['end'].replace('Z', '+00:00'))
                busy_periods.append((start, end))
            except (ValueError, KeyError) as e:
                logger.warning(f"Invalid busy slot format: {slot}, error: {e}")
                continue

        # Find free slots
        available = []
        current = work_start

        while current + slot_duration <= work_end:
            slot_end = current + slot_duration
            is_free = all(
                slot_end <= busy_start or current >= busy_end
                for busy_start, busy_end in busy_periods
            )

            if is_free:
                available.append({
                    "start": to_ist_isoformat(current),
                    "end": to_ist_isoformat(slot_end)
                })

            current += slot_duration

        return available

    @staticmethod
    def create_meeting(
        counsellor_id: str,
        patient_name: str,
        patient_email: Optional[str],
        patient_phone: str,
        start_time: str,
        end_time: str,
        db: Session
    ) -> Dict[str, Any]:
        """
        Create a Google Calendar event with Google Meet link.
        
        Returns:
            Dictionary with event details including meet_link and calendar_link
        """
        service = GoogleCalendarService.get_calendar_service(counsellor_id, db)

        # Build event payload
        attendees = []
        if patient_email:
            attendees.append({'email': patient_email})

        event = {
            'summary': f'Counselling Session - {patient_name}',
            'description': f'Patient: {patient_name}\nPhone: {patient_phone or "N/A"}',
            'start': {
                'dateTime': start_time,
                'timeZone': 'Asia/Kolkata'
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Asia/Kolkata'
            },
            'attendees': attendees,
            'conferenceData': {
                'createRequest': {
                    'requestId': f'meet-{uuid.uuid4()}',
                    'conferenceSolutionKey': {'type': 'hangoutsMeet'}
                }
            },
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 1440},  # 24 hours before
                    {'method': 'email', 'minutes': 60},    # 1 hour before
                    {'method': 'popup', 'minutes': 15}     # 15 minutes before
                ]
            }
        }

        try:
            # Create event with Meet link and send notifications
            created_event = service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all' if patient_email else 'none'  # Send emails only if patient has email
            ).execute()

            # Extract Meet link
            meet_link = None
            if 'conferenceData' in created_event and 'entryPoints' in created_event['conferenceData']:
                meet_link = created_event['conferenceData']['entryPoints'][0].get('uri')

            return {
                'google_event_id': created_event['id'],
                'meet_link': meet_link,
                'calendar_link': created_event.get('htmlLink'),
                'summary': created_event.get('summary'),
                'start': created_event['start']['dateTime'],
                'end': created_event['end']['dateTime']
            }

        except Exception as e:
            logger.error(f"Error creating calendar event for counsellor {counsellor_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create calendar event: {str(e)}"
            )

    @staticmethod
    def delete_meeting(
        counsellor_id: str,
        google_event_id: str,
        db: Session,
        send_notifications: bool = True
    ) -> bool:
        """
        Delete a Google Calendar event.
        
        Args:
            counsellor_id: Unique identifier for the counsellor
            google_event_id: Google Calendar event ID
            db: Database session
            send_notifications: Whether to send cancellation emails to attendees
        
        Returns:
            True if successful
        """
        service = GoogleCalendarService.get_calendar_service(counsellor_id, db)

        try:
            # Delete event from Google Calendar
            service.events().delete(
                calendarId='primary',
                eventId=google_event_id,
                sendUpdates='all' if send_notifications else 'none'
            ).execute()

            logger.info(f"Deleted Google Calendar event {google_event_id} for counsellor {counsellor_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting calendar event {google_event_id} for counsellor {counsellor_id}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete calendar event: {str(e)}"
            )

    @staticmethod
    def fetch_user_info(access_token: str) -> dict:
        """
        Fetch user information from Google using access token.
        Extracts ALL available fields from Google's userinfo endpoint.
        
        Args:
            access_token: OAuth access token
        
        Returns:
            Dictionary with all available user info fields:
            - google_user_id: Google's user ID (id field)
            - email: User's email address
            - email_verified: Whether email is verified
            - name: Full name
            - given_name: First name
            - family_name: Last name
            - profile_picture_url: Profile picture URL
            - locale: Language/region preference
        """
        try:
            response = requests.get(
                'https://www.googleapis.com/oauth2/v2/userinfo',
                headers={'Authorization': f'Bearer {access_token}'},
                timeout=10
            )
            response.raise_for_status()
            user_info = response.json()
            
            # Extract all available fields with None as default for missing fields
            return {
                'google_user_id': user_info.get('id'),  # Google's user ID
                'email': user_info.get('email'),
                'email_verified': user_info.get('verified_email'),  # Google uses 'verified_email'
                'name': user_info.get('name'),
                'given_name': user_info.get('given_name'),
                'family_name': user_info.get('family_name'),
                'profile_picture_url': user_info.get('picture'),
                'locale': user_info.get('locale')
            }
        except requests.exceptions.RequestException as e:
            logger.error(f"Error fetching user info from Google: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch user information from Google: {str(e)}"
            )

