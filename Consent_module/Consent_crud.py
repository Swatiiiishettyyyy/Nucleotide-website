from sqlalchemy.orm import Session
from sqlalchemy import and_
from typing import List, Optional
from fastapi import HTTPException
import logging

from .Consent_model import UserConsent, ConsentProduct

logger = logging.getLogger(__name__)

# Special consent product ID for "All Products" (login consent)
ALL_PRODUCTS_CONSENT_ID = 99999


def get_consent_by_user_and_product(db: Session, user_phone: str, product_id: int) -> Optional[UserConsent]:
    """Get consent record for a specific user and product"""
    return db.query(UserConsent).filter(
        and_(
            UserConsent.user_phone == user_phone,
            UserConsent.product_id == product_id
        )
    ).first()


def get_user_all_products_consent(db: Session, user_phone: str) -> Optional[UserConsent]:
    """Get user's 'All Products' consent record (login consent)"""
    return get_consent_by_user_and_product(db, user_phone, ALL_PRODUCTS_CONSENT_ID)


def has_consent_for_product(db: Session, user_phone: str, product_id: int) -> bool:
    """
    Check if user has consent for a specific product.
    Returns True if user has consent for the specific product_id OR has "All Products" consent.
    """
    # Check for specific product consent
    specific_consent = get_consent_by_user_and_product(db, user_phone, product_id)
    if specific_consent and specific_consent.status == "yes":
        return True
    
    # Check for "All Products" consent
    all_products_consent = get_user_all_products_consent(db, user_phone)
    if all_products_consent and all_products_consent.status == "yes":
        return True
    
    return False


