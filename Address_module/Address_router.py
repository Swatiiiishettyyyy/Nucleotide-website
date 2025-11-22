from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import uuid

from deps import get_db
from .Address_schema import AddressRequest, AddressResponse, AddressListResponse, AddressData
from .Address_crud import save_address, get_addresses_by_user, delete_address
from Login_module.Utils.auth_user import get_current_user
from Cart_module.Cart_model import CartItem

router = APIRouter(prefix="/address", tags=["Address"])

# Save or update address
@router.post("/save", response_model=AddressResponse)
def save_address_api(
    req: AddressRequest,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    address = save_address(db, user, req, request=request, correlation_id=correlation_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found for editing")

    return {
        "status": "success",
        "message": "Address saved successfully.",
        "data": {
            "address_id": address.id,
            "user_id": user.id,
            # Removed: first_name, last_name, email, mobile
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
            # Removed: first_name, last_name, email, mobile
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

# Delete address
@router.delete("/delete/{address_id}")
def delete_address_api(
    address_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Delete address. Prevents deletion if address is linked to cart items."""
    # Check if address is linked to any cart items (check all, not just first)
    cart_items_count = db.query(CartItem).filter(
        CartItem.address_id == address_id,
        CartItem.user_id == user.id
    ).count()
    
    if cart_items_count > 0:
        raise HTTPException(
            status_code=400,
            detail=f"This address is linked to {cart_items_count} item(s) in your cart. Please remove it from cart items before deleting."
        )
    
    result = delete_address(db, user, address_id)
    if not result:
        raise HTTPException(status_code=404, detail="Address not found")
    
    return {
        "status": "success",
        "message": "Address deleted successfully."
    }