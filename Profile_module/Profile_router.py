from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
import uuid

from .Profile_schema import (
    EditProfileRequest,
    EditProfileResponse,
    UserProfileData,
    GetProfileResponse
)
from Login_module.Utils.auth_user import get_current_user
from Login_module.User import user_session_crud
from deps import get_db
from .Profile_audit_crud import log_profile_update

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=GetProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Get current user's profile information.
    """
    data = UserProfileData(
        user_id=current_user.id,
        name=current_user.name,
        email=current_user.email,
        mobile=current_user.mobile
    )

    return GetProfileResponse(
        status="success",
        message="Profile retrieved successfully.",
        data=data
    )


@router.put("/edit", response_model=EditProfileResponse)
def edit_profile(
    req: EditProfileRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    # Must provide at least one field
    if not any([req.name, req.email, req.mobile]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (name, email, or mobile) must be provided"
        )

    # Store old data for audit
    old_data = {
        "name": current_user.name,
        "email": current_user.email,
        "mobile": current_user.mobile
    }

    # --- EMAIL DUPLICATE CHECK ---
    if req.email and req.email != current_user.email:
        existing_email_user = user_session_crud.get_user_by_email(db, req.email)
        if existing_email_user and existing_email_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

    # --- MOBILE DUPLICATE CHECK ---
    if req.mobile and req.mobile != current_user.mobile:
        existing_mobile_user = user_session_crud.get_user_by_mobile(db, req.mobile)
        if existing_mobile_user and existing_mobile_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already exists"
            )

    # UPDATE USER
    updated_user = user_session_crud.update_user_profile(
        db=db,
        user_id=current_user.id,
        name=req.name,
        email=req.email,
        mobile=req.mobile
    )

    if not updated_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update user profile"
        )

    # Store new data for audit
    new_data = {
        "name": updated_user.name,
        "email": updated_user.email,
        "mobile": updated_user.mobile
    }

    # Audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    log_profile_update(
        db=db,
        user_id=current_user.id,
        old_data=old_data,
        new_data=new_data,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )

    data = UserProfileData(
        user_id=updated_user.id,
        name=updated_user.name,
        email=updated_user.email,
        mobile=updated_user.mobile
    )

    return EditProfileResponse(
        status="success",
        message="Profile updated successfully.",
        data=data
    )
