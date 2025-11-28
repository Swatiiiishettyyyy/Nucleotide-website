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
    # Store original city/state before auto-fill to check if user provided them
    original_city = req.city
    original_state = req.state
    
    # Always lookup pincode to get the actual city (regardless of what user provided)
    # This ensures we validate against the city from pincode lookup, not user input
    from .pincode_service import get_pincode_details
    pincode_city, pincode_state, _ = get_pincode_details(req.postal_code)
    
    # Auto-fill city/state/country from pincode (if not provided)
    # Locality is NOT auto-filled - user must provide it manually
    req.auto_fill_city_state()
    
    # Ensure country is always set (default to India for Indian pincodes)
    if not req.country or req.country.strip() == "":
        req.country = "India"
    
    # Ensure state is set from pincode lookup if available
    if pincode_state and (not req.state or req.state.strip() == ""):
        req.state = pincode_state
    
    # Log what we got from pincode lookup
    logger.info(
        f"Address validation - Pincode: {req.postal_code}, "
        f"Pincode lookup city: '{pincode_city}', Pincode lookup state: '{pincode_state}', "
        f"Original city provided: '{original_city}', Final city: '{req.city}', "
        f"Final state: '{req.state}', Final country: '{req.country}', "
        f"Locality: '{req.locality}'"
    )
    
    # If still not filled, allow manual entry (don't block user)
    # But warn if pincode lookup failed
    if not req.city or not req.state:
        msg = (
            f"Could not resolve city/state for pincode {req.postal_code}. "
            "Please provide city and state manually."
        )
        logger.warning(msg)
        raise HTTPException(status_code=422, detail=msg)

    # Validate that the city is in serviceable locations
    # Validation works regardless of order (city before pincode or pincode before city)
    # Try multiple validation approaches:
    # 1. First, validate using city from pincode lookup (most accurate)
    # 2. Validate using user-provided city (works even if entered before pincode)
    # 3. Validate using final city (after auto-fill)
    # 4. Also check locality as fallback
    validation_passed = False
    validation_method = None
    
    # Priority 1: Validate using city from pincode lookup (most accurate)
    if pincode_city and is_serviceable_location(pincode_city, req.locality):
        validation_passed = True
        validation_method = "pincode_lookup_city"
        logger.info(f"City validation passed using pincode lookup city: '{pincode_city}'")
    
    # Priority 2: Validate using user-provided city (works even if entered before pincode)
    # This handles cases where user enters city first, then pincode
    # We check this regardless of whether it matches pincode city, to handle all scenarios
    if not validation_passed and original_city and original_city.strip():
        if is_serviceable_location(original_city, req.locality):
            validation_passed = True
            validation_method = "user_provided_city"
            logger.info(f"City validation passed using user-provided city: '{original_city}' (entered before/with pincode)")
    
    # Also check user-provided city even if pincode validation passed (for logging/consistency)
    # This ensures we validate user input regardless of order
    if validation_passed and original_city and original_city.strip() and original_city != pincode_city:
        if is_serviceable_location(original_city, req.locality):
            logger.info(f"User-provided city '{original_city}' also validated successfully (backup check)")
    
    # Priority 3: Validate using final city (after auto-fill) - handles edge cases
    if not validation_passed and req.city and req.city.strip():
        if is_serviceable_location(req.city, req.locality):
            validation_passed = True
            validation_method = "final_city"
            logger.info(f"City validation passed using final city: '{req.city}'")
    
    # If all validations failed, reject the address
    if not validation_passed:
        logger.warning(
            "Address rejected for user %s: city from pincode='%s', user-provided city='%s', final city='%s', locality='%s' not serviceable. Pincode: %s. "
            "Validation checked all three city sources.",
            user.id,
            pincode_city,
            original_city,
            req.city,
            req.locality,
            req.postal_code,
        )
        raise HTTPException(
            status_code=422,
            detail="Sample cannot be collected in your location."
        )
    
    logger.info(f"Address validation passed using method: {validation_method}")
    
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

    return address

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