from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import List
import os
import logging

from deps import get_db
from config import settings

logger = logging.getLogger(__name__)
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.User.user_model import User
from Member_module.Member_model import Member
from .Consent_model import ConsentProduct
from config import settings

from .Consent_schema import (
    ConsentRecordRequest,
    ManageConsentRequest,
    ConsentRecordResponse,
    ConsentListResponse,
    ManageConsentResponse,
    ManageConsentPageResponse,
    ProductConsentStatus,
    PartnerConsentRequestRequest,
    PartnerConsentRequestResponse,
    PartnerVerifyOTPRequest,
    PartnerVerifyOTPResponse,
    PartnerResendOTPRequest,
    PartnerResendOTPResponse,
    PartnerCancelRequestRequest,
    PartnerCancelRequestResponse,
    PartnerConsentStatusResponse
)
from .Consent_crud import (
    record_consent,
    update_manage_consent as update_manage_consent_crud,
    get_manage_consent_page_data
)
from .Partner_consent_crud import (
    create_partner_consent_request,
    send_partner_otp,
    verify_partner_otp,
    resend_partner_otp,
    cancel_partner_consent_request,
    get_partner_consent_status,
    check_active_request_exists,
    check_cooldown_period,
    check_daily_attempt_limit,
    MAX_RESENDS
)

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
    For product_id 11 (Child simulator), use /consent/partner-request endpoint instead.
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
            detail="Product ID 11 requires partner consent. Please use /consent/partner-request endpoint."
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
                member_id=item.get("member_id"),
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
    Note: Product 11 (partner consent) cannot be updated via this endpoint.
    Use /consent/partner-request endpoint for Product 11 (OTP-based flow).
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
            
            # Skip Product 11 - requires partner consent flow
            if product_id == 11:
                continue
            
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


# ============================================================================
# OTP-Based Partner Consent Endpoints (Product 11)
# ============================================================================

