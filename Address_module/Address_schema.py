from typing import List, Optional

from pydantic import BaseModel, Field, validator

from .pincode_service import validate_and_auto_fill_address


class LocalityOption(BaseModel):
    name: str
    branch_type: Optional[str] = None
    delivery_status: Optional[str] = None
    district: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None


class AddressRequest(BaseModel):
    address_id: int = Field(..., description="Address ID (use 0 for new address)", ge=0)
    # Removed: first_name, last_name, email, mobile (as per requirements)
    address_label: str = Field(..., description="Address label (e.g., 'Home', 'Office')", min_length=1, max_length=50)
    street_address: str = Field(..., description="Street address", min_length=1, max_length=255)
    landmark: str = Field(..., description="Landmark", max_length=255)
    locality: str = Field(..., description="Locality", max_length=150)
    city: str = Field(..., description="City", max_length=100)
    state: str = Field(..., description="State", max_length=100)
    postal_code: str = Field(..., description="Postal code (pincode) - 6 digits", min_length=6, max_length=6)
    country: str = Field(..., description="Country", max_length=100)
    save_for_future: bool = Field(..., description="Save address for future use")
    
    @validator('postal_code')
    def validate_postal_code(cls, v):
        # Clean and validate pincode
        v = v.strip().replace(" ", "")
        if len(v) != 6 or not v.isdigit():
            raise ValueError('Postal code must be 6 digits')
        return v
    
    def auto_fill_city_state(self):
        """Auto-fill city/state/country from pincode. Locality is NOT auto-filled."""
        # Always lookup pincode to get city, state, and country
        # This ensures we auto-fill even if user provided empty strings
        from .pincode_service import get_pincode_details
        pincode_city, pincode_state, _ = get_pincode_details(self.postal_code)
        
        # Use pincode lookup values, but allow user-provided values to override if they exist
        if pincode_city:
            self.city = pincode_city
        if pincode_state:
            self.state = pincode_state
        
        # Country always defaults to India for Indian pincodes
        self.country = "India"
        
        # Locality is NOT auto-filled - user must provide it manually


class AddressData(BaseModel):
    address_id: int
    user_id: int
    # Removed: first_name, last_name, email, mobile
    address_label: str
    street_address: str
    landmark: Optional[str] = None
    locality: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country: str
    save_for_future: Optional[bool] = None


class AddressResponse(BaseModel):
    status: str
    message: str
    data: AddressData


class AddressListResponse(BaseModel):
    status: str
    message: str
    data: List[AddressData]


class PincodeDetails(BaseModel):
    city: Optional[str] = None
    state: Optional[str] = None
    localities: List[LocalityOption] = Field(default_factory=list)


class PincodeLookupResponse(BaseModel):
    status: str
    message: str
    data: PincodeDetails