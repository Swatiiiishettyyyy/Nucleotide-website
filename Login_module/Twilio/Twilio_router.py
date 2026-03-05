"""
Twilio Verify API integration - separate from custom OTP (send-otp/verify-otp).
Uses Twilio Verify v2 for SMS verification.
Twilio verify returns access_token and refresh_token same as verify-otp (web cookies or mobile JSON).
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from sqlalchemy.orm import Session
from typing import Optional
import re
import logging
import uuid

from config import settings
from deps import get_db
from Login_module.Utils.phone_validation import validate_indian_mobile
from Login_module.Utils import security
from Login_module.Utils.rate_limiter import get_client_ip
from Login_module.User.user_session_crud import get_user_by_mobile, create_user
from Login_module.Device.Device_session_crud import create_device_session
from Login_module.OTP.OTP_schema import VerifiedData, VerifyOTPResponse
from Login_module.Token.Refresh_token_crud import create_refresh_token
from Login_module.Utils.datetime_utils import now_ist
from datetime import timedelta
from Notification_module.Notification_crud import upsert_device_token

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth/twilio", tags=["auth", "twilio"])

OTP_EXPIRY_SECONDS = settings.OTP_EXPIRY_SECONDS
ACCESS_TOKEN_EXPIRE_SECONDS = settings.ACCESS_TOKEN_EXPIRE_SECONDS
MAX_ACTIVE_SESSIONS = settings.MAX_ACTIVE_SESSIONS


# Request/Response schemas
class TwilioSendVerificationRequest(BaseModel):
    country_code: str = Field(..., example="+91", min_length=1, max_length=5)
    mobile: str = Field(..., example="9876543210", min_length=10, max_length=15)
    channel: str = Field(default="sms", example="sms", description="sms or call")

    @validator("country_code")
    def validate_country_code(cls, v):
        if not re.match(r"^\+?\d{1,4}$", v):
            raise ValueError("Invalid country code format")
        return v if v.startswith("+") else f"+{v}"

    @validator("mobile")
    def validate_mobile(cls, v):
        return validate_indian_mobile(v)

    @validator("channel")
    def validate_channel(cls, v):
        if v not in ("sms", "call"):
            raise ValueError("Channel must be 'sms' or 'call'")
        return v


class TwilioSendVerificationResponse(BaseModel):
    status: str = "success"
    message: str
    verification_sid: str


class TwilioVerifyRequest(BaseModel):
    country_code: str = Field(..., example="+91", min_length=1, max_length=5)
    mobile: str = Field(..., example="9876543210", min_length=10, max_length=15)
    code: str = Field(..., example="123456", min_length=4, max_length=8)

    @validator("country_code")
    def validate_country_code(cls, v):
        if not re.match(r"^\+?\d{1,4}$", v):
            raise ValueError("Invalid country code format")
        return v if v.startswith("+") else f"+{v}"

    @validator("mobile")
    def validate_mobile(cls, v):
        return validate_indian_mobile(v)

    @validator("code")
    def validate_code(cls, v):
        if not re.match(r"^\d{4,8}$", v):
            raise ValueError("Code must be 4-8 digits")
        return v


class TwilioVerifyResponse(BaseModel):
    status: str = "success"
    message: str
    verification_status: str


def _get_twilio_client():
    """Get Twilio client; raises if config is missing."""
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio is not configured. Set TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN.",
        )
    if not settings.TWILIO_VERIFY_SERVICE_SID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio Verify service is not configured. Set TWILIO_VERIFY_SERVICE_SID.",
        )
    try:
        from twilio.rest import Client
        return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    except ImportError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Twilio package not installed. Run: pip install twilio",
        )


@router.post("/send-verification", response_model=TwilioSendVerificationResponse)
def twilio_send_verification(req: TwilioSendVerificationRequest):
    """
    Send verification code via Twilio Verify API (SMS or call).
    Separate from /auth/send-otp which uses custom OTP flow.
    """
    client = _get_twilio_client()
    phone_number = f"{req.country_code}{req.mobile}"

    try:
        verification = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verifications.create(to=phone_number, channel=req.channel)
        )
        logger.info(f"Twilio verification sent to {phone_number}, sid={verification.sid}")
        return TwilioSendVerificationResponse(
            status="success",
            message="Verification code sent successfully.",
            verification_sid=verification.sid,
        )
    except Exception as e:
        logger.error(f"Twilio send verification failed for {phone_number}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to send verification: {str(e)}",
        )


@router.post("/verify", response_model=TwilioVerifyResponse)
def twilio_verify(req: TwilioVerifyRequest):
    """
    Verify code via Twilio Verify API.
    Separate from /auth/verify-otp which uses custom OTP flow and creates session.
    """
    client = _get_twilio_client()
    phone_number = f"{req.country_code}{req.mobile}"

    try:
        verification_check = (
            client.verify.v2.services(settings.TWILIO_VERIFY_SERVICE_SID)
            .verification_checks.create(to=phone_number, code=req.code)
        )
        if verification_check.status == "approved":
            logger.info(f"Twilio verification approved for {phone_number}")
            return TwilioVerifyResponse(
                status="success",
                message="Verification successful.",
                verification_status=verification_check.status,
            )
        else:
            logger.warning(f"Twilio verification failed for {phone_number}: status={verification_check.status}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code.",
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Twilio verify failed for {phone_number}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Verification check failed: {str(e)}",
        )