@router.post("/partner-request", response_model=PartnerConsentRequestResponse)
def initiate_partner_consent_request(
    req: PartnerConsentRequestRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Initiate partner consent request for Product 11 (OTP-based flow).
    
    Flow:
    1. User initiates request (implicitly gives consent by calling this endpoint)
    2. Validates partner eligibility and creates request
    3. Sends OTP to partner's mobile
    4. Returns request_id for tracking
    
    Note: Calling this endpoint means the user has already consented (user_consent = "yes").
    If user wants to decline, they simply don't call this endpoint.
    
    Requires an active member profile to be selected.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        is_resend = False  # Initialize flag
        # Check for active request - if exists, resend OTP instead of creating new
        active_request = check_active_request_exists(db, current_member.id, req.product_id)
        if active_request:
            # Active request exists - resend OTP instead of creating new
            # Check if same partner mobile (for security)
            if active_request.partner_mobile != req.partner_mobile:
                raise HTTPException(
                    status_code=400,
                    detail="Active request exists for a different partner. Please cancel the existing request first."
                )
            
            # Check resend limit
            if active_request.resend_count >= MAX_RESENDS:
                raise HTTPException(
                    status_code=400,
                    detail="Maximum OTP resend attempts reached. Please wait for request to expire and create a new request."
                )
            
            # Resend OTP
            is_resend = True
            active_request.resend_count += 1
            otp = send_partner_otp(db, active_request)
            consent = active_request
        else:
            # No active request - create new one
            # Check cooldown period (only for new requests, not resends)
            if not check_cooldown_period(db, current_member.id, req.product_id):
                raise HTTPException(
                    status_code=400,
                    detail="Please wait 10 minutes before creating a new request."
                )
            
            # Check daily attempt limit
            if not check_daily_attempt_limit(db, current_member.id, req.product_id):
                raise HTTPException(
                    status_code=400,
                    detail="Maximum daily request attempts reached. Please try again tomorrow."
                )
            
            # Create partner consent request
            # User consent is automatically "yes" since they called this endpoint
            consent = create_partner_consent_request(
                db=db,
                user_id=current_user.id,
                user_member_id=current_member.id,
                user_name=current_user.name or current_user.mobile,
                user_mobile=current_user.mobile,
                product_id=req.product_id,
                partner_mobile=req.partner_mobile,
                partner_name=req.partner_name
            )
            
            # Send OTP to partner
            otp = send_partner_otp(db, consent)
        
        # In development/test mode, include OTP in response for testing
        message = "OTP resent to partner" if is_resend else "OTP sent to partner"
        response_data = {
            "request_id": consent.request_id,
            "user_member_id": consent.user_member_id,
            "partner_member_id": consent.partner_member_id,
            "partner_mobile": consent.partner_mobile,
            "partner_name": consent.partner_name,
            "request_expires_at": consent.request_expires_at.isoformat() if consent.request_expires_at else None,
            "otp_expires_at": consent.otp_expires_at.isoformat() if consent.otp_expires_at else None,
            "resend_count": consent.resend_count
        }
        
        # Include OTP in response for testing (4-digit OTP)
        # TODO: Remove OTP from response when Twilio SMS integration is complete
        response_data["otp"] = otp
        response_data["_test_mode"] = True
        response_data["_note"] = "⚠️ TESTING MODE: OTP included in response. Remove in production when Twilio is integrated."
        
        return {
            "status": "success",
            "message": f"{message} at {consent.partner_mobile} (OTP: {otp} - for testing only)",
            "data": response_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error initiating partner consent request: {str(e)}")


@router.post("/partner-verify-otp", response_model=PartnerVerifyOTPResponse)
def verify_partner_otp_endpoint(
    req: PartnerVerifyOTPRequest,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Partner verifies OTP received on their mobile.
    After successful verification, partner can give consent decision.
    """
    try:
        consent = verify_partner_otp(
            db=db,
            request_id=req.request_id,
            partner_mobile=req.partner_mobile,
            otp=req.otp
        )
        
        return {
            "status": "success",
            "message": "OTP verified successfully. Partner consent has been automatically recorded.",
            "data": {
                "request_id": consent.request_id,
                "user_member_id": consent.user_member_id,
                "partner_member_id": consent.partner_member_id,
                "request_status": consent.request_status,
                "partner_mobile": consent.partner_mobile,
                "partner_consent": consent.partner_consent,
                "final_status": consent.final_status
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error verifying OTP: {str(e)}")
@router.post("/partner-resend-otp", response_model=PartnerResendOTPResponse)
def resend_partner_otp_endpoint(
    req: PartnerResendOTPRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Resend OTP to partner (with rate limiting - max 5 resends per request).
    Only the requester can resend OTP.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        otp = resend_partner_otp(
            db=db,
            request_id=req.request_id,
            user_member_id=current_member.id
        )
        
        # Include OTP in response for testing (4-digit OTP)
        # TODO: Remove OTP from response when Twilio SMS integration is complete
        # Get consent record to include member_id
        from .Partner_consent_crud import get_partner_consent_by_request_id
        consent = get_partner_consent_by_request_id(db, req.request_id)
        
        response_data = {
            "request_id": req.request_id,
            "user_member_id": consent.user_member_id if consent else None,
            "partner_member_id": consent.partner_member_id if consent else None,
            "message": "OTP has been resent to partner",
            "otp": otp,
            "_test_mode": True,
            "_note": "⚠️ TESTING MODE: OTP included in response. Remove in production when Twilio is integrated."
        }
        
        return {
            "status": "success",
            "message": f"OTP resent successfully. (OTP: {otp} - for testing only)",
            "data": response_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resending OTP: {str(e)}")


@router.post("/partner-cancel-request", response_model=PartnerCancelRequestResponse)
def cancel_partner_consent_request_endpoint(
    req: PartnerCancelRequestRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Member = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Cancel partner consent request (by requester).
    Cannot cancel if partner has already given consent.
    """
    if not current_member:
        raise HTTPException(
            status_code=400,
            detail="No member profile selected. Please select a member profile first."
        )
    
    try:
        consent = cancel_partner_consent_request(
            db=db,
            request_id=req.request_id,
            user_member_id=current_member.id
        )
        
        return {
            "status": "success",
            "message": "Request cancelled successfully.",
            "data": {
                "request_id": consent.request_id,
                "user_member_id": consent.user_member_id,
                "partner_member_id": consent.partner_member_id,
                "request_status": consent.request_status
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error cancelling request: {str(e)}")


@router.get("/partner-status/{request_id}", response_model=PartnerConsentStatusResponse)
def get_partner_consent_status_endpoint(
    request_id: str,
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Get partner consent request status.
    Can be called by anyone with the request_id.
    """
    try:
        status_data = get_partner_consent_status(db, request_id)
        
        return {
            "status": "success",
            "message": "Request status retrieved successfully.",
            "data": status_data
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving request status: {str(e)}")

