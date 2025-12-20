from fastapi import APIRouter, Depends, HTTPException, status, Request, UploadFile, File
from sqlalchemy.orm import Session
import uuid
import os
from pathlib import Path
from typing import Optional

from .Profile_schema import (
    EditProfileRequest,
    EditProfileResponse,
    UserProfileData,
    GetProfileResponse,
    UploadPhotoResponse
)
from Login_module.Utils.auth_user import get_current_user
from Login_module.User import user_session_crud
from deps import get_db
from .Profile_audit_crud import log_profile_update

router = APIRouter(prefix="/profile", tags=["profile"])

# Directory for storing uploaded profile photos
UPLOAD_DIR = Path("uploads/profile_photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


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
        mobile=current_user.mobile,
        profile_photo_url=current_user.profile_photo_url
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
        "mobile": current_user.mobile,
        "profile_photo_url": current_user.profile_photo_url
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

    # UPDATE USER (profile_photo_url is not updated here - use upload-photo endpoint)
    updated_user = user_session_crud.update_user_profile(
        db=db,
        user_id=current_user.id,
        name=req.name,
        email=req.email,
        mobile=req.mobile,
        profile_photo_url=None  # Don't update photo URL via edit endpoint
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
        "mobile": updated_user.mobile,
        "profile_photo_url": updated_user.profile_photo_url
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
        mobile=updated_user.mobile,
        profile_photo_url=updated_user.profile_photo_url
    )

    return EditProfileResponse(
        status="success",
        message="Profile updated successfully.",
        data=data
    )


@router.post("/upload-photo", response_model=UploadPhotoResponse)
async def upload_profile_photo(
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    """
    Upload profile photo for the current user.
    Accepts image files (jpg, jpeg, png, gif, webp) up to 5MB.
    """
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Read file content to check size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {MAX_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    # Generate unique filename: user_id_timestamp.ext
    timestamp = int(uuid.uuid4().hex[:8], 16)  # Use part of UUID as timestamp-like identifier
    filename = f"{current_user.id}_{timestamp}{file_ext}"
    file_path = UPLOAD_DIR / filename
    
    # Delete old profile photo if exists
    if current_user.profile_photo_url:
        old_file_path = UPLOAD_DIR / Path(current_user.profile_photo_url).name
        if old_file_path.exists():
            try:
                old_file_path.unlink()
            except Exception as e:
                # Log but don't fail if old file deletion fails
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to delete old profile photo: {str(e)}")
    
    # Save new file
    try:
        with open(file_path, "wb") as buffer:
            buffer.write(file_content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Store relative path in database (relative to uploads directory or absolute URL in production)
    profile_photo_url = f"profile_photos/{filename}"
    
    # Store old data for audit
    old_data = {
        "profile_photo_url": current_user.profile_photo_url
    }
    
    # Update user profile with photo URL
    updated_user = user_session_crud.update_user_profile(
        db=db,
        user_id=current_user.id,
        name=None,  # Don't change other fields
        email=None,
        mobile=None,
        profile_photo_url=profile_photo_url
    )
    
    if not updated_user:
        # Delete uploaded file if update failed
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to update profile photo"
        )
    
    # Store new data for audit
    new_data = {
        "profile_photo_url": updated_user.profile_photo_url
    }
    
    # Audit log
    ip_address = request.client.host if request else None
    user_agent = request.headers.get("user-agent") if request else None
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
        mobile=updated_user.mobile,
        profile_photo_url=updated_user.profile_photo_url
    )
    
    return UploadPhotoResponse(
        status="success",
        message="Profile photo uploaded successfully.",
        data=data
    )
