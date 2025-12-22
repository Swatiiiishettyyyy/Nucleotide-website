from pydantic import BaseModel, Field, validator
from typing import Optional, Dict, Any
from datetime import datetime, date


class BannerAction(BaseModel):
    """Action object that can have just type or type+value"""
    type: str = Field(..., description="Action type (e.g., 'GENETIC_TEST', 'PRODUCT', 'CATEGORY')")
    value: Optional[str] = Field(None, description="Optional action value (e.g., 'CANCER_PREDISPOSITION')")
    
    class Config:
        schema_extra = {
            "example": {
                "type": "GENETIC_TEST",
                "value": "CANCER_PREDISPOSITION"
            }
        }


class BannerCreate(BaseModel):
    """Schema for creating a new banner"""
    title: Optional[str] = Field(None, description="Banner title", max_length=200)
    subtitle: Optional[str] = Field(None, description="Banner subtitle", max_length=500)
    image_url: Optional[str] = Field(None, description="Banner image URL (will be set after S3 upload)", max_length=500)
    action: Optional[BannerAction] = Field(None, description="Action object with type and optional value")
    position: int = Field(0, description="Display position (lower numbers appear first)", ge=0)
    is_active: bool = Field(True, description="Whether banner is active")
    start_date: Optional[date] = Field(None, description="Start date for banner display (YYYY-MM-DD)")
    end_date: Optional[date] = Field(None, description="End date for banner display (YYYY-MM-DD)")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Ensure end_date is after start_date if both are provided"""
        if v and 'start_date' in values and values['start_date']:
            if v < values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class BannerUpdate(BaseModel):
    """Schema for updating an existing banner"""
    title: Optional[str] = Field(None, description="Banner title", max_length=200)
    subtitle: Optional[str] = Field(None, description="Banner subtitle", max_length=500)
    image_url: Optional[str] = Field(None, description="Banner image URL", max_length=500)
    action: Optional[BannerAction] = Field(None, description="Action object with type and optional value")
    position: Optional[int] = Field(None, description="Display position", ge=0)
    is_active: Optional[bool] = Field(None, description="Whether banner is active")
    start_date: Optional[date] = Field(None, description="Start date for banner display")
    end_date: Optional[date] = Field(None, description="End date for banner display")
    
    @validator('end_date')
    def validate_end_date(cls, v, values):
        """Ensure end_date is after start_date if both are provided"""
        if v and 'start_date' in values and values.get('start_date'):
            if v < values['start_date']:
                raise ValueError('end_date must be after start_date')
        return v


class BannerResponse(BaseModel):
    """Schema for banner response"""
    id: int
    title: Optional[str] = None
    subtitle: Optional[str] = None
    image_url: str
    action: Optional[Dict[str, Any]] = None  # JSON object: {"type": "...", "value": "..."} or {"type": "..."}
    position: int
    is_active: bool
    start_date: Optional[str] = None  # ISO format date string
    end_date: Optional[str] = None  # ISO format date string
    created_at: str  # ISO format datetime string
    updated_at: Optional[str] = None  # ISO format datetime string
    
    class Config:
        orm_mode = True


class BannerListResponse(BaseModel):
    """Schema for list of banners"""
    status: str
    message: str
    data: list[BannerResponse]


class BannerSingleResponse(BaseModel):
    """Schema for single banner response"""
    status: str
    message: str
    data: BannerResponse

