"""
CRUD operations for Partner Consent (Product 11 - Child simulator).
Handles OTP-based dual consent flow where both user and partner must consent.
Implements state machine, rate limiting, and expiration handling.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from typing import Optional
from fastapi import HTTPException
import logging
import uuid
from datetime import datetime, timedelta
from Login_module.OTP import otp_manager
from Login_module.Utils.datetime_utils import now_ist, to_ist, IST

from .Consent_model import PartnerConsent, ConsentProduct
from Login_module.User.user_model import User
from Member_module.Member_model import Member

logger = logging.getLogger(__name__)

# Rate limiting constants
MAX_RESENDS = 5  # Max OTP resends per request
COOLDOWN_PERIOD_MINUTES = 10  # Wait time between requests (in minutes)
MAX_DAILY_ATTEMPTS = 10  # Max requests per 24 hours per member
OTP_EXPIRY_MINUTES = 3  # OTP expires in 3 minutes
REQUEST_EXPIRY_HOURS = 1  # Request expires in 1 hour
MAX_FAILED_ATTEMPTS = 3  # Max OTP verification failures


def _partner_otp_key(request_id: str) -> str:
    """Generate Redis key for partner consent OTP"""
    return f"partner_consent_otp:{request_id}"


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


def get_partner_consent_by_request_id(
    db: Session,
    request_id: str
) -> Optional[PartnerConsent]:
    """Get partner consent record by request_id"""
    return db.query(PartnerConsent).filter(
        PartnerConsent.request_id == request_id
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


def find_partner_member_under_same_user(db: Session, user_id: int, partner_mobile: str) -> Optional[Member]:
    """Find partner as member under same user account"""
    return db.query(Member).filter(
        and_(
            Member.user_id == user_id,
            Member.mobile == partner_mobile,
            Member.is_deleted == False
        )
    ).first()


def validate_partner_eligibility(
    db: Session,
    current_user_id: int,
    current_user_mobile: str,
    partner_mobile: str
) -> dict:
    """
    Validate partner eligibility - partner must be either:
    - Scenario A: Registered user (partner_user_id REQUIRED)
    - Scenario B: Member under same user (partner_member_id REQUIRED)
    
    Returns dict with partner_user_id, partner_member_id, partner_name
    Raises HTTPException if partner is not eligible
    """
    # Prevent self-consent
    if partner_mobile == current_user_mobile:
        raise HTTPException(
            status_code=400,
            detail="You cannot use your own phone number as the partner's number."
        )
    
    # Step 1: Check if partner is a registered user
    partner_user = find_partner_user_by_mobile(db, partner_mobile)
    
    if partner_user:
        # Scenario A: Partner is a registered user
        partner_user_id = partner_user.id  # REQUIRED
        partner_member = find_partner_member_by_user_id(db, partner_user_id)
        partner_member_id = partner_member.id if partner_member else None  # Optional
        partner_name = partner_user.name
        
        return {
            "partner_user_id": partner_user_id,
            "partner_member_id": partner_member_id,
            "partner_name": partner_name
        }
    
    # Step 2: Check if partner is a member under same user
    partner_member = find_partner_member_under_same_user(db, current_user_id, partner_mobile)
    
    if partner_member:
        # Scenario B: Partner is a member under same user
        partner_user_id = current_user_id  # REQUIRED (same account)
        partner_member_id = partner_member.id  # REQUIRED
        partner_name = partner_member.name
        
        return {
            "partner_user_id": partner_user_id,
            "partner_member_id": partner_member_id,
            "partner_name": partner_name
        }
    
    # Step 3: Partner is neither user nor member - REJECT
    raise HTTPException(
        status_code=400,
        detail="The partner must be a registered user or added as a family member in your account."
    )


def check_request_expiration(consent: PartnerConsent) -> bool:
    """Check if request has expired (1 hour)"""
    if not consent.request_expires_at:
        return False
    try:
        # Convert database datetime to IST-aware before comparison
        expires_at = to_ist(consent.request_expires_at)
        if expires_at is None:
            return False
        # Ensure both are timezone-aware
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=IST)
        now = now_ist()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        return now >= expires_at
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Error checking request expiration: {e}, expires_at type: {type(consent.request_expires_at)}")
        # If comparison fails, assume not expired to avoid blocking
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking request expiration: {e}")
        return False


def check_otp_expiration(consent: PartnerConsent) -> bool:
    """Check if OTP has expired (3 minutes)"""
    if not consent.otp_expires_at:
        return False
    try:
        # Convert database datetime to IST-aware before comparison
        expires_at = to_ist(consent.otp_expires_at)
        if expires_at is None:
            return False
        # Ensure both are timezone-aware
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=IST)
        now = now_ist()
        if now.tzinfo is None:
            now = now.replace(tzinfo=IST)
        return now >= expires_at
    except (TypeError, ValueError, AttributeError) as e:
        logger.error(f"Error checking OTP expiration: {e}, expires_at type: {type(consent.otp_expires_at)}")
        # If comparison fails, assume not expired to avoid blocking
        return False
    except Exception as e:
        logger.error(f"Unexpected error checking OTP expiration: {e}")
        return False


def check_active_request_exists(
    db: Session,
    user_member_id: int,
    product_id: int = 11
) -> Optional[PartnerConsent]:
    """
    Check if active request exists (not expired/cancelled/declined/revoked).
    Only considers truly active requests (PENDING_REQUEST, OTP_SENT) that haven't expired.
    CONSENT_GIVEN is not considered active - once consent is given, new requests are allowed.
    """
    now = now_ist()
    active_statuses = ["PENDING_REQUEST", "OTP_SENT"]
    
    # Find requests with active status
    active_request = db.query(PartnerConsent).filter(
        and_(
            PartnerConsent.user_member_id == user_member_id,
            PartnerConsent.product_id == product_id,
            PartnerConsent.request_status.in_(active_statuses)
        )
    ).first()
    
    # If found, check if it has expired
    if active_request:
        # Check expiration: if expiration is set and has passed, mark as expired
        if active_request.request_expires_at:
            # Convert database datetime to IST-aware before comparison
            expires_at = to_ist(active_request.request_expires_at)
            if expires_at <= now:
                active_request.request_status = "EXPIRED"
                db.commit()
                return None
    
    return active_request


def check_cooldown_period(
    db: Session,
    user_member_id: int,
    product_id: int = 11
) -> bool:
    """Check if cooldown period has passed (10 minutes)"""
    expired_statuses = ["EXPIRED", "CANCELLED", "DECLINED", "REVOKED_BY_PARTNER"]
    
    recent_request = db.query(PartnerConsent).filter(
        and_(
            PartnerConsent.user_member_id == user_member_id,
            PartnerConsent.product_id == product_id,
            PartnerConsent.request_status.in_(expired_statuses),
            PartnerConsent.last_request_created_at.isnot(None)
        )
    ).order_by(PartnerConsent.last_request_created_at.desc()).first()
    
    if not recent_request or not recent_request.last_request_created_at:
        return True  # No recent request, cooldown passed
    
    # Convert database datetime to IST-aware before calculation
    last_request_at = to_ist(recent_request.last_request_created_at)
    cooldown_end = last_request_at + timedelta(minutes=COOLDOWN_PERIOD_MINUTES)
    return now_ist() >= cooldown_end


def check_daily_attempt_limit(
    db: Session,
    user_member_id: int,
    product_id: int = 11
) -> bool:
    """Check if daily attempt limit reached (10 requests per 24 hours)"""
    twenty_four_hours_ago = now_ist() - timedelta(hours=24)
    
    count = db.query(PartnerConsent).filter(
        and_(
            PartnerConsent.user_member_id == user_member_id,
            PartnerConsent.product_id == product_id,
            PartnerConsent.created_at >= twenty_four_hours_ago
        )
    ).count()
    
    return count < MAX_DAILY_ATTEMPTS


def create_partner_consent_request(
    db: Session,
    user_id: int,
    user_member_id: int,
    user_name: str,
    user_mobile: str,
    product_id: int,
    partner_mobile: str,
    partner_name: Optional[str] = None
) -> PartnerConsent:
    """
    Create or update partner consent request.
    Handles unique constraint by updating existing EXPIRED/CANCELLED/DECLINED record.
    """
    # Validate product
    consent_product = db.query(ConsentProduct).filter(ConsentProduct.id == product_id).first()
    if not consent_product:
        raise HTTPException(status_code=404, detail="We couldn't find this product. Please try again.")
    
    if product_id != 11:
        raise HTTPException(status_code=400, detail="Partner consent is only available for the Child Simulator product.")
    
    # Validate partner eligibility
    partner_info = validate_partner_eligibility(db, user_id, user_mobile, partner_mobile)
    
    # Use provided name or found name
    if not partner_name:
        partner_name = partner_info["partner_name"]
    
    # Generate request_id
    request_id = str(uuid.uuid4())
    
    # Check if existing record exists (for unique constraint handling)
    existing_consent = get_partner_consent_by_member(db, user_member_id, product_id)
    
    now = now_ist()
    request_expires_at = now + timedelta(hours=REQUEST_EXPIRY_HOURS)
    
    if existing_consent and existing_consent.request_status in ["EXPIRED", "CANCELLED", "DECLINED", "REVOKED_BY_PARTNER"]:
        # Update existing record
        existing_consent.request_id = request_id
        existing_consent.user_consent = "yes"
        existing_consent.partner_consent = "pending"
        existing_consent.final_status = "no"
        existing_consent.request_status = "PENDING_REQUEST"
        existing_consent.partner_mobile = partner_mobile
        existing_consent.partner_user_id = partner_info["partner_user_id"]
        existing_consent.partner_member_id = partner_info["partner_member_id"]
        existing_consent.partner_name = partner_name
        existing_consent.consent_source = "partner_otp"
        existing_consent.resend_count = 0
        existing_consent.failed_attempts = 0
        existing_consent.total_attempts += 1
        existing_consent.request_expires_at = request_expires_at
        existing_consent.last_request_created_at = now
        existing_consent.revoked_at = None
        
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
            user_consent="yes",
            partner_user_id=partner_info["partner_user_id"],
            partner_member_id=partner_info["partner_member_id"],
            partner_name=partner_name,
            partner_mobile=partner_mobile,
            partner_consent="pending",
            final_status="no",
            request_status="PENDING_REQUEST",
            request_id=request_id,
            consent_source="partner_otp",
            resend_count=0,
            failed_attempts=0,
            total_attempts=1,
            request_expires_at=request_expires_at,
            last_request_created_at=now
        )
        
        db.add(partner_consent)
        db.commit()
        db.refresh(partner_consent)
        return partner_consent


def send_partner_otp(
    db: Session,
    consent: PartnerConsent
) -> str:
    """
    Generate and send OTP to partner.
    Returns the OTP (for testing/debugging - in production, OTP should be sent via SMS).
    """
    if not consent.request_id:
        raise HTTPException(status_code=400, detail="We couldn't find your consent request. Please try again.")
    
    # Generate OTP
    otp = otp_manager.generate_otp(length=4)
    
    # Store OTP in Redis (expires in 3 minutes)
    otp_key = _partner_otp_key(consent.request_id)
    otp_expiry_seconds = OTP_EXPIRY_MINUTES * 60
    
    try:
        otp_manager._redis_client.set(otp_key, otp, ex=otp_expiry_seconds)
    except Exception as e:
        logger.error(f"Failed to store OTP in Redis: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong while creating the partner consent request. Please try again.")
    
    # Update consent record
    now = now_ist()
    consent.request_status = "OTP_SENT"
    consent.otp_expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    consent.otp_sent_at = now
    
    db.commit()
    db.refresh(consent)
    
    # TODO: Send OTP via SMS service
    # For now, OTP is stored in Redis and can be retrieved for testing
    
    return otp


def verify_partner_otp(
    db: Session,
    request_id: str,
    partner_mobile: str,
    otp: str
) -> PartnerConsent:
    """
    Verify partner OTP.
    Returns the consent record if verification successful.
    """
    # Find consent record
    consent = get_partner_consent_by_request_id(db, request_id)
    if not consent:
        raise HTTPException(status_code=404, detail="We couldn't find your consent request. Please try again.")
    
    # Validate partner mobile matches
    if consent.partner_mobile != partner_mobile:
        raise HTTPException(status_code=400, detail="The partner's phone number doesn't match. Please check and try again.")
    
    # Check request status
    if consent.request_status not in ["PENDING_REQUEST", "OTP_SENT", "OTP_VERIFIED"]:
        raise HTTPException(
            status_code=400,
            detail="This request has expired. Please create a new request."
        )
    
    # Check request expiration (1 hour)
    if check_request_expiration(consent):
        consent.request_status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=400, detail="This request has expired. Please create a new request.")
    
    # Check OTP expiration (3 minutes)
    if check_otp_expiration(consent):
        raise HTTPException(status_code=400, detail="The OTP code has expired. Please request a new one.")
    
    # Get OTP from Redis
    otp_key = _partner_otp_key(request_id)
    stored_otp = None
    try:
        stored_otp = otp_manager._redis_client.get(otp_key)
    except Exception as e:
        logger.error(f"Failed to get OTP from Redis: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong while verifying the OTP. Please try again.")
    
    if not stored_otp:
        raise HTTPException(status_code=400, detail="The OTP code is missing or has expired. Please request a new one.")
    
    # Verify OTP
    if stored_otp != otp:
        # Increment failed attempts
        consent.failed_attempts += 1
        
        if consent.failed_attempts >= MAX_FAILED_ATTEMPTS:
            consent.request_status = "EXPIRED"
            db.commit()
            raise HTTPException(
                status_code=400,
                detail="You've entered the wrong OTP code too many times. This request has expired."
            )
        
        db.commit()
        remaining = MAX_FAILED_ATTEMPTS - consent.failed_attempts
        raise HTTPException(
            status_code=400,
            detail=f"The OTP code you entered is incorrect. You have {remaining} more attempt(s)."
        )
    
    # OTP verified successfully
    # Keep OTP in Redis (don't delete) so it can be used for revocation
    # OTP will naturally expire after OTP_EXPIRY_MINUTES (3 minutes)
    
    # Update consent record - OTP verification means automatic consent (yes)
    consent.request_status = "CONSENT_GIVEN"
    consent.partner_consent = "yes"
    consent.final_status = "yes"  # Both user and partner have consented
    consent.failed_attempts = 0  # Reset on success
    
    db.commit()
    db.refresh(consent)
    
    return consent


def resend_partner_otp(
    db: Session,
    request_id: str,
    user_member_id: int
) -> str:
    """
    Resend OTP to partner (with rate limiting).
    """
    # Find consent record
    consent = get_partner_consent_by_request_id(db, request_id)
    if not consent:
        raise HTTPException(status_code=404, detail="We couldn't find your consent request. Please try again.")
    
    # Validate user is the requester
    if consent.user_member_id != user_member_id:
        raise HTTPException(status_code=403, detail="Only the person who created the request can resend the OTP.")
    
    # Check request status - block if consent already given
    if consent.request_status == "CONSENT_GIVEN":
        raise HTTPException(
            status_code=400,
            detail="Cannot resend OTP. The partner has already verified and given consent."
        )
    
    # Also block if OTP_VERIFIED (for backward compatibility with old records)
    if consent.request_status == "OTP_VERIFIED":
        raise HTTPException(
            status_code=400,
            detail="Cannot resend OTP. The partner has already verified the OTP."
        )
    
    # Check request expiration
    if check_request_expiration(consent):
        consent.request_status = "EXPIRED"
        db.commit()
        raise HTTPException(status_code=400, detail="This request has expired. Please create a new request.")
    
    # Check rate limiting
    if consent.resend_count >= MAX_RESENDS:
        raise HTTPException(
            status_code=400,
            detail="You've reached the maximum number of OTP resends. Please wait for the request to expire and try again."
        )
    
    # Increment resend count
    consent.resend_count += 1
    
    # Send new OTP
    otp = send_partner_otp(db, consent)
    
    return otp


def cancel_partner_consent_request(
    db: Session,
    request_id: str,
    user_member_id: int
) -> PartnerConsent:
    """
    Cancel partner consent request (by user).
    """
    # Find consent record
    consent = get_partner_consent_by_request_id(db, request_id)
    if not consent:
        raise HTTPException(status_code=404, detail="We couldn't find your consent request. Please try again.")
    
    # Validate user is the requester
    if consent.user_member_id != user_member_id:
        raise HTTPException(status_code=403, detail="Only the person who created the request can cancel it.")
    
    # Check request status
    if consent.request_status == "CONSENT_GIVEN":
        raise HTTPException(
            status_code=400,
            detail="Cannot cancel this request. The partner has already given consent."
        )
    
    if consent.request_status == "REVOKED_BY_PARTNER":
        raise HTTPException(
            status_code=400,
            detail="This request has already been cancelled by the partner."
        )
    
    # Log warning for OTP_VERIFIED (for backward compatibility with old records)
    if consent.request_status == "OTP_VERIFIED":
        logger.warning(f"User cancelled request {request_id} after partner verified OTP")
    
    # Update request status
    consent.request_status = "CANCELLED"
    
    db.commit()
    db.refresh(consent)
    
    return consent


def revoke_partner_consent(
    db: Session,
    partner_mobile: str,
    otp: str
) -> PartnerConsent:
    """
    Partner revokes consent (after giving it).
    Requires partner_mobile and OTP for security verification.
    """
    if not partner_mobile:
        raise HTTPException(status_code=400, detail="Partner mobile is required")
    
    if not otp:
        raise HTTPException(status_code=400, detail="OTP is required for revoking consent")
    
    # Find consent record by partner_mobile and status CONSENT_GIVEN
    consent = db.query(PartnerConsent).filter(
        and_(
            PartnerConsent.partner_mobile == partner_mobile,
            PartnerConsent.request_status == "CONSENT_GIVEN"
        )
    ).first()
    
    if not consent:
        raise HTTPException(status_code=404, detail="No active consent found for this partner mobile")
    
    # Verify partner mobile matches
    if consent.partner_mobile != partner_mobile:
        raise HTTPException(status_code=400, detail="The partner's phone number doesn't match. Please check and try again.")
    
    # Verify OTP from Redis (required for security)
    if not consent.request_id:
        raise HTTPException(status_code=400, detail="Request ID is missing, cannot verify OTP")
    
    otp_key = _partner_otp_key(consent.request_id)
    stored_otp = None
    try:
        stored_otp = otp_manager._redis_client.get(otp_key)
    except Exception as e:
        logger.error(f"Failed to get OTP from Redis: {e}")
        raise HTTPException(status_code=500, detail="Something went wrong while verifying the OTP. Please try again.")
    
    if not stored_otp:
        raise HTTPException(
            status_code=400, 
            detail="OTP not found or expired. Please use the OTP that was sent to your mobile number."
        )
    
    if stored_otp != otp:
        raise HTTPException(status_code=400, detail="Invalid OTP")
    
    # Check request status
    if consent.request_status != "CONSENT_GIVEN":
        raise HTTPException(
            status_code=400,
            detail=f"Cannot revoke consent. Request status is {consent.request_status}"
        )
    
    # Update consent record
    consent.partner_consent = "no"
    consent.final_status = "no"
    consent.request_status = "REVOKED_BY_PARTNER"
    consent.revoked_at = now_ist()
    
    db.commit()
    db.refresh(consent)
    
    return consent


def get_partner_consent_status(
    db: Session,
    request_id: str
) -> dict:
    """
    Get partner consent request status.
    """
    consent = get_partner_consent_by_request_id(db, request_id)
    if not consent:
        raise HTTPException(status_code=404, detail="We couldn't find your consent request. Please try again.")
    
    # Check expiration on-demand
    if consent.request_status in ["PENDING_REQUEST", "OTP_SENT", "OTP_VERIFIED"]:
        if check_request_expiration(consent):
            consent.request_status = "EXPIRED"
            db.commit()
    
    return {
        "request_id": consent.request_id,
        "user_member_id": consent.user_member_id,
        "partner_member_id": consent.partner_member_id,
        "request_status": consent.request_status,
        "user_consent": consent.user_consent,
        "partner_consent": consent.partner_consent,
        "final_status": consent.final_status,
        "partner_mobile": consent.partner_mobile,
        "partner_name": consent.partner_name,
        "request_expires_at": consent.request_expires_at.isoformat() if consent.request_expires_at else None,
        "otp_expires_at": consent.otp_expires_at.isoformat() if consent.otp_expires_at else None,
        "created_at": consent.created_at.isoformat() if consent.created_at else None,
        "updated_at": consent.updated_at.isoformat() if consent.updated_at else None
    }


def get_partner_consent_status_by_member(
    db: Session,
    user_member_id: int,
    product_id: int = 11
) -> Optional[dict]:
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
        "request_status": consent.request_status,
        "created_at": consent.created_at,
        "updated_at": consent.updated_at
    }
