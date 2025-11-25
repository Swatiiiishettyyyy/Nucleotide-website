import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from Cart_module.Cart_model import CartItem
from Login_module.Utils.auth_user import get_current_user
from deps import get_db
from .Address_crud import delete_address, get_addresses_by_user, save_address
from .Address_schema import (
    AddressListResponse,
    AddressRequest,
    AddressResponse,
    PincodeLookupResponse,
)
from .pincode_service import get_pincode_details

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
    address, locality_options = save_address(db, user, req, request=request, correlation_id=correlation_id)
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
            "locality": address.locality,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "country": address.country,
            "save_for_future": address.save_for_future
        },
        "locality_options": locality_options
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
            "locality": addr.locality,
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


@router.get("/pincode/{postal_code}", response_model=PincodeLookupResponse)
def lookup_pincode(postal_code: str):
    """Fetch city/state/locality options for a pincode."""
    sanitized = postal_code.strip().replace(" ", "")
    if len(sanitized) != 6 or not sanitized.isdigit():
        raise HTTPException(status_code=400, detail="Postal code must be 6 digits")

    city, state, localities = get_pincode_details(sanitized)
    if not city or not state:
        raise HTTPException(
            status_code=404,
            detail=f"Could not find city/state for pincode {sanitized}.",
        )

    return {
        "status": "success",
        "message": "Pincode details fetched successfully.",
        "data": {
            "city": city,
            "state": state,
            "localities": localities,
        },
    }

# Delete address
@router.delete("/delete/{address_id}")
def delete_address_api(
    address_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Delete address. Prevents deletion if address is linked to cart items.
    Note: Addresses can be deleted even if associated with confirmed orders,
    since orders use OrderSnapshot to preserve data integrity.
    """
    from Cart_module.Cart_model import CartItem
    from .Address_model import Address
    from .Address_audit_model import AddressAudit
    import uuid
    
    # Get address before deletion for audit log
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == user.id
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if address is linked to any cart items
    cart_items = db.query(CartItem).filter(
        CartItem.address_id == address_id,
        CartItem.user_id == user.id
    ).all()
    
    if cart_items:
        # Get product names for better error message
        product_names = set()
        for item in cart_items:
            if item.product:
                product_names.add(item.product.Name)
        
        products_str = ", ".join(product_names) if product_names else "items"
        raise HTTPException(
            status_code=422,
            detail=f"This address is associated with {len(cart_items)} cart item(s) for product(s): {products_str}."
        )
    
    # Note: We don't check orders because confirmed orders use OrderSnapshot,
    # so deleting/editing addresses won't affect existing orders
    
    # Store address data before deletion for audit log
    old_data = {
        "address_id": address_id,
        "address_label": address.address_label,
        "street_address": address.street_address,
        "landmark": address.landmark,
        "locality": address.locality,
        "city": address.city,
        "state": address.state,
        "postal_code": address.postal_code,
        "country": address.country,
        "save_for_future": address.save_for_future
    }
    
    # Get IP and user agent for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    # Create address identifier for clear identification
    address_label = address.address_label
    address_identifier = f"{address.address_label} ({address.city} - {address.postal_code})"
    
    # Create audit log for deletion BEFORE deleting the address
    # This ensures the foreign key constraint is satisfied
    audit = AddressAudit(
        user_id=user.id,
        username=user.name or user.mobile,
        phone_number=user.mobile,
        address_id=address_id,  # Address still exists at this point
        address_label=address_label,
        address_identifier=address_identifier,
        action="deleted",
        old_data=old_data,
        new_data=None,  # No new data for deletion
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(audit)
    
    # Now delete the address
    db.delete(address)
    
    # Commit both operations in a single transaction
    db.commit()
    
    return {
        "status": "success",
        "message": "Address deleted successfully."
    }