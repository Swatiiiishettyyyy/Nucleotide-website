from .Address_model import Address
from  .Address_audit_model import AddressAudit
from sqlalchemy.orm import Session
from fastapi import HTTPException, Request
from typing import Optional, Dict, Any
import logging
import json

logger = logging.getLogger(__name__)

def save_address(db: Session, user, req, request: Optional[Request] = None, correlation_id: Optional[str] = None):
    # Auto-fill city and state from pincode (if not provided)
    req.auto_fill_city_state()
    
    # If still not filled, allow manual entry (don't block user)
    # But warn if pincode lookup failed
    if not req.city or not req.state:
        logger.warning(f"City/state not auto-filled for pincode {req.postal_code}. User provided manually: city={req.city}, state={req.state}")
        # Don't raise error - allow user to enter manually if pincode service doesn't have the data
    
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
            "address_label": req.address_label,
            "street_address": req.street_address,
            "landmark": req.landmark,
            "city": req.city,
            "state": req.state,
            "postal_code": req.postal_code,
            "country": req.country or "India"
        }
    else:
        # Edit existing address - capture old data
        address = db.query(Address).filter_by(id=req.address_id, user_id=user.id).first()
        if not address:
            return None
        
        # Store old data before update
        old_data = {
            "address_label": address.address_label,
            "street_address": address.street_address,
            "landmark": address.landmark,
            "city": address.city,
            "state": address.state,
            "postal_code": address.postal_code,
            "country": address.country
        }
        
        # Removed: first_name, last_name, email, mobile updates
        address.address_label = req.address_label
        address.street_address = req.street_address
        address.landmark = req.landmark
        address.city = req.city
        address.state = req.state
        address.postal_code = req.postal_code
        address.country = req.country or "India"
        address.save_for_future = req.save_for_future
        db.commit()
        action = "updated"
        
        new_data = {
            "address_label": req.address_label,
            "street_address": req.street_address,
            "landmark": req.landmark,
            "city": req.city,
            "state": req.state,
            "postal_code": req.postal_code,
            "country": req.country or "India"
        }

    # Audit log with IP, user_agent, and old_data/new_data
    audit = AddressAudit(
        user_id=user.id,
        username=user.name or user.mobile,
        phone_number=user.mobile,
        address_id=address.id,
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