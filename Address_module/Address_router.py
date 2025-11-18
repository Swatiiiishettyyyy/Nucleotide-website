from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from deps import get_db
from .Address_schema import AddressRequest, AddressResponse, AddressListResponse, AddressData
from .Address_crud import save_address, get_addresses_by_user
from Login_module.Utils.auth_user import get_current_user

router = APIRouter(prefix="/address", tags=["Address"])

# Save or update address
@router.post("/save", response_model=AddressResponse)
def save_address_api(
    req: AddressRequest,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    address = save_address(db, user, req)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found for editing")

    return {
        "status": "success",
        "message": "Address saved successfully.",
        "data": {
            "address_id": address.id,
            "user_id": user.id,
            "first_name": address.first_name,
            "last_name": address.last_name,
            "email": address.email,
            "mobile": address.mobile,
            "address_label": address.address_label,
            "street_address": address.street_address,
            "landmark": address.landmark,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "country": address.country,
            "save_for_future": address.save_for_future
        }
    }

# Get all addresses of user
@router.get("/list", response_model=AddressListResponse)
def get_address_list(
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    addresses = get_addresses_by_user(db, user)
    data = []
    for addr in addresses:
        data.append({
            "address_id": addr.id,
            "user_id": user.id,
            "first_name": addr.first_name,
            "last_name": addr.last_name,
            "email": addr.email,
            "mobile": addr.mobile,
            "address_label": addr.address_label,
            "street_address": addr.street_address,
            "landmark": addr.landmark,
            "city": addr.city,
            "state": addr.state,
            "postal_code": addr.postal_code,
            "country": addr.country,
            "save_for_future": addr.save_for_future
        })
    return {
        "status": "success",
        "message": "Address list fetched successfully.",
        "data": data
    }