"""
Phone Change CRUD Operations
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timedelta
from typing import Optional, Tuple
import secrets
import hashlib
import logging
import re

from .PhoneChange_model import PhoneChangeRequest, PhoneChangeAuditLog, PhoneChangeStatus
from Login_module.User.user_model import User
from Login_module.User.user_session_crud import get_user_by_id
from Member_module.Member_model import Member
from Login_module.Utils.datetime_utils import now_ist, to_ist
from Login_module.OTP import otp_manager

logger = logging.getLogger(__name__)

# Constants
OTP_EXPIRY_SECONDS = 180  # 3 minutes
SESSION_TOKEN_EXPIRY_SECONDS = 600  # 10 minutes
MAX_OTP_ATTEMPTS = 3
COOLDOWN_SECONDS = 900  # 15 minutes
REQUEST_EXPIRY_SECONDS = 600  # 10 minutes (for abandoned requests)
MAX_REQUESTS_PER_DAY = 10
OTP_LENGTH = 4


def normalize_phone(phone: str) -> str:
    """Normalize phone number by removing spaces and dashes"""
    return re.sub(r'[\s\-]', '', phone) if phone else ""


def generate_session_token() -> str:
    """Generate cryptographically secure random session token"""
    return secrets.token_urlsafe(32)


def hash_otp(otp: str) -> str:
    """Hash OTP using SHA256 (for audit purposes, actual OTP stored in Redis)"""
    return hashlib.sha256(otp.encode()).hexdigest()


def create_audit_log(
    db: Session,
    user_id: int,
    request_id: Optional[int],
    action: str,
    status: str,
    success: bool = True,
    error_message: Optional[str] = None,
    details: Optional[dict] = None,
    ip_address: Optional[str] = None
) -> PhoneChangeAuditLog:
    """Create audit log entry"""
    log = PhoneChangeAuditLog(
        user_id=user_id,
        request_id=request_id,
        action=action,
        status=status,
        success=1 if success else 0,
        error_message=error_message,
        details=details or {},
        ip_address=ip_address,
        timestamp=now_ist()
    )
    db.add(log)
    db.flush()
    return log


def check_rate_limit(db: Session, user_id: int) -> Tuple[bool, Optional[str]]:
    """
    Check if user has exceeded daily rate limit (10 requests per day)
    Returns (is_allowed, error_message)
    """
    # Check requests in last 24 hours
    yesterday = now_ist() - timedelta(days=1)
    recent_requests = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.user_id == user_id,
        PhoneChangeRequest.created_at >= yesterday
    ).count()
    
    if recent_requests >= MAX_REQUESTS_PER_DAY:
        return False, f"Maximum {MAX_REQUESTS_PER_DAY} phone change requests per day. Please try again tomorrow."
    
    return True, None


def cancel_active_requests(db: Session, user_id: int) -> int:
    """Cancel all active requests for user (except completed/cancelled/expired)"""
    active_statuses = [
        PhoneChangeStatus.OLD_NUMBER_PENDING.value,
        PhoneChangeStatus.OLD_NUMBER_VERIFIED.value,
        PhoneChangeStatus.NEW_NUMBER_PENDING.value
    ]
    
    cancelled = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.user_id == user_id,
        PhoneChangeRequest.status.in_(active_statuses)
    ).update({
        PhoneChangeRequest.status: PhoneChangeStatus.CANCELLED.value
    })
    
    db.flush()
    return cancelled


def get_or_create_request(
    db: Session,
    user_id: int,
    old_phone: str,
    ip_address: Optional[str] = None
) -> Tuple[PhoneChangeRequest, bool]:
    """
    Get existing active request or create new one
    Returns (request, is_new)
    """
    # Check for existing active request
    active_statuses = [
        PhoneChangeStatus.OLD_NUMBER_PENDING.value,
        PhoneChangeStatus.OLD_NUMBER_VERIFIED.value,
        PhoneChangeStatus.NEW_NUMBER_PENDING.value
    ]
    
    existing = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.user_id == user_id,
        PhoneChangeRequest.status.in_(active_statuses)
    ).first()
    
    if existing:
        # Check if request is too old (> 10 minutes)
        # Normalize created_at to IST for comparison
        created_at_ist = to_ist(existing.created_at)
        if created_at_ist and created_at_ist < now_ist() - timedelta(seconds=REQUEST_EXPIRY_SECONDS):
            # Auto-expire old request
            existing.status = PhoneChangeStatus.EXPIRED.value
            db.flush()
            create_audit_log(
                db, user_id, existing.id, "auto_expire",
                PhoneChangeStatus.EXPIRED.value, True, None, None, ip_address
            )
        else:
            # Return existing request - refresh to ensure it's up to date
            db.refresh(existing)
            return existing, False
    
    # Cancel any other active requests (shouldn't happen, but safety check)
    cancel_active_requests(db, user_id)
    
    # Create new request
    request = PhoneChangeRequest(
        user_id=user_id,
        old_phone=old_phone,
        status=PhoneChangeStatus.OLD_NUMBER_PENDING.value,
        expires_at=now_ist() + timedelta(seconds=REQUEST_EXPIRY_SECONDS),
        ip_address=ip_address
    )
    db.add(request)
    db.flush()
    db.refresh(request)
    
    create_audit_log(
        db, user_id, request.id, "request_created",
        PhoneChangeStatus.OLD_NUMBER_PENDING.value, True, None,
        {"old_phone": old_phone}, ip_address
    )
    
    return request, True


def send_otp_to_phone(phone: str, otp: str, step: str = "old") -> Tuple[bool, Optional[str]]:
    """
    Send OTP to phone number via SMS
    Returns (success, error_message)
    
    Note: Currently no SMS service integrated. OTP is generated and stored in Redis.
    The OTP is logged for development/testing purposes.
    
    TODO: Integrate with SMS service (Twilio, AWS SNS, etc.) when available.
    Replace the logging with actual SMS API call:
        sms_service.send(phone, f"Your OTP for phone number change is {otp}. Valid for 3 minutes.")
    """
    try:
        # Log OTP for development/testing (remove in production when SMS is integrated)
        logger.info(f"[OTP GENERATED] {step.upper()} phone number {phone}: OTP = {otp}")
        logger.warning(f"SMS integration not available. OTP for {phone} is: {otp} (for testing only)")
        
        # TODO: Uncomment and configure when SMS service is available
        # from your_sms_service import send_sms
        # send_sms(phone, f"Your OTP for phone number change is {otp}. Valid for 3 minutes.")
        
        # Always return success since OTP is stored in Redis and can be retrieved
        # In production, this should check SMS sending result
        return True, None
    except Exception as e:
        logger.error(f"Error in send_otp_to_phone for {phone}: {e}")
        # Still return True since OTP is stored in Redis
        # In production with SMS, this should return False on failure
        return True, None


def verify_old_number_initiate(
    db: Session,
    user_id: int,
    old_phone: str,
    ip_address: Optional[str] = None
) -> Tuple[Optional[PhoneChangeRequest], Optional[str], Optional[str]]:
    """
    Step 1: Initiate old number verification
    Returns (request, otp, error_message)
    """
    # Get user
    user = get_user_by_id(db, user_id)
    if not user:
        return None, None, "User not found"
    
    # Normalize phone
    old_phone = normalize_phone(old_phone)
    
    # Validate old phone matches user's current phone
    if user.mobile != old_phone:
        return None, None, "Phone number does not match your current number"
    
    # Check rate limit
    allowed, error = check_rate_limit(db, user_id)
    if not allowed:
        return None, None, error
    
    # Check if user is locked/blocked (implement if needed)
    # For now, skip this check
    
    # Get or create request
    request, is_new = get_or_create_request(db, user_id, old_phone, ip_address)
    
    # Ensure request is properly committed and has an ID
    if not request.id:
        db.flush()
        db.refresh(request)
    
    # Generate OTP
    otp = otp_manager.generate_otp(length=OTP_LENGTH)
    
    # Store OTP in Redis (using country code +91 for now, adjust if needed)
    country_code = "+91"
    otp_manager.store_otp(country_code, old_phone, otp, expires_in=OTP_EXPIRY_SECONDS)
    
    # Send OTP via SMS (Note: Currently SMS sending is optional - just logs OTP)
    # When SMS integration is added, uncomment retry logic below
    sms_success, sms_error = send_otp_to_phone(old_phone, otp, "old")
    
    # TODO: Uncomment retry logic when SMS service is integrated
    # sms_success = False
    # sms_error = None
    # for retry in range(3):
    #     success, error = send_otp_to_phone(old_phone, otp, "old")
    #     if success:
    #         sms_success = True
    #         break
    #     sms_error = error
    #     if retry < 2:  # Wait before retry (exponential backoff)
    #         import time
    #         time.sleep(2 ** retry)  # 2s, 4s, 8s
    
    # Currently always succeeds since OTP is logged and stored in Redis
    # When SMS is integrated, uncomment the failure handling below
    # if not sms_success:
    #     request.status = PhoneChangeStatus.FAILED_SMS.value
    #     request.sms_retry_count = 3
    #     db.commit()
    #     create_audit_log(
    #         db, user_id, request.id, "otp_send_failed",
    #         PhoneChangeStatus.FAILED_SMS.value, False, sms_error,
    #         {"old_phone": old_phone}, ip_address
    #     )
    #     return None, "Failed to send OTP. Please try again."
    
    # Update request
    request.sms_retry_count = 0
    request.expires_at = now_ist() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    request.status = PhoneChangeStatus.OLD_NUMBER_PENDING.value  # Ensure status is correct
    request.old_phone_otp_attempts = 0  # Reset attempts for new OTP
    db.commit()
    db.refresh(request)  # Refresh to ensure request is up to date
    
    create_audit_log(
        db, user_id, request.id, "otp_sent_old",
        PhoneChangeStatus.OLD_NUMBER_PENDING.value, True, None,
        {"old_phone": old_phone, "otp_hash": hash_otp(otp)}, ip_address
    )
    
    return request, otp, None


def verify_old_number_confirm(
    db: Session,
    user_id: int,
    request_id: int,
    otp: str,
    ip_address: Optional[str] = None
) -> Tuple[Optional[PhoneChangeRequest], Optional[str], Optional[str]]:
    """
    Step 1 (Part 2): Confirm old number OTP
    Returns (request, session_token, error_message)
    """
    # Try to get request by ID first
    request = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.id == request_id,
        PhoneChangeRequest.user_id == user_id
    ).first()
    
    # If not found by ID, try to find active request for user (fallback)
    if not request:
        request = db.query(PhoneChangeRequest).filter(
            PhoneChangeRequest.user_id == user_id,
            PhoneChangeRequest.status == PhoneChangeStatus.OLD_NUMBER_PENDING.value
        ).order_by(PhoneChangeRequest.created_at.desc()).first()
        
        if not request:
            return None, None, "No active phone change request found. Please start the process again."
        
        # Log that we used fallback lookup (for debugging)
        logger.info(f"Request ID {request_id} not found, using fallback lookup for user {user_id}. Found request ID {request.id}")
    
    # Check status
    if request.status != PhoneChangeStatus.OLD_NUMBER_PENDING.value:
        if request.status == PhoneChangeStatus.OLD_NUMBER_VERIFIED.value:
            # Already verified - return existing session token
            if request.session_token:
                return request, request.session_token, None
            else:
                # Session token missing - generate new one
                session_token = generate_session_token()
                request.session_token = session_token
                request.expires_at = now_ist() + timedelta(seconds=SESSION_TOKEN_EXPIRY_SECONDS)
                db.commit()
                return request, session_token, None
        elif request.status == PhoneChangeStatus.LOCKED.value:
            cooldown_ist = to_ist(request.cooldown_until) if request.cooldown_until else None
            if cooldown_ist and cooldown_ist > now_ist():
                remaining = int((cooldown_ist - now_ist()).total_seconds())
                return None, None, f"Account locked. Please try again in {remaining} seconds."
            else:
                # Cooldown expired, reset
                request.status = PhoneChangeStatus.OLD_NUMBER_PENDING.value
                request.old_phone_otp_attempts = 0
                request.cooldown_until = None
                db.flush()
        elif request.status in [PhoneChangeStatus.FAILED_OLD_OTP.value, PhoneChangeStatus.EXPIRED.value, PhoneChangeStatus.CANCELLED.value]:
            return None, None, f"Request is {request.status}. Please start a new phone change process."
        else:
            return None, None, f"Invalid request status: {request.status}. Please start a new phone change process."
    
    # Check attempts
    if request.old_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
        request.status = PhoneChangeStatus.FAILED_OLD_OTP.value
        request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
        db.commit()
        create_audit_log(
            db, request.user_id, request.id, "otp_max_attempts_reached",
            PhoneChangeStatus.FAILED_OLD_OTP.value, False, "Max OTP attempts reached",
            None, ip_address
        )
        return None, None, f"Maximum {MAX_OTP_ATTEMPTS} attempts exceeded. Please try again in {COOLDOWN_SECONDS // 60} minutes."
    
    # Get OTP from Redis
    country_code = "+91"
    stored_otp = otp_manager.get_otp(country_code, request.old_phone)
    
    if not stored_otp:
        # OTP expired
        request.old_phone_otp_attempts += 1
        if request.old_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
            request.status = PhoneChangeStatus.FAILED_OLD_OTP.value
            request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
        db.commit()
        create_audit_log(
            db, request.user_id, request.id, "otp_verification_failed",
            request.status, False, "OTP expired",
            None, ip_address
        )
        return None, None, "OTP has expired. Please request a new one."
    
    # Verify OTP
    if stored_otp != otp:
        # Wrong OTP
        request.old_phone_otp_attempts += 1
        remaining_attempts = MAX_OTP_ATTEMPTS - request.old_phone_otp_attempts
        
        if request.old_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
            request.status = PhoneChangeStatus.LOCKED.value
            request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
            db.commit()
            create_audit_log(
                db, request.user_id, request.id, "otp_verification_failed",
                PhoneChangeStatus.LOCKED.value, False, "Max attempts reached",
                {"remaining_attempts": 0}, ip_address
            )
            return None, None, f"Maximum {MAX_OTP_ATTEMPTS} attempts exceeded. Please try again in {COOLDOWN_SECONDS // 60} minutes."
        
        db.commit()
        create_audit_log(
            db, request.user_id, request.id, "otp_verification_failed",
            request.status, False, "Invalid OTP",
            {"remaining_attempts": remaining_attempts}, ip_address
        )
        return None, None, f"Invalid OTP. {remaining_attempts} attempts remaining."
    
    # OTP verified successfully
    session_token = generate_session_token()
    
    # Delete OTP from Redis
    otp_manager.delete_otp(country_code, request.old_phone)
    
    # Update request
    request.status = PhoneChangeStatus.OLD_NUMBER_VERIFIED.value
    request.session_token = session_token
    request.old_phone_verified_at = now_ist()
    request.expires_at = now_ist() + timedelta(seconds=SESSION_TOKEN_EXPIRY_SECONDS)
    request.old_phone_otp_attempts = 0
    db.commit()
    
    create_audit_log(
        db, request.user_id, request.id, "old_number_verified",
        PhoneChangeStatus.OLD_NUMBER_VERIFIED.value, True, None,
        {"session_token_generated": True}, ip_address
    )
    
    return request, session_token, None


def verify_new_number_initiate(
    db: Session,
    user_id: int,
    session_token: str,
    new_phone: str,
    ip_address: Optional[str] = None
) -> Tuple[Optional[PhoneChangeRequest], Optional[str], Optional[str]]:
    """
    Step 2: Initiate new number verification
    Returns (request, otp, error_message)
    """
    # Get request by session token
    request = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.user_id == user_id,
        PhoneChangeRequest.session_token == session_token,
        PhoneChangeRequest.status == PhoneChangeStatus.OLD_NUMBER_VERIFIED.value
    ).first()
    
    if not request:
        return None, None, "Invalid or expired session token"
    
    # Check session token expiry
    expires_at_ist = to_ist(request.expires_at) if request.expires_at else None
    if expires_at_ist and expires_at_ist < now_ist():
        request.status = PhoneChangeStatus.EXPIRED.value
        db.commit()
        create_audit_log(
            db, user_id, request.id, "session_expired",
            PhoneChangeStatus.EXPIRED.value, False, "Session token expired",
            None, ip_address
        )
        return None, None, "Session expired. Please start the process again."
    
    # Normalize phone
    new_phone = normalize_phone(new_phone)
    
    # Validate new phone is different from old phone
    if new_phone == request.old_phone:
        return None, None, "New number cannot be the same as current number"
    
    # Check if new phone already exists in users table
    existing_user = db.query(User).filter(User.mobile == new_phone).first()
    if existing_user:
        return None, None, "This phone number is already registered"
    
    # Generate OTP
    otp = otp_manager.generate_otp(length=OTP_LENGTH)
    
    # Store OTP in Redis
    country_code = "+91"
    otp_manager.store_otp(country_code, new_phone, otp, expires_in=OTP_EXPIRY_SECONDS)
    
    # Send OTP via SMS
    # Note: Currently SMS sending is optional (just logs OTP)
    # When SMS integration is added, uncomment retry logic below
    sms_success, sms_error = send_otp_to_phone(new_phone, otp, "new")
    
    # TODO: Uncomment retry logic when SMS service is integrated
    # sms_success = False
    # sms_error = None
    # for retry in range(3):
    #     success, error = send_otp_to_phone(new_phone, otp, "new")
    #     if success:
    #         sms_success = True
    #         break
    #     sms_error = error
    #     if retry < 2:
    #         import time
    #         time.sleep(2 ** retry)
    
    # Currently always succeeds since OTP is logged and stored in Redis
    # When SMS is integrated, uncomment the failure handling below
    # if not sms_success:
    #     request.status = PhoneChangeStatus.FAILED_SMS.value
    #     request.sms_retry_count = 3
    #     db.commit()
    #     create_audit_log(
    #         db, user_id, request.id, "otp_send_failed_new",
    #         PhoneChangeStatus.FAILED_SMS.value, False, sms_error,
    #         {"new_phone": new_phone}, ip_address
    #     )
    #     return None, "Failed to send OTP. Please try again."
    
    # Update request
    request.new_phone = new_phone
    request.status = PhoneChangeStatus.NEW_NUMBER_PENDING.value
    request.sms_retry_count = 0
    request.expires_at = now_ist() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    db.commit()
    
    create_audit_log(
        db, user_id, request.id, "otp_sent_new",
        PhoneChangeStatus.NEW_NUMBER_PENDING.value, True, None,
        {"new_phone": new_phone, "otp_hash": hash_otp(otp)}, ip_address
    )
    
    return request, otp, None


def verify_new_number_confirm(
    db: Session,
    user_id: int,
    session_token: str,
    otp: str,
    ip_address: Optional[str] = None
) -> Tuple[Optional[PhoneChangeRequest], Optional[str]]:
    """
    Step 2 (Part 2): Confirm new number OTP and update database
    Returns (request, error_message)
    """
    # Get request
    request = db.query(PhoneChangeRequest).filter(
        PhoneChangeRequest.user_id == user_id,
        PhoneChangeRequest.session_token == session_token,
        PhoneChangeRequest.status == PhoneChangeStatus.NEW_NUMBER_PENDING.value
    ).first()
    
    if not request:
        return None, "Invalid or expired session token"
    
    if not request.new_phone:
        return None, "New phone number not set"
    
    # Check attempts
    if request.new_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
        request.status = PhoneChangeStatus.FAILED_NEW_OTP.value
        request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
        db.commit()
        create_audit_log(
            db, user_id, request.id, "otp_max_attempts_reached_new",
            PhoneChangeStatus.FAILED_NEW_OTP.value, False, "Max OTP attempts reached",
            None, ip_address
        )
        return None, f"Maximum {MAX_OTP_ATTEMPTS} attempts exceeded. Please try again in {COOLDOWN_SECONDS // 60} minutes."
    
    # Get OTP from Redis
    country_code = "+91"
    stored_otp = otp_manager.get_otp(country_code, request.new_phone)
    
    if not stored_otp:
        # OTP expired
        request.new_phone_otp_attempts += 1
        if request.new_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
            request.status = PhoneChangeStatus.FAILED_NEW_OTP.value
            request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
        db.commit()
        create_audit_log(
            db, user_id, request.id, "otp_verification_failed_new",
            request.status, False, "OTP expired",
            None, ip_address
        )
        return None, "OTP has expired. Please request a new one."
    
    # Verify OTP
    if stored_otp != otp:
        # Wrong OTP
        request.new_phone_otp_attempts += 1
        remaining_attempts = MAX_OTP_ATTEMPTS - request.new_phone_otp_attempts
        
        if request.new_phone_otp_attempts >= MAX_OTP_ATTEMPTS:
            request.status = PhoneChangeStatus.LOCKED.value
            request.cooldown_until = now_ist() + timedelta(seconds=COOLDOWN_SECONDS)
            db.commit()
            create_audit_log(
                db, user_id, request.id, "otp_verification_failed_new",
                PhoneChangeStatus.LOCKED.value, False, "Max attempts reached",
                {"remaining_attempts": 0}, ip_address
            )
            return None, f"Maximum {MAX_OTP_ATTEMPTS} attempts exceeded. Please try again in {COOLDOWN_SECONDS // 60} minutes."
        
        db.commit()
        create_audit_log(
            db, user_id, request.id, "otp_verification_failed_new",
            request.status, False, "Invalid OTP",
            {"remaining_attempts": remaining_attempts}, ip_address
        )
        return None, f"Invalid OTP. {remaining_attempts} attempts remaining."
    
    # OTP verified successfully - Update database
    try:
        # Delete OTP from Redis
        otp_manager.delete_otp(country_code, request.new_phone)
        
        # Begin transaction
        # Update users.mobile
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return None, "User not found"
        
        # Double-check new phone doesn't exist (race condition)
        existing_user = db.query(User).filter(User.mobile == request.new_phone).first()
        if existing_user:
            return None, "This phone number is already registered"
        
        # Update users.mobile
        user.mobile = request.new_phone
        
        # Update members.mobile where is_self_profile = True
        db.query(Member).filter(
            Member.user_id == user_id,
            Member.is_self_profile == True
        ).update({Member.mobile: request.new_phone})
        
        # Update request
        request.status = PhoneChangeStatus.COMPLETED.value
        request.new_phone_verified_at = now_ist()
        request.completed_at = now_ist()
        request.session_token = None  # Invalidate session token
        
        # Commit transaction
        db.commit()
        
        create_audit_log(
            db, user_id, request.id, "phone_change_completed",
            PhoneChangeStatus.COMPLETED.value, True, None,
            {"old_phone": request.old_phone, "new_phone": request.new_phone}, ip_address
        )
        
        # TODO: Send notification to old number
        
        return request, None
        
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error during phone change: {e}")
        request.status = PhoneChangeStatus.FAILED_DB_UPDATE.value
        db.commit()
        create_audit_log(
            db, user_id, request.id, "db_update_failed",
            PhoneChangeStatus.FAILED_DB_UPDATE.value, False, str(e),
            None, ip_address
        )
        return None, "Failed to update phone number. Please try again."
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during phone change: {e}", exc_info=True)
        request.status = PhoneChangeStatus.FAILED_DB_UPDATE.value
        db.commit()
        create_audit_log(
            db, user_id, request.id, "db_update_failed",
            PhoneChangeStatus.FAILED_DB_UPDATE.value, False, str(e),
            None, ip_address
        )
        return None, "An error occurred. Please try again."


def cancel_phone_change(
    db: Session,
    user_id: int,
    session_token: Optional[str] = None,
    request_id: Optional[int] = None,
    ip_address: Optional[str] = None
) -> Tuple[Optional[PhoneChangeRequest], Optional[str]]:
    """Cancel phone change process"""
    if session_token:
        request = db.query(PhoneChangeRequest).filter(
            PhoneChangeRequest.user_id == user_id,
            PhoneChangeRequest.session_token == session_token
        ).first()
    elif request_id:
        request = db.query(PhoneChangeRequest).filter(
            PhoneChangeRequest.id == request_id,
            PhoneChangeRequest.user_id == user_id
        ).first()
    else:
        return None, "Either session_token or request_id must be provided"
    
    if not request:
        return None, "Request not found"
    
    # Only cancel if not already completed/cancelled/expired
    if request.status not in [
        PhoneChangeStatus.COMPLETED.value,
        PhoneChangeStatus.CANCELLED.value,
        PhoneChangeStatus.EXPIRED.value
    ]:
        request.status = PhoneChangeStatus.CANCELLED.value
        db.commit()
        
        create_audit_log(
            db, user_id, request.id, "request_cancelled",
            PhoneChangeStatus.CANCELLED.value, True, None,
            None, ip_address
        )
    
    return request, None

