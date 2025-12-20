"""
CRUD operations for Partner Consent (Product 11 - Child simulator).
Handles dual consent where both user and partner must consent.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import Optional
from fastapi import HTTPException
import logging

from .Consent_model import PartnerConsent, ConsentProduct
from Login_module.User.user_model import User
from Member_module.Member_model import Member

logger = logging.getLogger(__name__)


def get_partner_consent_by_member(
    db: Session, 
    user_member_id: int, 
    product_id: int = 11
) -> Optional[PartnerConsent]:
    """Get partner consent record for a specific member and product (product_id should be 11)"""
    return db.query(PartnerConsent).filter(
        and_(
            PartnerConsent.user_member_id == user_member_id,
            PartnerConsent.product_id == product_id
        )
    ).first()


def find_partner_user_by_mobile(db: Session, partner_mobile: str) -> Optional[User]:
    """Find user account by mobile number"""
    return db.query(User).filter(User.mobile == partner_mobile).first()


def find_partner_member_by_user_id(db: Session, partner_user_id: int) -> Optional[Member]:
    """Find partner's self member profile (is_self_profile = True)"""
    return db.query(Member).filter(
        and_(
            Member.user_id == partner_user_id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        )
    ).first()


def calculate_final_status(user_consent: str, partner_consent: str) -> str:
    """Calculate final consent status - only 'yes' if both consented"""
    if user_consent.lower() == "yes" and partner_consent.lower() == "yes":
        return "yes"
    return "no"


def record_partner_consent(
    db: Session,
    user_id: int,
    user_member_id: int,
    user_name: str,
    user_mobile: str,
    user_consent: str,
    product_id: int,
    partner_mobile: Optional[str] = None,
    partner_name: Optional[str] = None,
    partner_consent: Optional[str] = None,
    consent_source: str = "product"
) -> Optional[PartnerConsent]:
    """
    Record partner consent for Product 11.
    
    Flow:
    - If user_consent is "no": No record created (return None)
    - If user_consent is "yes": Requires partner_mobile and partner_consent, creates/updates record
    """
    # Validate product exists and is product 11
    consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
    if not consent_product:
        raise HTTPException(status_code=404, detail=f"Consent product with ID {product_id} not found")
    
    if product_id != 11:
        raise HTTPException(status_code=400, detail="Partner consent endpoint is only for product_id 11")
    
    # If user said "no", don't create record (same as regular consent behavior)
    if user_consent.lower() == "no":
        return None
    
    # User said "yes" - partner consent is required
    if not partner_mobile:
        raise HTTPException(status_code=400, detail="partner_mobile is required when user_consent is 'yes'")
    
    if not partner_consent:
        raise HTTPException(status_code=400, detail="partner_consent is required when user_consent is 'yes'")
    
    # Try to find partner's user account
    partner_user = find_partner_user_by_mobile(db, partner_mobile)
    partner_user_id = partner_user.id if partner_user else None
    
    # Try to find partner's member profile
    partner_member_id = None
    if partner_user_id:
        partner_member = find_partner_member_by_user_id(db, partner_user_id)
        partner_member_id = partner_member.id if partner_member else None
    
    # Get partner name if not provided
    if not partner_name and partner_user:
        partner_name = partner_user.name
    
    # Calculate final status
    final_status = calculate_final_status(user_consent, partner_consent)
    
    # Check if partner consent record already exists
    existing_consent = get_partner_consent_by_member(db, user_member_id, product_id)
    
    if existing_consent:
        # Update existing record
        existing_consent.user_consent = user_consent.lower()
        existing_consent.partner_mobile = partner_mobile
        existing_consent.partner_user_id = partner_user_id
        existing_consent.partner_member_id = partner_member_id
        if partner_name:
            existing_consent.partner_name = partner_name
        existing_consent.partner_consent = partner_consent.lower()
        existing_consent.final_status = final_status
        existing_consent.consent_source = consent_source
        
        db.commit()
        db.refresh(existing_consent)
        return existing_consent
    else:
        # Create new record
        partner_consent = PartnerConsent(
            product_id=product_id,
            user_id=user_id,
            user_member_id=user_member_id,
            user_name=user_name,
            user_mobile=user_mobile,
            user_consent=user_consent.lower(),
            partner_user_id=partner_user_id,
            partner_member_id=partner_member_id,
            partner_name=partner_name,
            partner_mobile=partner_mobile,
            partner_consent=partner_consent.lower(),
            final_status=final_status,
            consent_source=consent_source
        )
        
        db.add(partner_consent)
        db.commit()
        db.refresh(partner_consent)
        return partner_consent


def get_partner_consent_status(db: Session, user_member_id: int, product_id: int = 11) -> Optional[dict]:
    """
    Get partner consent status for a member and product.
    Returns None if no record exists, otherwise returns status dict.
    """
    consent = get_partner_consent_by_member(db, user_member_id, product_id)
    
    if not consent:
        return None
    
    return {
        "has_consent": consent.final_status == "yes",
        "user_consent": consent.user_consent,
        "partner_consent": consent.partner_consent,
        "final_status": consent.final_status,
        "created_at": consent.created_at,
        "updated_at": consent.updated_at
    }

