from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from .OTP_schema import (
    SendOTPRequest,
    SendOTPResponse,
    OTPData,
    VerifyOTPRequest,
    VerifyOTPResponse,
    VerifiedData
)
from deps import get_db
from Utils import Security
from OTP import otp_manager
from User.user_session_crud import get_user_by_mobile, create_user
from Device.Device_session_crud import create_device_session
from OTP import OTP_crud

from dotenv import load_dotenv
import os

load_dotenv()

OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 300))
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 86400))

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/send-otp", response_model=SendOTPResponse)
def send_otp(request: SendOTPRequest, db: Session = Depends(get_db)):
    """
    Send OTP to the provided mobile number.
    Rate limited to prevent abuse.
    """
    if not otp_manager.can_request_otp(request.country_code, request.mobile):
        remaining = otp_manager.get_remaining_requests(request.country_code, request.mobile)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"OTP request limit reached. Remaining: {remaining}"
        )

    # Generate OTP
    otp = otp_manager.generate_otp()
    otp_manager.store_otp(request.country_code, request.mobile, otp, expires_in=OTP_EXPIRY_SECONDS)

    # Store hashed version in DB audit log
    otp_log.create_sent_log(
        db=db,
        phone_number=f"{request.country_code}{request.mobile}",
        otp_hash=security.hash_value(otp)
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
    """
    phone_number = f"{req.country_code}{req.mobile}"

    # Fetch OTP from Redis (plaintext)
    stored = otp_manager.get_otp(req.country_code, req.mobile)
    if not stored:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found"
        )

    # Compare plaintext (fast check)
    if stored != req.otp:
        otp_log.mark_failed(
            db=db,
            phone_number=phone_number,
            user_entered_otp_hash=security.hash_value(req.otp)
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid OTP"
        )

    # Retrieve last sent OTP log and mark as verified
    last_sent = (
        db.query(otp_log.OTPLog)
        .filter(
            otp_log.OTPLog.phone_number == phone_number,
            otp_log.OTPLog.status == "sent"
        )
        .order_by(otp_log.OTPLog.generated_at.desc())
        .first()
    )

    if last_sent:
        otp_log.mark_verified(
            db=db,
            log_id=last_sent.id,
            user_entered_otp_hash=security.hash_value(req.otp)
        )

    # Remove OTP from Redis
    otp_manager.delete_otp(req.country_code, req.mobile)

    # Get or create user
    user = get_user_by_mobile(db, req.mobile)
    if not user:
        user = create_user(db, mobile=req.mobile)

    # Device & session
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    session = create_device_session(
        db=db,
        user_id=user.id,
        device_id=req.device_id,
        device_platform=req.device_platform or "unknown",
        device_details=req.device_details,
        ip=ip,
        user_agent=user_agent,
        expires_in_seconds=ACCESS_TOKEN_EXPIRE_SECONDS
    )

    token = security.create_access_token({
        "sub": str(user.id),
        "session_id": str(session.id),
        "device_platform": session.device_platform
    }, expires_delta=ACCESS_TOKEN_EXPIRE_SECONDS)

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