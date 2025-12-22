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
    UploadPhotoResponse,
    DeletePhotoResponse
)
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.User import user_session_crud
from deps import get_db
from .Profile_audit_crud import log_profile_update
from Member_module.Member_model import Member
from Member_module.Member_s3_service import get_member_photo_s3_service

router = APIRouter(prefix="/profile", tags=["profile"])

# Directory for storing uploaded profile photos
UPLOAD_DIR = Path("uploads/profile_photos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Content type mapping for member photos
CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp"
}


@router.get("/me", response_model=GetProfileResponse)
def get_profile(
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    current_member=Depends(get_current_member)
):
    """
    Get current member's profile information.
    Returns the currently selected member profile, or default member if none selected.
    Falls back to user profile if no members exist.
    """
    # If no member selected in token, fall back to default member (first/self member)
    if not current_member:
        # Try to get self profile member first
        default_member = db.query(Member).filter(
            Member.user_id == current_user.id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        # If no self profile, get the first member (oldest by created_at)
        if not default_member:
            default_member = db.query(Member).filter(
                Member.user_id == current_user.id,
                Member.is_deleted == False
            ).order_by(Member.created_at.asc()).first()
        
        # If still no member found, fall back to user profile
        if not default_member:
            data = UserProfileData(
                user_id=current_user.id,
                name=current_user.name,
                email=current_user.email,
                mobile=current_user.mobile,
                profile_photo_url=current_user.profile_photo_url,
                has_taken_genetic_test=False  # No member, so no genetic test
            )
            return GetProfileResponse(
                status="success",
                message="Profile retrieved successfully (user profile - no members found).",
                data=data
            )
        
        # Use default member
        current_member = default_member
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=current_member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    # Return current member's profile details
    data = UserProfileData(
        user_id=current_user.id,  # Keep user_id for reference
        name=current_member.name,
        email=current_user.email,  # Email is user-level, not member-level
        mobile=current_member.mobile,
        profile_photo_url=current_member.profile_photo_url,
        has_taken_genetic_test=has_taken_genetic_test
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
    current_user=Depends(get_current_user),
    current_member=Depends(get_current_member)
):
    """
    Edit current member's profile.
    Updates member name and mobile. Email is updated at user level.
    """
    # Get current member (similar to /profile/me logic)
    if not current_member:
        # Try to get self profile member first
        default_member = db.query(Member).filter(
            Member.user_id == current_user.id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        # If no self profile, get the first member (oldest by created_at)
        if not default_member:
            default_member = db.query(Member).filter(
                Member.user_id == current_user.id,
                Member.is_deleted == False
            ).order_by(Member.created_at.asc()).first()
        
        if not default_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No member found. Please create a member profile first."
            )
        
        current_member = default_member
    
    # Must provide at least one field
    if not any([req.name, req.email, req.mobile]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least one field (name, email, or mobile) must be provided"
        )

    # Store old data for audit (member and user data)
    old_data = {
        "member_name": current_member.name,
        "member_mobile": current_member.mobile,
        "user_email": current_user.email,
        "profile_photo_url": current_member.profile_photo_url
    }

    # Update email at user level if provided
    updated_user = current_user
    if req.email and req.email != current_user.email:
        # EMAIL DUPLICATE CHECK
        existing_email_user = user_session_crud.get_user_by_email(db, req.email)
        if existing_email_user and existing_email_user.id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )
        
        # Update user email
        updated_user = user_session_crud.update_user_profile(
            db=db,
            user_id=current_user.id,
            name=None,
            email=req.email,
            mobile=None,
            profile_photo_url=None
        )
        
        if not updated_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to update user email"
            )

    # Update member name and mobile if provided
    if req.name or req.mobile:
        # MOBILE DUPLICATE CHECK (check at member level if mobile is being changed)
        # Note: Mobile is member-level, so we only check if it's different
        # Multiple members can have the same mobile (e.g., family members sharing a phone)
        # But we'll check if another member already has this mobile for validation
        
        # Update member fields
        if req.name:
            current_member.name = req.name
        if req.mobile:
            current_member.mobile = req.mobile
        
        db.commit()
        db.refresh(current_member)

    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=current_member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False

    # Store new data for audit
    new_data = {
        "member_name": current_member.name,
        "member_mobile": current_member.mobile,
        "user_email": updated_user.email,
        "profile_photo_url": current_member.profile_photo_url
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
        user_id=current_user.id,
        name=current_member.name,
        email=updated_user.email,
        mobile=current_member.mobile,
        profile_photo_url=current_member.profile_photo_url,
        has_taken_genetic_test=has_taken_genetic_test
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
    current_user=Depends(get_current_user),
    current_member=Depends(get_current_member)
):
    """
    Upload profile photo for the current member.
    Accepts image files (jpg, jpeg, png, gif, webp) up to 5MB.
    """
    # Get current member (similar to /profile/me logic)
    if not current_member:
        # Try to get self profile member first
        default_member = db.query(Member).filter(
            Member.user_id == current_user.id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        # If no self profile, get the first member (oldest by created_at)
        if not default_member:
            default_member = db.query(Member).filter(
                Member.user_id == current_user.id,
                Member.is_deleted == False
            ).order_by(Member.created_at.asc()).first()
        
        if not default_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No member found. Please create a member profile first."
            )
        
        current_member = default_member
    
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
    
    # Generate unique filename: timestamp.ext (member_id will be added by S3 service)
    timestamp = int(uuid.uuid4().hex[:8], 16)  # Use part of UUID as timestamp-like identifier
    filename = f"{timestamp}{file_ext}"
    
    # Determine content type
    content_type = file.content_type or CONTENT_TYPE_MAP.get(file_ext, "image/jpeg")
    
    # Delete old profile photo from S3 if exists
    if current_member.profile_photo_url:
        try:
            s3_service = get_member_photo_s3_service()
            s3_service.delete_member_photo(current_member.profile_photo_url)
        except Exception as e:
            # Log but don't fail if old photo deletion fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete old member profile photo from S3: {str(e)}")
    
    # Upload to S3
    try:
        s3_service = get_member_photo_s3_service()
        profile_photo_url = s3_service.upload_member_photo(
            member_id=current_member.id,
            filename=filename,
            file_content=file_content,
            content_type=content_type
        )
    except ValueError as e:
        # S3 not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 configuration error: {str(e)}"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error uploading member photo to S3: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photo to S3: {str(e)}"
        )
    
    # Store old data for audit
    old_data = {
        "profile_photo_url": current_member.profile_photo_url
    }
    
    # Update member profile with S3 URL
    current_member.profile_photo_url = profile_photo_url
    db.commit()
    db.refresh(current_member)
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=current_member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    # Store new data for audit
    new_data = {
        "profile_photo_url": current_member.profile_photo_url
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
        user_id=current_user.id,
        name=current_member.name,
        email=current_user.email,
        mobile=current_member.mobile,
        profile_photo_url=current_member.profile_photo_url,
        has_taken_genetic_test=has_taken_genetic_test
    )
    
    return UploadPhotoResponse(
        status="success",
        message="Profile photo uploaded successfully.",
        data=data
    )


