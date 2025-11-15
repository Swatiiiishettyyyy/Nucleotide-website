from pydantic import BaseModel
from typing import List, Optional

class AddressRequest(BaseModel):
    address_id: int
    first_name: str
    last_name: str
    email: str
    mobile: str
    address_label: str
    street_address: str
    landmark: str
    city: str
    state: str
    postal_code: str
    country: str
    save_for_future: bool

class AddressData(BaseModel):
    address_id: int
    user_id: int
    first_name: str
    last_name: str
    email: str
    mobile: str
    address_label: str
    street_address: str
    landmark: str
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