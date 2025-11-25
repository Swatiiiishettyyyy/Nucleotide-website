from .Address_model import Address
from  .Address_audit_model import AddressAudit
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request
from typing import Optional, Dict, Any
import logging
import json

from .location_validator import is_serviceable_location

logger = logging.getLogger(__name__)

def save_address(db: Session, user, req, request: Optional[Request] = None, correlation_id: Optional[str] = None):
    # Auto-fill city/state/locality from pincode (if not provided)
    locality_options = req.auto_fill_city_state() or []
    
    # If still not filled, allow manual entry (don't block user)
    # But warn if pincode lookup failed
    if not req.city or not req.state:
        msg = (
            f"Could not resolve city/state for pincode {req.postal_code}. "
            "Please provide city and state manually."
        )
        logger.warning(msg)
        raise HTTPException(status_code=422, detail=msg)

    if not is_serviceable_location(req.city, req.locality):
        logger.warning(
            "Address rejected for user %s: city=%s locality=%s not serviceable",
            user.id,
            req.city,
            req.locality,
        )
        raise HTTPException(
            status_code=422,
            detail="Order cannot be delivered to this location."
        )
    
    # Get IP and user agent
    ip_address = None
    user_agent = None
    if request:
        ip_address = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
    
    old_data = None
    
    if req.address_id == 0:
        # Create new address
        address = Address(
            user_id=user.id,
            # Removed: first_name, last_name, email, mobile
            address_label=req.address_label,
            street_address=req.street_address,
            landmark=req.landmark,
            locality=req.locality,
            city=req.city,
            state=req.state,
            postal_code=req.postal_code,
            country=req.country or "India",
            save_for_future=req.save_for_future
        )
        db.add(address)
        db.commit()
        db.refresh(address)
        action = "created"
        new_data = {
            "address_id": address.id,
            "address_label": req.address_label,
            "street_address": req.street_address,
            "landmark": req.landmark,
            "locality": req.locality,
            "city": req.city,
            "state": req.state,
            "postal_code": req.postal_code,
            "country": req.country or "India",
            "save_for_future": req.save_for_future
        }
    else:
        # Edit existing address - capture old data
        address = db.query(Address).filter_by(id=req.address_id, user_id=user.id).first()
        if not address:
            return None
        
        # Check if address is associated with cart items - prevent editing if in cart
        from Cart_module.Cart_model import CartItem
        
        cart_items = db.query(CartItem).filter(
            CartItem.address_id == req.address_id,
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
                detail=f"This address is associated with {len(cart_items)} cart item(s) for product(s): {products_str}. Please remove these items from your cart before editing the address."
            )
        
        # Store old data before update
        old_data = {
            "address_id": address.id,
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
        
        # Removed: first_name, last_name, email, mobile updates
        address.address_label = req.address_label
        address.street_address = req.street_address
        address.landmark = req.landmark
        address.locality = req.locality
        address.city = req.city
        address.state = req.state
        address.postal_code = req.postal_code
        address.country = req.country or "India"
        address.save_for_future = req.save_for_future
        db.commit()
        action = "updated"
        
        new_data = {
            "address_id": address.id,
            "address_label": req.address_label,
            "street_address": req.street_address,
            "landmark": req.landmark,
            "locality": req.locality,
            "city": req.city,
            "state": req.state,
            "postal_code": req.postal_code,
            "country": req.country or "India",
            "save_for_future": req.save_for_future
        }

    # Audit log with IP, user_agent, and old_data/new_data
    # Determine address_label and identifier from new_data or old_data
    address_label = new_data.get("address_label") if new_data else (old_data.get("address_label") if old_data else None)
    address_city = new_data.get("city") if new_data else (old_data.get("city") if old_data else None)
    address_pincode = new_data.get("postal_code") if new_data else (old_data.get("postal_code") if old_data else None)
    address_identifier = f"{address_label} ({address_city} - {address_pincode})" if address_label and address_city and address_pincode else address_label
    
    audit = AddressAudit(
        user_id=user.id,
        username=user.name or user.mobile,
        phone_number=user.mobile,
        address_id=address.id,
        address_label=address_label,
        address_identifier=address_identifier,
        action=action,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(audit)
    db.commit()

    return address, locality_options

def get_addresses_by_user(db, user):
    return db.query(Address).filter_by(user_id=user.id).all()


def delete_address(db: Session, user, address_id: int):
    """Delete an address"""
    address = db.query(Address).filter_by(id=address_id, user_id=user.id).first()
    if not address:
        return None
    
    db.delete(address)
    db.commit()
    return True