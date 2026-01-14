"""
Tracking Schemas - Pydantic models for request/response validation
"""
from pydantic import BaseModel, Field, validator, root_validator
from typing import Optional, List
from datetime import datetime
import re
import logging

logger = logging.getLogger(__name__)


class DeviceInfo(BaseModel):
    """Device information schema"""
    user_agent: Optional[str] = Field(None, description="User agent string")
    device_type: Optional[str] = Field(None, description="Device type: mobile, desktop, tablet")
    browser: Optional[str] = Field(None, description="Browser name and version")
    os: Optional[str] = Field(None, description="Operating system")
    language: Optional[str] = Field(None, description="Language code (e.g., en-US)")
    timezone: Optional[str] = Field(None, description="Timezone (e.g., America/Los_Angeles)")


class TrackingEventRequest(BaseModel):
    """Request schema for tracking event"""
    ga_consent: bool = Field(..., description="Google Analytics consent flag")
    location_consent: bool = Field(..., description="Location tracking consent flag")
    ga_client_id: Optional[str] = Field(None, max_length=255, description="Google Analytics Client ID")
    session_id: Optional[str] = Field(None, max_length=255, description="Session identifier")
    latitude: Optional[float] = Field(None, ge=-90, le=90, description="Latitude (-90 to 90)")
    longitude: Optional[float] = Field(None, ge=-180, le=180, description="Longitude (-180 to 180)")
    accuracy: Optional[float] = Field(None, ge=0, description="Location accuracy in meters")
    page_url: Optional[str] = Field(None, max_length=500, description="Current page URL")
    referrer: Optional[str] = Field(None, max_length=500, description="Referrer URL")
    device_info: Optional[DeviceInfo] = Field(None, description="Device information")

    @validator('ga_client_id')
    def validate_ga_client_id(cls, v):
        """Validate GA Client ID format if provided"""
        if v is None or v == "":
            return None
        
        v = v.strip()
        if not v:
            return None
        
        # GA Client ID pattern: GA1.2.{10-20 digits}.{10-20 digits}
        pattern = r'^GA1\.2\.\d{10,20}\.\d{10,20}$'
        if not re.match(pattern, v):
            logger.warning(f"Invalid GA Client ID format provided (ignoring): {v[:20]}...")
            return None
        
        return v

    @root_validator
    def validate_conditional_fields(cls, values):
        """Validate that required fields are provided based on consent values"""
        ga_consent = values.get('ga_consent')
        location_consent = values.get('location_consent')
        ga_client_id = values.get('ga_client_id')
        latitude = values.get('latitude')
        longitude = values.get('longitude')
        accuracy = values.get('accuracy')

        # If GA consent is true, ga_client_id should be provided (but not strictly required)
        # If GA consent is false, ga_client_id must be null
        if ga_consent is False:
            if ga_client_id is not None and (not isinstance(ga_client_id, str) or ga_client_id.strip() != ""):
                raise ValueError('ga_client_id must be null when ga_consent is false')
            values['ga_client_id'] = None

        # If location consent is true, latitude and longitude should be provided
        if location_consent is True:
            if latitude is None or longitude is None:
                raise ValueError('latitude and longitude are required when location_consent is true')
        
        # If location consent is false, location fields must be null
        if location_consent is False:
            if latitude is not None or longitude is not None or accuracy is not None:
                raise ValueError('latitude, longitude, and accuracy must be null when location_consent is false')
            values['latitude'] = None
            values['longitude'] = None
            values['accuracy'] = None

        return values


class TrackingEventResponse(BaseModel):
    """Response schema for tracking event"""
    success: bool = Field(default=True, example=True)
    message: str = Field(example="Tracking data recorded successfully")
    data: dict = Field(example={
        "record_id": "550e8400-e29b-41d4-a716-446655440000",
        "user_type": "anonymous",
        "consents": {
            "ga_consent": True,
            "location_consent": True
        },
        "fields_stored": ["ga_client_id", "session_id", "latitude", "longitude"],
        "fields_null": ["user_id"],
        "timestamp": "2026-01-13T15:30:00.000Z"
    })

