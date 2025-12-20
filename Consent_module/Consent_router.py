from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from deps import get_db
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.User.user_model import User
from Member_module.Member_model import Member
from .Consent_model import ConsentProduct

from .Consent_schema import (
    ConsentRecordRequest,
    ManageConsentRequest,
    ConsentRecordResponse,
    ConsentListResponse,
    ManageConsentResponse,
    ManageConsentPageResponse,
    ProductConsentStatus,
    PartnerConsentRecordRequest,
    PartnerConsentRecordResponse
)
from .Consent_crud import (
    record_consent,
    update_manage_consent as update_manage_consent_crud,
    get_manage_consent_page_data
)
from .Partner_consent_crud import record_partner_consent

router = APIRouter(prefix="/consent", tags=["Consent"])


@router.post("/record", response_model=ConsentRecordResponse)
def record_user_consent(
    req: ConsentRecordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Record consent for a single product (product pages only).
    Handles both 'yes' and 'no' consent values.
    - If 'yes': Creates or updates record to 'yes'
    - If 'no': Updates existing record to 'no' (if exists), or returns success without creating record
    
    Used for individual product consent pages (product_id: 1-17).
    For product_id 11 (Child simulator), use /consent/partner-record endpoint instead.
    consent_source automatically defaults to "product" if not provided.
    Requires an active member profile to be selected.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    # Route product_id 11 to partner consent endpoint
    if req.product_id == 11:
        raise HTTPException(
            status_code=400,
            detail="Product ID 11 requires partner consent. Please use /consent/partner-record endpoint."
        )
    
    try:
        # Ensure consent_source is "product" for this endpoint
        consent_source = req.consent_source or "product"
        
        consent = record_consent(
            db=db,
            user_id=current_user.id,
            user_phone=current_user.mobile,
            member_id=current_member.id,
            product_id=req.product_id,
            consent_value=req.consent_value,
            consent_source=consent_source
        )
        
        if consent:
            if req.consent_value.lower() == "yes":
                return {
                    "status": "success",
                    "message": "Consent recorded successfully.",
                    "data": consent
                }
            else:
                return {
                    "status": "success",
                    "message": "Consent declined successfully.",
                    "data": consent
                }
        else:
            # User declined (consent_value = "no") and no record existed
            return {
                "status": "success",
                "message": "Consent declined. No record stored.",
                "data": None
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording consent: {str(e)}")


@router.post("/partner-record", response_model=PartnerConsentRecordResponse)
def record_partner_consent_endpoint(
    req: PartnerConsentRecordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Record partner consent for Product 11 (Child simulator).
    
    Flow:
    - User (self member) gives consent (yes/no)
    - If user says "yes": Requires partner mobile and partner consent
    - If user says "no": No record created (same as regular consent)
    
    Requires an active member profile to be selected (should be user's self profile).
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        # Record partner consent
        partner_consent = record_partner_consent(
            db=db,
            user_id=current_user.id,
            user_member_id=current_member.id,
            user_name=current_user.name or current_user.mobile,
            user_mobile=current_user.mobile,
            user_consent=req.user_consent,
            product_id=req.product_id,
            partner_mobile=req.partner_mobile,
            partner_name=req.partner_name,
            partner_consent=req.partner_consent,
            consent_source="product"
        )
        
        if partner_consent:
            return {
                "status": "success",
                "message": "Partner consent recorded successfully.",
                "data": partner_consent
            }
        else:
            # User declined (user_consent = "no") and no record was created
            return {
                "status": "success",
                "message": "Consent declined. No record stored.",
                "data": None
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording partner consent: {str(e)}")


@router.get("/manage", response_model=ManageConsentPageResponse)
def get_manage_consent_page(
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Get all products with their consent status for manage consent page.
    Returns list of all products with current consent status (checked/unchecked).
    Requires an active member profile to be selected.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        products_data = get_manage_consent_page_data(db, current_member.id)
        
        # Convert to ProductConsentStatus objects
        result = [
            ProductConsentStatus(
                product_id=item["product_id"],
                product_name=item["product_name"],
                has_consent=item["has_consent"],
                consent_status=item["consent_status"],
                created_at=item["created_at"],
                updated_at=item["updated_at"]
            )
            for item in products_data
        ]
        
        return {
            "status": "success",
            "message": "Manage consent page data retrieved successfully.",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving manage consent data: {str(e)}")


@router.put("/manage", response_model=ManageConsentResponse)
def update_manage_consent(
    req: ManageConsentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Update consents from manage consent page.
    Accepts list of product consents with product_id and status.
    Requires an active member profile to be selected.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        # Validate and format product_consents
        product_consents = []
        for item in req.product_consents:
            if "product_id" not in item:
                continue
            
            product_id = item.get("product_id")
            status = item.get("status", "no").lower()
            
            if status not in ["yes", "no"]:
                continue
            
            # Validate consent product exists
            consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
            if not consent_product:
                continue
            
            product_consents.append({
                "product_id": product_id,
                "status": status
            })
        
        if len(product_consents) == 0:
            return {
                "status": "success",
                "message": "No valid product consents to update.",
                "data": {
                    "updated": 0,
                    "created": 0,
                    "total_processed": 0
                }
            }
        
        result = update_manage_consent_crud(
            db=db,
            user_id=current_user.id,
            user_phone=current_user.mobile,
            member_id=current_member.id,
            product_consents=product_consents
        )
        
        return {
            "status": "success",
            "message": f"Updated {result['updated']} record(s), created {result['created']} record(s).",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating manage consent: {str(e)}")

