from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from fastapi import HTTPException
import logging

from .Consent_model import UserConsent, ConsentProduct

logger = logging.getLogger(__name__)



def get_consent_by_member_and_product(db: Session, member_id: int, product_id: int) -> Optional[UserConsent]:
    """Get consent record for a specific member and product"""
    return db.query(UserConsent).filter(
        and_(
            UserConsent.member_id == member_id,
            UserConsent.product_id == product_id
        )
    ).first()


def get_consent_by_user_and_product(db: Session, user_phone: str, product_id: int) -> Optional[UserConsent]:
    """Get consent record for a specific user and product (legacy - for backward compatibility)"""
    consent = db.query(UserConsent).filter(
        and_(
            UserConsent.user_phone == user_phone,
            UserConsent.product_id == product_id
        )
    ).first()
    return consent




def has_consent_for_product(db: Session, member_id: int, product_id: int) -> bool:
    """
    Check if member has consent for a specific product.
    Returns True if member has consent for the specific product_id.
    """
    # Check for specific product consent
    specific_consent = get_consent_by_member_and_product(db, member_id, product_id)
    if specific_consent and specific_consent.status == "yes":
        return True
    
    return False


def create_consent(
    db: Session,
    user_id: int,
    user_phone: str,
    member_id: int,
    product_id: int,
    consent_source: str,
    status: str = "yes"
) -> UserConsent:
    """Create a new consent record"""
    # Get product name from consent_products table
    consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
    product_name = consent_product.name if consent_product else None
    
    # Store phone number as plain text
    consent = UserConsent(
        user_id=user_id,
        user_phone=user_phone,
        member_id=member_id,
        product_id=product_id,
        product=product_name,
        consent_given=1,
        consent_source=consent_source,
        status=status
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    
    return consent


def update_consent_status(
    db: Session,
    consent: UserConsent,
    status: str,
    consent_source: Optional[str] = None
) -> UserConsent:
    """Update consent status and optionally consent_source"""
    consent.status = status
    if consent_source:
        consent.consent_source = consent_source
    db.commit()
    db.refresh(consent)
    return consent


def record_consent(
    db: Session,
    user_id: int,
    user_phone: str,
    member_id: int,
    product_id: int,
    consent_value: str,
    consent_source: str
) -> Optional[UserConsent]:
    """
    Record consent for a product.
    Handles both 'yes' and 'no' consent values.
    - If 'yes': Creates new record or updates existing to 'yes'
    - If 'no': Updates existing record to 'no' (if exists), or returns None (no record created)
    """
    # Validate consent product exists
    consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
    if not consent_product:
        logger.warning(
            f"Consent record failed - Product not found | "
            f"Product ID: {product_id} | User ID: {user_id} | Member ID: {member_id}"
        )
        raise HTTPException(status_code=404, detail="We couldn't find this product. Please try again.")
    
    # Check if consent already exists (member-scoped)
    existing_consent = get_consent_by_member_and_product(db, member_id, product_id)
    
    if consent_value.lower() == "yes":
        # User gave consent
        if existing_consent:
            # Update existing record
            # Ensure product name is populated if missing
            if not existing_consent.product:
                existing_consent.product = consent_product.name
            
            if existing_consent.status == "no":
                # Reactivating consent
                return update_consent_status(db, existing_consent, "yes", consent_source)
            else:
                # Already active, just update timestamp and source if needed
                if consent_source != existing_consent.consent_source:
                    existing_consent.consent_source = consent_source
                db.commit()
                db.refresh(existing_consent)
                return existing_consent
        else:
            # Create new record
            return create_consent(db, user_id, user_phone, member_id, product_id, consent_source, "yes")
    
    else:
        # User declined consent (consent_value = "no")
        if existing_consent:
            # Update existing record to "no"
            if existing_consent.status == "yes":
                return update_consent_status(db, existing_consent, "no", consent_source)
            else:
                # Already "no", just update source if needed
                if consent_source != existing_consent.consent_source:
                    existing_consent.consent_source = consent_source
                    db.commit()
                    db.refresh(existing_consent)
                return existing_consent
        else:
            # No record exists and user declined - don't create record
            return None


def get_member_consents(db: Session, member_id: int) -> List[UserConsent]:
    """Get all consent records for a member"""
    return db.query(UserConsent).filter(UserConsent.member_id == member_id).all()


def get_user_consents(db: Session, user_phone: str) -> List[UserConsent]:
    """Get all consent records for a user (legacy - for backward compatibility)"""
    consents = db.query(UserConsent).filter(UserConsent.user_phone == user_phone).all()
    return consents


def get_consents_by_product(db: Session, product_id: int) -> List[UserConsent]:
    """Get all consent records for a specific product"""
    return db.query(UserConsent).filter(
        and_(
            UserConsent.product_id == product_id,
            UserConsent.status == "yes"
        )
    ).all()


def update_manage_consent(
    db: Session,
    user_id: int,
    user_phone: str,
    member_id: int,
    product_consents: List[dict]
) -> dict:
    """
    Update consents from manage consent page.
    product_consents is a list of dicts with product_id and status.
    """
    updated_count = 0
    created_count = 0
    
    for item in product_consents:
        product_id = item.get("product_id")
        status = item.get("status", "no").lower()
        
        # Validate product_id is present and is an integer
        if product_id is None:
            logger.warning("product_id missing in consent item, skipping")
            continue
        
        try:
            product_id = int(product_id)
            if product_id <= 0:
                logger.warning(f"Invalid product_id {product_id}, must be positive integer, skipping")
                continue
        except (ValueError, TypeError):
            logger.warning(f"Invalid product_id type {type(product_id).__name__}, must be integer, skipping")
            continue
        
        if status not in ["yes", "no"]:
            continue
        
        # Validate consent product exists
        consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
        if not consent_product:
            logger.warning(f"Consent product {product_id} not found, skipping")
            continue
        
        # Check if consent exists (member-scoped)
        existing_consent = get_consent_by_member_and_product(db, member_id, product_id)
        
        if existing_consent:
            # Update existing record
            if existing_consent.status != status:
                update_consent_status(db, existing_consent, status)
                updated_count += 1
        else:
            # Create new record only if status is "yes"
            # If status is "no" and no record exists, we can skip (nothing to uncheck)
            if status == "yes":
                # user_phone will be encrypted inside create_consent
                create_consent(db, user_id, user_phone, member_id, product_id, "product", status)
                created_count += 1
    
    return {
        "updated": updated_count,
        "created": created_count,
        "total_processed": len(product_consents)
    }


def get_manage_consent_page_data(db: Session, member_id: int) -> List[dict]:
    """
    Get all consent products with their consent status for manage consent page.
    Returns list of consent products with consent status.
    For Product 11, queries partner_consents table instead of user_consents.
    """
    from .Partner_consent_crud import get_partner_consent_status_by_member
    
    # Get all consent products
    all_consent_products = db.query(ConsentProduct).all()
    
    # Get member's existing consents (for regular products)
    member_consents = get_member_consents(db, member_id)
    consent_map = {consent.product_id: consent for consent in member_consents}
    
    # Get partner consent status for product_id 11 (if exists)
    from .Partner_consent_crud import get_partner_consent_status_by_member
    partner_consent_status = get_partner_consent_status_by_member(db, member_id, product_id=11)
    
    result = []
    for consent_product in all_consent_products:
        # Special handling for Product 11 (partner consent)
        if consent_product.id == 11:
            # Use partner_consent_status already fetched above
            if partner_consent_status and partner_consent_status.get("has_consent"):
                has_consent = True
                consent_status = "yes"
                created_at = partner_consent_status.get("created_at")
                updated_at = partner_consent_status.get("updated_at")
                # For product 11, use the member_id passed to the function
                member_id_value = member_id
            else:
                has_consent = False
                consent_status = "no"
                created_at = None
                updated_at = None
                member_id_value = None
        else:
            # Regular products (1-10, 12-17)
            consent = consent_map.get(consent_product.id)
            has_consent = consent is not None and consent.status == "yes"
            consent_status = consent.status if consent else "no"
            created_at = consent.created_at if consent else None
            updated_at = consent.updated_at if consent else None
            member_id_value = consent.member_id if consent else None
        
        result.append({
            "product_id": consent_product.id,
            "product_name": consent_product.name,
            "member_id": member_id_value,
            "has_consent": has_consent,
            "consent_status": consent_status,
            "created_at": created_at,
            "updated_at": updated_at
        })
    
    return result


def should_show_login_consent(db: Session, member_id: int) -> bool:
    """
    Check if login consent should be shown for a member.
    Returns True if member exists and is not deleted.
    """
    from Member_module.Member_model import Member
    
    # Get member
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        return False
    
    # Show consent (always show if member exists)
    return True