@router.delete("/delete-photo", response_model=DeletePhotoResponse)
def delete_profile_photo(
    request: Request,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
    current_member=Depends(get_current_member)
):
    """
    Delete profile photo for the current member.
    """
    # Get current member (similar to /profile/me logic)
    if not current_member:
        # Try to get self profile member first
        default_member = db.query(Member).filter(
            Member.user_id == current_user.id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        # If no self profile, get the first member (oldest by created_at)
        if not default_member:
            default_member = db.query(Member).filter(
                Member.user_id == current_user.id,
                Member.is_deleted == False
            ).order_by(Member.created_at.asc()).first()
        
        if not default_member:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No member found. Please create a member profile first."
            )
        
        current_member = default_member
    
    if not current_member.profile_photo_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No photo exists. Kindly upload the profile photo."
        )
    
    # Store old data for audit
    old_data = {
        "profile_photo_url": current_member.profile_photo_url
    }
    
    # Delete file from S3
    try:
        s3_service = get_member_photo_s3_service()
        s3_service.delete_member_photo(current_member.profile_photo_url)
    except ValueError as e:
        # S3 not configured - log but don't fail deletion (photo might already be deleted)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"S3 configuration error when deleting member profile photo: {str(e)}")
    except Exception as e:
        # Log but don't fail if S3 deletion fails (photo might already be deleted)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to delete member profile photo from S3: {str(e)}")
    
    # Remove photo URL from database
    current_member.profile_photo_url = None
    db.commit()
    db.refresh(current_member)
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=current_member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    # Store new data for audit
    new_data = {
        "profile_photo_url": None
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
        user_id=current_user.id,
        name=current_member.name,
        email=current_user.email,
        mobile=current_member.mobile,
        profile_photo_url=None,
        has_taken_genetic_test=has_taken_genetic_test
    )
    
    return DeletePhotoResponse(
        status="success",
        message="Profile photo deleted successfully.",
        data=data
    )
