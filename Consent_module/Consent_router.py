from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List

from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User
from .Consent_model import ConsentProduct

from .Consent_schema import (
    ConsentRecordRequest,
    ConsentBulkRequest,
    ManageConsentRequest,
    ConsentRecordResponse,
    ConsentListResponse,
    ConsentBulkResponse,
    ConsentBulkData,
    ManageConsentResponse,
    ManageConsentPageResponse,
    ProductConsentStatus
)
from .Consent_crud import (
    record_consent,
    record_bulk_consent,
    update_manage_consent as update_manage_consent_crud,
    get_manage_consent_page_data
)

router = APIRouter(prefix="/consent", tags=["Consent"])


@router.post("/record", response_model=ConsentRecordResponse)
def record_user_consent(
    req: ConsentRecordRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record consent for a single product (product pages only).
    Handles both 'yes' and 'no' consent values.
    - If 'yes': Creates or updates record to 'yes'
    - If 'no': Updates existing record to 'no' (if exists), or returns success without creating record
    
    Used for individual product consent pages (product_id: 1-17).
    consent_source automatically defaults to "product" if not provided.
    """
    try:
        # Ensure consent_source is "product" for this endpoint
        consent_source = req.consent_source or "product"
        
        consent = record_consent(
            db=db,
            user_id=current_user.id,
            user_phone=current_user.mobile,
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


@router.post("/record-bulk", response_model=ConsentBulkResponse)
def record_bulk_user_consent(
    req: ConsentBulkRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Record consent for all products (bulk operation - typically for login scenario).
    When consent_source is 'login' and consent_value is 'yes', creates a single record
    for all products. No product_ids needed in request or response.
    """
    try:
        # For login consent, product_ids are not needed (will use special "All Products" product)
        # Pass empty list as product_ids are not used for login consent
        product_ids = []
        
        consents = record_bulk_consent(
            db=db,
            user_id=current_user.id,
            user_phone=current_user.mobile,
            product_ids=product_ids,
            consent_value=req.consent_value,
            consent_source=req.consent_source
        )
        
        if consents:
            # Convert consent data to exclude product_id
            consent_data = []
            for consent in consents:
                consent_data.append(ConsentBulkData(
                    id=consent.id,
                    user_id=consent.user_id,
                    user_phone=consent.user_phone,
                    consent_given=consent.consent_given,
                    consent_source=consent.consent_source,
                    status=consent.status,
                    created_at=consent.created_at,
                    updated_at=consent.updated_at
                ))
            
            if req.consent_value.lower() == "yes":
                return {
                    "status": "success",
                    "message": "Consent recorded for all products.",
                    "data": consent_data
                }
            else:
                return {
                    "status": "success",
                    "message": "Consent declined for all products.",
                    "data": consent_data
                }
        else:
            # User declined (consent_value = "no") and no record exists
            return {
                "status": "success",
                "message": "Consent declined for all products. No record stored.",
                "data": []
            }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error recording bulk consent: {str(e)}")


@router.get("/manage", response_model=ManageConsentPageResponse)
def get_manage_consent_page(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all products with their consent status for manage consent page.
    Returns list of all products with current consent status (checked/unchecked).
    """
    try:
        products_data = get_manage_consent_page_data(db, current_user.mobile)
        
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
    db: Session = Depends(get_db)
):
    """
    Update consents from manage consent page.
    Accepts list of product consents with product_id and status.
    """
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
            product_consents=product_consents
        )
        
        return {
            "status": "success",
            "message": f"Updated {result['updated']} record(s), created {result['created']} record(s).",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating manage consent: {str(e)}")