def create_consent(
    db: Session,
    user_id: int,
    user_phone: str,
    product_id: int,
    consent_source: str,
    status: str = "yes"
) -> UserConsent:
    """Create a new consent record"""
    # Get product name from consent_products table
    consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
    product_name = consent_product.name if consent_product else None
    
    consent = UserConsent(
        user_id=user_id,
        user_phone=user_phone,
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
        raise HTTPException(status_code=404, detail=f"Consent product with ID {product_id} not found")
    
    # Prevent using the special "All Products" ID for individual product consents
    if product_id == ALL_PRODUCTS_CONSENT_ID and consent_source.lower() == "product":
        raise HTTPException(
            status_code=400,
            detail=f"Product ID {product_id} is reserved for login consent. Use individual product IDs (1-17)."
        )
    
    # Check if consent already exists
    existing_consent = get_consent_by_user_and_product(db, user_phone, product_id)
    
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
            return create_consent(db, user_id, user_phone, product_id, consent_source, "yes")
    
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


def record_bulk_consent(
    db: Session,
    user_id: int,
    user_phone: str,
    product_ids: List[int],
    consent_value: str,
    consent_source: str = "login"
) -> List[UserConsent]:
    """
    Record consent for multiple products (bulk operation for login scenario).
    When consent_source is 'login' and consent_value is 'yes', creates a single record
    with the special 'All Products' product_id instead of multiple records.
    When consent_source is 'login' and consent_value is 'no', updates existing "All Products"
    consent to "no" if it exists.
    """
    # Special handling for login consent: create/update single "All Products" record
    if consent_source.lower() == "login":
        # Check if user already has "All Products" consent
        existing_consent = get_user_all_products_consent(db, user_phone)
        
        if existing_consent:
            # Update existing record
            if consent_value.lower() == "yes":
                if existing_consent.status == "no":
                    updated_consent = update_consent_status(db, existing_consent, "yes", consent_source)
                    return [updated_consent]
                else:
                    # Already active, just update source if needed
                    if consent_source != existing_consent.consent_source:
                        existing_consent.consent_source = consent_source
                        db.commit()
                        db.refresh(existing_consent)
                    return [existing_consent]
            else:
                # consent_value is "no" - update status to "no"
                if existing_consent.status == "yes":
                    updated_consent = update_consent_status(db, existing_consent, "no", consent_source)
                    return [updated_consent]
                else:
                    # Already "no", just update source if needed
                    if consent_source != existing_consent.consent_source:
                        existing_consent.consent_source = consent_source
                        db.commit()
                        db.refresh(existing_consent)
                    return [existing_consent]
        else:
            # Create new "All Products" consent record only if consent_value is "yes"
            if consent_value.lower() == "yes":
                consent = create_consent(db, user_id, user_phone, ALL_PRODUCTS_CONSENT_ID, consent_source, "yes")
                return [consent]
            else:
                # consent_value is "no" and no record exists - don't create record
                return []
    
    # For non-login sources, process each product_id (existing behavior)
    # Only store if consent_value is 'yes'
    if consent_value.lower() != "yes":
        # Don't store "no" consents for non-login sources
        return []
    
    created_consents = []
    
    for product_id in product_ids:
        # Check if consent product exists
        consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
        if not consent_product:
            logger.warning(f"Consent product {product_id} not found, skipping consent creation")
            continue
        
        # Check if consent already exists
        existing_consent = get_consent_by_user_and_product(db, user_phone, product_id)
        
        if existing_consent:
            # Update existing record
            if existing_consent.status == "no":
                update_consent_status(db, existing_consent, "yes", consent_source)
                created_consents.append(existing_consent)
            else:
                # Already active, just update source if needed
                if consent_source != existing_consent.consent_source:
                    existing_consent.consent_source = consent_source
                    db.commit()
                    db.refresh(existing_consent)
                created_consents.append(existing_consent)
        else:
            # Create new record
            consent = create_consent(db, user_id, user_phone, product_id, consent_source, "yes")
            created_consents.append(consent)
    
    return created_consents


def get_user_consents(db: Session, user_phone: str) -> List[UserConsent]:
    """Get all consent records for a user"""
    return db.query(UserConsent).filter(UserConsent.user_phone == user_phone).all()


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
        
        if status not in ["yes", "no"]:
            continue
        
        # Validate consent product exists
        consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
        if not consent_product:
            logger.warning(f"Consent product {product_id} not found, skipping")
            continue
        
        # Check if consent exists
        existing_consent = get_consent_by_user_and_product(db, user_phone, product_id)
        
        if existing_consent:
            # Update existing record
            if existing_consent.status != status:
                update_consent_status(db, existing_consent, status)
                updated_count += 1
        else:
            # Create new record only if status is "yes"
            # If status is "no" and no record exists, we can skip (nothing to uncheck)
            if status == "yes":
                create_consent(db, user_id, user_phone, product_id, "product", status)
                created_count += 1
    
    return {
        "updated": updated_count,
        "created": created_count,
        "total_processed": len(product_consents)
    }


def get_manage_consent_page_data(db: Session, user_phone: str) -> List[dict]:
    """
    Get all consent products with their consent status for manage consent page.
    Returns list of consent products with consent status.
    If user has "All Products" consent (login consent), all products show as consented.
    """
    # Get all consent products (excluding the special "All Products" product from display)
    all_consent_products = db.query(ConsentProduct).filter(
        ConsentProduct.id != ALL_PRODUCTS_CONSENT_ID
    ).all()
    
    # Get user's existing consents
    user_consents = get_user_consents(db, user_phone)
    consent_map = {consent.product_id: consent for consent in user_consents}
    
    # Check if user has "All Products" consent (login consent)
    all_products_consent = get_user_all_products_consent(db, user_phone)
    has_all_products_consent = all_products_consent is not None and all_products_consent.status == "yes"
    
    result = []
    for consent_product in all_consent_products:
        consent = consent_map.get(consent_product.id)
        
        # If user has "All Products" consent, show all products as consented
        # Otherwise, check specific product consent
        if has_all_products_consent:
            has_consent = True
            consent_status = "yes"
            # Use the "All Products" consent timestamps if no specific product consent exists
            created_at = consent.created_at if consent else all_products_consent.created_at
            updated_at = consent.updated_at if consent else all_products_consent.updated_at
        else:
            has_consent = consent is not None and consent.status == "yes"
            consent_status = consent.status if consent else "no"
            created_at = consent.created_at if consent else None
            updated_at = consent.updated_at if consent else None
        
        result.append({
            "product_id": consent_product.id,
            "product_name": consent_product.name,
            "has_consent": has_consent,
            "consent_status": consent_status,
            "created_at": created_at,
            "updated_at": updated_at
        })
    
    return result

