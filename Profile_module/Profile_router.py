from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from Profile_schema import (
    EditProfileRequest,
    EditProfileResponse,
    UserProfileData,
    GetProfileResponse
)
from Login_module.Utils.auth_user import get_current_user
from Login_module.User import user_session_crud
from deps import get_db

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
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Edit current user's profile information.
    At least one field (name, email, or mobile) must be provided.
    """
    # Check if at least one field is provided
    if not any([req.name, req.email, req.mobile]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (name, email, or mobile) must be provided"
        )

    # If mobile is being updated, check if it already exists for another user
    if req.mobile and req.mobile != current_user.mobile:
        existing_user = auth.get_user_by_mobile(db, req.mobile)
        if existing_user and existing_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mobile number already registered with another account"
            )

    updated_user = auth.update_user_profile(
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