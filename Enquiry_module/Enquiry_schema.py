"""
Pydantic schemas for enquiry / test request form.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional


class EnquiryRequestCreate(BaseModel):
    """Request body for submitting an enquiry. Preferred key order: name, organization, contact_number, email, number_of_tests, notes."""

    name: str = Field(..., min_length=1, max_length=255, description="Full name")
    organization: Optional[str] = Field(None, max_length=255, description="Organization (optional)")
    contact_number: str = Field(..., min_length=1, max_length=50, description="Contact number")
    email: EmailStr = Field(..., description="Email address")
    number_of_tests: int = Field(..., ge=1, description="Number of tests required")
    notes: Optional[str] = Field(None, description="Notes (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "organization": "Acme Labs",
                "contact_number": "+919876543210",
                "email": "john@example.com",
                "number_of_tests": 5,
                "notes": "Need reports by next week",
            }
        }


class EnquiryResponse(BaseModel):
    """Response after submitting an enquiry."""

    status: str = "success"
    message: str = "Request received! Our team will contact you shortly."
    # Data in order: name, organization, contact_number, email, number_of_tests, notes
    name: str = Field(..., description="Full name")
    organization: Optional[str] = Field(None, description="Organization (optional)")
    contact_number: str = Field(..., description="Contact number")
    email: str = Field(..., description="Email address")
    number_of_tests: int = Field(..., description="Number of tests required")
    notes: Optional[str] = Field(None, description="Notes (optional)")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Request received! Our team will contact you shortly.",
                "name": "John Doe",
                "organization": "Acme Labs",
                "contact_number": "+919876543210",
                "email": "john@example.com",
                "number_of_tests": 5,
                "notes": "Need reports by next week",
            }
        }
