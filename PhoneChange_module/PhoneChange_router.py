"""
Phone Change Router - API endpoints for phone number change
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import Optional
import logging

from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User
from Login_module.Utils.rate_limiter import get_client_ip
from .PhoneChange_schema import (
    VerifyOldNumberRequest,
    VerifyOldNumberResponse,
    ConfirmOldNumberRequest,
    ConfirmOldNumberResponse,
    VerifyNewNumberRequest,
    VerifyNewNumberResponse,
    ConfirmNewNumberRequest,
    ConfirmNewNumberResponse,
    CancelPhoneChangeRequest,
    CancelPhoneChangeResponse
)
from . import PhoneChange_crud
from Login_module.OTP import otp_manager

router = APIRouter(prefix="/api/phone-change", tags=["Phone Change"])

logger = logging.getLogger(__name__)

# Constants
OTP_EXPIRY_SECONDS = 180  # 3 minutes
SESSION_TOKEN_EXPIRY_SECONDS = 600  # 10 minutes
MAX_OTP_ATTEMPTS = 3


@router.post("/verify-old-number", response_model=VerifyOldNumberResponse)
def verify_old_number(
    request: VerifyOldNumberRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1: Send OTP to current/old phone number
    Validates that the provided phone number matches the user's current phone number
    """
    ip_address = get_client_ip(http_request)
    
    # Verify old number and send OTP
    phone_change_request, otp, error = PhoneChange_crud.verify_old_number_initiate(
        db=db,
        user_id=current_user.id,
        old_phone=request.old_phone,
        ip_address=ip_address
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Calculate remaining attempts
    remaining_attempts = MAX_OTP_ATTEMPTS - phone_change_request.old_phone_otp_attempts
    
    return VerifyOldNumberResponse(
        status="success",
        message="OTP sent successfully to your current phone number",
        request_id=phone_change_request.id,
        otp=otp,  # Include OTP in response for development/testing
        otp_expires_in=OTP_EXPIRY_SECONDS,
        remaining_attempts=remaining_attempts
    )


@router.post("/confirm-old-number", response_model=ConfirmOldNumberResponse)
def confirm_old_number(
    request: ConfirmOldNumberRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 1 (Part 2): Verify OTP for old/current phone number
    Returns session token for Step 2
    """
    ip_address = get_client_ip(http_request)
    
    # Verify OTP and generate session token
    phone_change_request, session_token, error = PhoneChange_crud.verify_old_number_confirm(
        db=db,
        user_id=current_user.id,
        request_id=request.request_id,
        otp=request.otp,
        ip_address=ip_address
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate session token"
        )
    
    return ConfirmOldNumberResponse(
        status="success",
        message="Old phone number verified successfully",
        session_token=session_token,
        session_expires_in=SESSION_TOKEN_EXPIRY_SECONDS
    )


@router.post("/verify-new-number", response_model=VerifyNewNumberResponse)
def verify_new_number(
    request: VerifyNewNumberRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2: Send OTP to new phone number
    Validates that new number is different from old number and not already registered
    """
    ip_address = get_client_ip(http_request)
    
    # Verify new number and send OTP
    phone_change_request, otp, error = PhoneChange_crud.verify_new_number_initiate(
        db=db,
        user_id=current_user.id,
        session_token=request.session_token,
        new_phone=request.new_phone,
        ip_address=ip_address
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    # Calculate remaining attempts
    remaining_attempts = MAX_OTP_ATTEMPTS - phone_change_request.new_phone_otp_attempts
    
    return VerifyNewNumberResponse(
        status="success",
        message="OTP sent successfully to your new phone number",
        request_id=phone_change_request.id,
        otp=otp,  # Include OTP in response for development/testing
        otp_expires_in=OTP_EXPIRY_SECONDS,
        remaining_attempts=remaining_attempts
    )


@router.post("/confirm-new-number", response_model=ConfirmNewNumberResponse)
def confirm_new_number(
    request: ConfirmNewNumberRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Step 2 (Part 2): Verify OTP for new phone number and update database
    Updates users.mobile and members.mobile (self profile) in a transaction
    """
    ip_address = get_client_ip(http_request)
    
    # Verify OTP and update database
    phone_change_request, error = PhoneChange_crud.verify_new_number_confirm(
        db=db,
        user_id=current_user.id,
        session_token=request.session_token,
        otp=request.otp,
        ip_address=ip_address
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    if not phone_change_request or not phone_change_request.new_phone:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to complete phone number change"
        )
    
    return ConfirmNewNumberResponse(
        status="success",
        message="Phone number changed successfully",
        new_phone=phone_change_request.new_phone
    )


@router.post("/cancel", response_model=CancelPhoneChangeResponse)
def cancel_phone_change(
    request: CancelPhoneChangeRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Cancel the phone change process
    Can cancel using either session_token or request_id
    """
    ip_address = get_client_ip(http_request)
    
    # Cancel phone change request
    phone_change_request, error = PhoneChange_crud.cancel_phone_change(
        db=db,
        user_id=current_user.id,
        session_token=request.session_token,
        request_id=request.request_id,
        ip_address=ip_address
    )
    
    if error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error
        )
    
    return CancelPhoneChangeResponse(
        status="success",
        message="Phone change process cancelled successfully"
    )

