from typing import List, Optional
from pydantic import BaseModel, Field, validator
from datetime import datetime


class ConsentRecordRequest(BaseModel):
    """Request schema for recording consent (for product pages)"""
    product_id: int = Field(..., description="Product ID for which consent is given (1-17)", gt=0)
    consent_value: str = Field(..., description="Consent value: 'yes' or 'no'")
    consent_source: Optional[str] = Field(default="product", description="Source of consent (defaults to 'product')")
    
    @validator('consent_value')
    def validate_consent_value(cls, v):
        v = v.lower().strip()
        if v not in ['yes', 'no']:
            raise ValueError('consent_value must be "yes" or "no"')
        return v
    
    @validator('consent_source')
    def validate_consent_source(cls, v):
        if v is None:
            return "product"
        v = v.lower().strip()
        if v not in ['login', 'product']:
            raise ValueError('consent_source must be "login" or "product"')
        return v
    
    @validator('product_id')
    def validate_product_id(cls, v):
        # For product pages, product_id should be 1-17
        if v not in range(1, 18):
            raise ValueError('product_id must be between 1 and 17 for product consent pages')
        return v


class ConsentBulkRequest(BaseModel):
    """Request schema for bulk consent (login scenario - all products)"""
    consent_value: str = Field(..., description="Consent value: 'yes' or 'no'")
    consent_source: str = Field(default="login", description="Source of consent: 'login' or 'product'")
    
    @validator('consent_value')
    def validate_consent_value(cls, v):
        v = v.lower().strip()
        if v not in ['yes', 'no']:
            raise ValueError('consent_value must be "yes" or "no"')
        return v
    
    @validator('consent_source')
    def validate_consent_source(cls, v):
        v = v.lower().strip()
        if v not in ['login', 'product']:
            raise ValueError('consent_source must be "login" or "product"')
        return v


class ManageConsentRequest(BaseModel):
    """Request schema for manage consent page"""
    product_consents: List[dict] = Field(..., description="List of product consent updates")
    
    class Config:
        schema_extra = {
            "example": {
                "product_consents": [
                    {"product_id": 1, "status": "yes"},
                    {"product_id": 2, "status": "no"}
                ]
            }
        }


class ConsentData(BaseModel):
    """Consent data model"""
    id: int
    user_id: int
    user_phone: str
    product_id: int
    product: Optional[str] = None  # Product name
    consent_given: int
    consent_source: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ConsentBulkData(BaseModel):
    """Consent data model for bulk consent (without product_id)"""
    id: int
    user_id: int
    user_phone: str
    consent_given: int
    consent_source: str
    status: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class ConsentRecordResponse(BaseModel):
    """Response for recording consent"""
    status: str
    message: str
    data: Optional[ConsentData] = None


class ConsentListResponse(BaseModel):
    """Response for listing consents"""
    status: str
    message: str
    data: List[ConsentData]


class ConsentBulkResponse(BaseModel):
    """Response for bulk consent (without product_id in data)"""
    status: str
    message: str
    data: List[ConsentBulkData]


class ManageConsentResponse(BaseModel):
    """Response for manage consent"""
    status: str
    message: str
    data: dict = Field(..., description="Update summary")


class ProductConsentStatus(BaseModel):
    """Product consent status for manage consent page"""
    product_id: int
    product_name: Optional[str] = None
    has_consent: bool
    consent_status: str  # "yes" or "no"
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ManageConsentPageResponse(BaseModel):
    """Response for manage consent page - shows all products with status"""
    status: str
    message: str
    data: List[ProductConsentStatus]

