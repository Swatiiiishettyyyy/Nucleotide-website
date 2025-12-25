import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from Cart_module.Cart_model import CartItem
from Login_module.Utils.auth_user import get_current_user
from Login_module.Utils.datetime_utils import to_ist_isoformat
from deps import get_db
from .Address_crud import delete_address, get_addresses_by_user, save_address
from .Address_schema import (
    AddressListResponse,
    AddressRequest,
    AddressResponse,
    EditAddressRequest,
)

router = APIRouter(prefix="/address", tags=["Address"])

# Create new address
@router.post("/save", response_model=AddressResponse)
def save_address_api(
    req: AddressRequest,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new address (requires authentication).
    Use address_id = 0 for new addresses.
    City name is validated against Locations.xlsx file.
    No pincode lookup or autofill - all fields must be provided manually.
    """
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
            "locality": address.locality,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "country": address.country,
            "save_for_future": address.save_for_future
        }
    }

# Update existing address
@router.put("/edit/{address_id}", response_model=AddressResponse)
def edit_address_api(
    address_id: int,
    req: EditAddressRequest,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Update an existing address (requires authentication).
    
    This endpoint autofills existing address details when address_id is provided.
    You can send only the fields you want to change - missing fields will be autofilled from existing address.
    
    Workflow:
    1. Send PUT request with address_id in path and only fields you want to change in body
    2. Endpoint autofills missing fields from existing address
    3. City name is validated against Locations.xlsx file before saving
    4. Cannot edit address if it's associated with cart items.
    
    Example: To change only city, send: {"city": "New City"}
    All other fields will be autofilled from existing address.
    """
    from .Address_model import Address
    
    # Fetch existing address for autofill
    existing_address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == user.id,
        Address.is_deleted == False
    ).first()
    
    if not existing_address:
        raise HTTPException(status_code=404, detail="Address not found or does not belong to you")
    
    # Autofill: Merge existing address data with request data (request takes precedence)
    # Convert request to dict, keeping only non-None values
    req_dict = req.dict(exclude_unset=True, exclude_none=True)
    
    # Create complete AddressRequest with autofilled data
    complete_req = AddressRequest(
        address_id=address_id,
        postal_code=req_dict.get('postal_code', existing_address.postal_code),
        address_label=req_dict.get('address_label', existing_address.address_label),
        street_address=req_dict.get('street_address', existing_address.street_address),
        landmark=req_dict.get('landmark', existing_address.landmark or ''),
        locality=req_dict.get('locality', existing_address.locality or ''),
        city=req_dict.get('city', existing_address.city),
        state=req_dict.get('state', existing_address.state),
        country=req_dict.get('country', existing_address.country or 'India'),
        save_for_future=req_dict.get('save_for_future', existing_address.save_for_future if existing_address.save_for_future is not None else True)
    )
    
    # Generate correlation ID for request tracing
    correlation_id = str(uuid.uuid4())
    
    # Save address (this will validate city name against excel sheet and update the address)
    address = save_address(db, user, complete_req, request=request, correlation_id=correlation_id)
    if not address:
        raise HTTPException(status_code=404, detail="Address not found or does not belong to you")

    return {
        "status": "success",
        "message": "Address updated successfully.",
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
        Address.user_id == user.id,
        Address.is_deleted == False
    ).first()
    
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")
    
    # Check if address is linked to any cart items (exclude deleted items)
    cart_items = db.query(CartItem).filter(
        CartItem.address_id == address_id,
        CartItem.user_id == user.id,
        CartItem.is_deleted == False
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
    
    # Soft delete the address
    from Login_module.Utils.datetime_utils import now_ist
    address.is_deleted = True
    address.deleted_at = now_ist()
    
    # Create audit log for deletion
    audit = AddressAudit(
        user_id=user.id,
        username=user.name or user.mobile,
        phone_number=user.mobile,
        address_id=address_id,
        address_label=address_label,
        address_identifier=address_identifier,
        action="deleted",
        old_data=old_data,
        new_data={"is_deleted": True, "deleted_at": to_ist_isoformat(address.deleted_at)},
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(audit)
    
    # Commit both operations in a single transaction
    db.commit()
    
    return {
        "status": "success",
        "message": "Address deleted successfully."
    }