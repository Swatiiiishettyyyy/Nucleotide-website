from pydantic import BaseModel, Field, validator, EmailStr
from typing import Optional


class NewsletterSubscribeRequest(BaseModel):
    """Schema for newsletter subscription request"""
    email: EmailStr = Field(..., description="Email address to subscribe", example="user@example.com")
    
    class Config:
        json_schema_extra = {
            "example": {
                "email": "user@example.com"
            }
        }


class NewsletterSubscribeData(BaseModel):
    """Data returned in subscription response"""
    user_id: Optional[int] = Field(None, description="User ID if authenticated, null if anonymous")
    email: str = Field(..., description="Validated email address")
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 123,
                "email": "user@example.com"
            }
        }


class NewsletterSubscribeResponse(BaseModel):
    """Schema for newsletter subscription response"""
    status: str = "success"
    message: str
    data: NewsletterSubscribeData

