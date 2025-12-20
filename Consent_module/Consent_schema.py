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
        # Product ID must be a positive integer
        if not isinstance(v, int) or v <= 0:
            raise ValueError('product_id must be a positive integer')
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


# Partner Consent Schemas (for Product 11)
class PartnerConsentRecordRequest(BaseModel):
    """Request schema for recording partner consent (Product 11 - Child simulator)"""
    product_id: int = Field(..., description="Product ID (should be 11 for Child simulator)", gt=0)
    user_consent: str = Field(..., description="User's consent value: 'yes' or 'no'")
    partner_mobile: Optional[str] = Field(None, description="Partner's mobile number (required if user_consent is 'yes')")
    partner_name: Optional[str] = Field(None, description="Partner's name (optional)")
    partner_consent: Optional[str] = Field(None, description="Partner's consent value: 'yes' or 'no' (required if user_consent is 'yes')")
    
    @validator('user_consent')
    def validate_user_consent(cls, v):
        v = v.lower().strip()
        if v not in ['yes', 'no']:
            raise ValueError('user_consent must be "yes" or "no"')
        return v
    
    @validator('partner_mobile')
    def validate_partner_mobile(cls, v, values):
        # For Pydantic v1, need to check values dict carefully
        user_consent = values.get('user_consent', '')
        if isinstance(user_consent, str):
            user_consent = user_consent.lower().strip()
            if user_consent == 'yes' and not v:
                raise ValueError('partner_mobile is required when user_consent is "yes"')
        return v
    
    @validator('partner_consent')
    def validate_partner_consent(cls, v, values):
        # For Pydantic v1, need to check values dict carefully
        user_consent = values.get('user_consent', '')
        if isinstance(user_consent, str):
            user_consent = user_consent.lower().strip()
            if user_consent == 'yes' and not v:
                raise ValueError('partner_consent is required when user_consent is "yes"')
        if v and v.lower().strip() not in ['yes', 'no']:
            raise ValueError('partner_consent must be "yes" or "no"')
        return v.lower().strip() if v else None
    
    @validator('product_id')
    def validate_product_id(cls, v):
        if not isinstance(v, int) or v <= 0:
            raise ValueError('product_id must be a positive integer')
        # Product 11 is for partner consent
        if v != 11:
            raise ValueError('partner_consent endpoint is only for product_id 11 (Child simulator)')
        return v


class PartnerConsentData(BaseModel):
    """Partner consent data model"""
    id: int
    product_id: int
    user_id: int
    user_member_id: int
    user_name: str
    user_mobile: str
    user_consent: str
    partner_user_id: Optional[int] = None
    partner_member_id: Optional[int] = None
    partner_name: Optional[str] = None
    partner_mobile: str
    partner_consent: str
    final_status: str
    consent_source: str
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        orm_mode = True


class PartnerConsentRecordResponse(BaseModel):
    """Response for recording partner consent"""
    status: str
    message: str
    data: Optional[PartnerConsentData] = None

