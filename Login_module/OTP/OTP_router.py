from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
import logging
import uuid
from .OTP_schema import (
    SendOTPRequest,
    SendOTPResponse,
    OTPData,
    VerifyOTPRequest,
    VerifyOTPResponse,
    VerifiedData
)
from deps import get_db
from ..Utils import security
from ..Utils.auth_user import get_current_user
from ..Utils.rate_limiter import check_ip_rate_limit, get_client_ip
from . import otp_manager
from ..User.user_session_crud import get_user_by_mobile, create_user
from ..Device.Device_session_crud import create_device_session, deactivate_session_by_token
from . import OTP_crud

from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 120))  # 2 minutes
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 86400))  # 1 day
MAX_ACTIVE_SESSIONS = int(os.getenv("MAX_ACTIVE_SESSIONS", 4))  # Max 4 active sessions per user

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp", response_model=SendOTPResponse)
def send_otp(request: SendOTPRequest, http_request: Request, db: Session = Depends(get_db)):
    """
    Send OTP to the provided mobile number.
    Rate limited to prevent abuse (max 15 per hour).
    """
    phone_number = f"{request.country_code}{request.mobile}"
    correlation_id = str(uuid.uuid4())
    client_ip = get_client_ip(http_request)
    user_agent = http_request.headers.get("user-agent")
    
    # Check if user is blocked
    if otp_manager.is_user_blocked(request.country_code, request.mobile):
        remaining_time = otp_manager.get_block_remaining_time(request.country_code, request.mobile)
        OTP_crud.create_otp_audit_log(
            db=db,
            event_type="BLOCKED",
            phone_number=phone_number,
            reason=f"Attempted OTP generation while blocked. Remaining block time: {remaining_time}s",
            ip_address=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account temporarily blocked due to too many failed attempts. Try again in {remaining_time // 60} minutes."
        )
    
    if not otp_manager.can_request_otp(request.country_code, request.mobile):
        remaining = otp_manager.get_remaining_requests(request.country_code, request.mobile)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"OTP request limit reached. Remaining: {remaining}"
        )

    # Generate OTP
    otp = otp_manager.generate_otp()
    otp_manager.store_otp(request.country_code, request.mobile, otp, expires_in=OTP_EXPIRY_SECONDS)

    # Create audit log (no OTP values stored)
    OTP_crud.create_otp_audit_log(
        db=db,
        event_type="GENERATED",
        phone_number=phone_number,
        reason="OTP generated and sent",
        ip_address=client_ip,
        user_agent=user_agent,
        correlation_id=correlation_id
    )

    message = f"OTP sent successfully to {request.mobile}."

    data = OTPData(
        mobile=request.mobile,
        otp=otp,
        expires_in=OTP_EXPIRY_SECONDS,
        purpose=request.purpose
    )
    return SendOTPResponse(status="success", message=message, data=data)


