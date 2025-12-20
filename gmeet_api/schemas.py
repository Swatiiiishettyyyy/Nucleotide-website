"""
Pydantic schemas for request and response validation.
"""
from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime


class AvailabilityRequest(BaseModel):
    """Request schema for availability fetching API."""
    counsellor_id: str = Field(..., description="Unique identifier for the counsellor")
    start_time: str = Field(..., description="Start time in ISO format (e.g., 2024-12-10T09:00:00+05:30)")
    end_time: str = Field(..., description="End time in ISO format (e.g., 2024-12-10T18:00:00+05:30)")

    @validator('start_time', 'end_time')
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError("Invalid datetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS+TZ:TZ")


class AvailabilitySlot(BaseModel):
    """Schema for a single availability slot."""
    start: str
    end: str


class AvailabilityResponse(BaseModel):
    """Response schema for availability fetching API."""
    status: str = "success"
    message: str = "Availability fetched successfully"
    counsellor_id: str
    start_time: str
    end_time: str
    available_slots: List[AvailabilitySlot]


class BookingRequest(BaseModel):
    """Request schema for Google Meet booking API."""
    counsellor_id: str = Field(..., description="Unique identifier for the counsellor")
    counsellor_member_id: str = Field(..., description="Member ID associated with the counsellor")
    patient_name: str = Field(..., min_length=1, description="Patient's full name")
    patient_email: Optional[EmailStr] = Field(None, description="Patient's email (optional)")
    patient_phone: str = Field(..., description="Patient's phone number")
    start_time: str = Field(..., description="Start time in ISO format")
    end_time: str = Field(..., description="End time in ISO format")

    @validator('start_time', 'end_time')
    def validate_datetime(cls, v):
        try:
            datetime.fromisoformat(v.replace('Z', '+00:00'))
            return v
        except ValueError:
            raise ValueError("Invalid datetime format. Use ISO format: YYYY-MM-DDTHH:MM:SS+TZ:TZ")

    @validator('end_time')
    def validate_end_after_start(cls, v, values):
        if 'start_time' in values:
            start = datetime.fromisoformat(values['start_time'].replace('Z', '+00:00'))
            end = datetime.fromisoformat(v.replace('Z', '+00:00'))
            if end <= start:
                raise ValueError("end_time must be after start_time")
        return v


class BookingResponse(BaseModel):
    """Response schema for Google Meet booking API."""
    status: str = "success"
    message: str = "Appointment booked successfully"
    booking_id: int
    counsellor_id: str
    counsellor_member_id: str
    google_event_id: str
    meet_link: str
    calendar_link: str
    start_time: str
    end_time: str
    patient_name: str
    patient_email: Optional[str] = None
    patient_phone: str
    notifications_sent: bool = True


class DeleteAppointmentResponse(BaseModel):
    """Response schema for appointment deletion API."""
    status: str = "success"
    message: str = "Appointment cancelled successfully"
    booking_id: int
    counsellor_id: str
    google_event_id: str
    notifications_sent: bool = True


class CounsellorSignupResponse(BaseModel):
    """Response schema for counsellor signup/connection."""
    status: str = "success"
    message: str
    counsellor_id: str
    google_user_id: Optional[str] = None
    email: str
    email_verified: Optional[bool] = None
    name: Optional[str] = None
    given_name: Optional[str] = None
    family_name: Optional[str] = None
    profile_picture_url: Optional[str] = None
    locale: Optional[str] = None
    is_new: bool

