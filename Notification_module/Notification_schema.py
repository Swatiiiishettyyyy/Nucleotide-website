from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class SendNotificationRequest(BaseModel):
    """Request body for POST /api/notifications/send"""
    user_id: int = Field(..., description="User ID (must match authenticated user)")
    title: str = Field(..., min_length=1, max_length=255)
    message: str = Field(..., min_length=1)
    type: Optional[str] = Field(None, max_length=50, description="e.g. info, warning, success")


class NotificationItem(BaseModel):
    """Single notification in list response"""
    id: int
    title: str
    message: str
    type: Optional[str] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UnreadCountResponse(BaseModel):
    """Response for GET /api/notifications/unread-count"""
    unread_count: int