@router.post("/verify-otp", response_model=VerifyOTPResponse)
def verify_otp(req: VerifyOTPRequest, request: Request, db: Session = Depends(get_db)):
    """
    Verify OTP and create user session.
    Returns access token on successful verification.
    Blocks user after 5-6 wrong attempts for 10 minutes.
    Includes IP-based rate limiting to prevent brute force attacks.
    """
    phone_number = f"{req.country_code}{req.mobile}"
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    # IP-based rate limiting (prevents brute force from same IP)
    is_allowed, remaining = check_ip_rate_limit(client_ip)
    if not is_allowed:
        logger.warning(f"IP rate limit exceeded for IP: {client_ip}, phone: {phone_number}")
        OTP_crud.create_otp_audit_log(
            db=db,
            event_type="BLOCKED",
            phone_number=phone_number,
            device_id=req.device_id,
            reason=f"IP rate limit exceeded. IP: {client_ip}",
            ip_address=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts from this IP. Please try again later."
        )

    # Check if user is blocked
    if otp_manager.is_user_blocked(req.country_code, req.mobile):
        remaining_time = otp_manager.get_block_remaining_time(req.country_code, req.mobile)
        OTP_crud.create_otp_audit_log(
            db=db,
            event_type="BLOCKED",
            phone_number=phone_number,
            device_id=req.device_id,
            reason=f"Attempted OTP verification while blocked. Remaining block time: {remaining_time}s"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Account temporarily blocked due to too many failed attempts. Try again in {remaining_time // 60} minutes."
        )

    # Fetch OTP from Redis (plaintext)
    stored = otp_manager.get_otp(req.country_code, req.mobile)
    if not stored:
        OTP_crud.create_otp_audit_log(
            db=db,
            event_type="FAILED",
            phone_number=phone_number,
            device_id=req.device_id,
            reason="OTP expired or not found",
            ip_address=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found"
        )

    # Compare plaintext (fast check)
    if stored != req.otp:
        # Record failed attempt
        failed_count = otp_manager.record_failed_attempt(req.country_code, req.mobile)
        
        # Check if user got blocked
        is_blocked = otp_manager.is_user_blocked(req.country_code, req.mobile)
        
        logger.warning(f"Invalid OTP attempt for {phone_number} from IP {client_ip}. Failed count: {failed_count}")
        
        OTP_crud.create_otp_audit_log(
            db=db,
            event_type="BLOCKED" if is_blocked else "FAILED",
            phone_number=phone_number,
            device_id=req.device_id,
            reason=f"Invalid OTP. Failed attempt count: {failed_count}. IP: {client_ip}",
            ip_address=client_ip,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        
        if is_blocked:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Too many failed attempts. Account blocked for 10 minutes."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid OTP. {5 - failed_count} attempts remaining before block."
            )

    # OTP verified successfully
    try:
        # Reset failed attempts
        otp_manager.reset_failed_attempts(req.country_code, req.mobile)
        
        # Remove OTP from Redis
        otp_manager.delete_otp(req.country_code, req.mobile)

        # Get or create user
        try:
            user = get_user_by_mobile(db, req.mobile)
            if not user:
                user = create_user(db, mobile=req.mobile)
        except Exception as e:
            db.rollback()
            logger.error(f"Error getting/creating user: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: Unable to get or create user. {str(e)}"
            )

        # Create audit log for successful verification
        try:
            OTP_crud.create_otp_audit_log(
                db=db,
                event_type="VERIFIED",
                user_id=user.id,
                device_id=req.device_id,
                phone_number=phone_number,
                reason=f"OTP verified successfully. IP: {client_ip}",
                ip_address=client_ip,
                user_agent=user_agent,
                correlation_id=correlation_id
            )
        except Exception as e:
            logger.warning(f"Failed to create audit log: {e}")

        # Device & session
        ip = client_ip
        user_agent = request.headers.get("user-agent")

        try:
            session = create_device_session(
                db=db,
                user_id=user.id,
                device_id=req.device_id,
                device_platform=req.device_platform or "unknown",
                device_details=req.device_details,
                ip=ip,
                user_agent=user_agent,
                expires_in_seconds=ACCESS_TOKEN_EXPIRE_SECONDS,
                max_active_sessions=MAX_ACTIVE_SESSIONS,
                correlation_id=correlation_id
            )
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating device session: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database error: Unable to create session. {str(e)}"
            )

        try:
            token = security.create_access_token({
                "sub": str(user.id),
                "session_id": str(session.id),
                "device_platform": session.device_platform
            }, expires_delta=ACCESS_TOKEN_EXPIRE_SECONDS)
        except Exception as e:
            db.rollback()
            logger.error(f"Error creating access token: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error generating access token. {str(e)}"
            )

        logger.info(f"OTP verified successfully for user {user.id} from IP {client_ip}")

        data = VerifiedData(
            user_id=user.id,
            name=user.name,
            mobile=user.mobile,
            email=user.email,
            access_token=token,
            token_type="Bearer",
            expires_in=ACCESS_TOKEN_EXPIRE_SECONDS
        )

        return VerifyOTPResponse(
            status="success",
            message="OTP verified successfully.",
            data=data
        )
    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Unexpected error during OTP verification: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during verification: {str(e)}"
        )


class LogoutResponse(BaseModel):
    status: str = "success"
    message: str


@router.post("/logout", response_model=LogoutResponse)
def logout(
    request: Request,
    current_user = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Logout from current device/session.
    Only deletes the current session; other sessions remain active.
    """
    # Extract token from Authorization header
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header"
        )
    
    token = auth_header.split(" ")[1]
    
    # Decode token to get session_id
    try:
        payload = security.decode_access_token(token)
        session_id = payload.get("session_id")
        if not session_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Token does not contain session info"
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {str(e)}"
        )
    
    # Deactivate session
    from ..Device.Device_session_crud import deactivate_session
    from ..Utils.rate_limiter import get_client_ip
    
    ip_address = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    try:
        deactivated = deactivate_session(
            db=db,
            session_id=int(session_id),
            reason="User logout",
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid session ID format"
        )
    
    if not deactivated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found or already inactive"
        )
    
    return LogoutResponse(
        status="success",
        message="Logged out successfully from this device."
    )