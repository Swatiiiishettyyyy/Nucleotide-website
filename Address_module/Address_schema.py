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
    address_id: int
    # Removed: first_name, last_name, email, mobile (as per requirements)
    address_label: str
    street_address: str
    landmark: Optional[str] = None
    locality: Optional[str] = None  # Optional - will be auto-filled or selected from list
    city: Optional[str] = None  # Optional - will be auto-filled from pincode if not provided
    state: Optional[str] = None  # Optional - will be auto-filled from pincode if not provided
    postal_code: str  # Pincode - required
    country: Optional[str] = "India"
    save_for_future: bool = True
    
    @validator('postal_code')
    def validate_postal_code(cls, v):
        # Clean and validate pincode
        v = v.strip().replace(" ", "")
        if len(v) != 6 or not v.isdigit():
            raise ValueError('Postal code must be 6 digits')
        return v
    
    def auto_fill_city_state(self):
        """Auto-fill city/state/locality and return available locality options."""
        city, state, locality, locality_options = validate_and_auto_fill_address(
            self.postal_code,
            self.city,
            self.state,
            self.locality
        )
        self.city = city or self.city
        self.state = state or self.state
        self.locality = locality or self.locality
        return locality_options


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
    locality_options: Optional[List[LocalityOption]] = None


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