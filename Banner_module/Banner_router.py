from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from typing import Optional, List
from datetime import datetime, date
from pathlib import Path
import uuid
import logging

from .Banner_model import Banner
from .Banner_schema import (
    BannerCreate,
    BannerUpdate,
    BannerResponse,
    BannerListResponse,
    BannerSingleResponse,
    BannerAction
)
from .Banner_s3_service import get_banner_image_s3_service
from deps import get_db
from Login_module.Utils.datetime_utils import to_ist_isoformat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/banners", tags=["Banners"])

# Allowed image file extensions
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB

# Content type mapping for banner images
CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp"
}


def convert_date_to_datetime(date_obj: Optional[date]) -> Optional[datetime]:
    """Convert date to datetime with time set to start of day"""
    if date_obj:
        if isinstance(date_obj, datetime):
            return date_obj
        return datetime.combine(date_obj, datetime.min.time())
    return None


def format_banner_response(banner: Banner) -> BannerResponse:
    """Convert Banner model to BannerResponse schema"""
    return BannerResponse(
        id=banner.id,
        title=banner.title,
        subtitle=banner.subtitle,
        image_url=banner.image_url,
        action=banner.action,
        position=banner.position,
        is_active=banner.is_active,
        start_date=banner.start_date.date().isoformat() if banner.start_date else None,
        end_date=banner.end_date.date().isoformat() if banner.end_date else None,
        created_at=to_ist_isoformat(banner.created_at) if banner.created_at else "",
        updated_at=to_ist_isoformat(banner.updated_at)
    )


@router.get("", response_model=BannerListResponse)
def get_banners(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """
    Get list of banners.
    By default, returns only active banners that are within their date range.
    Set active_only=false to get all banners (including inactive).
    """
    query = db.query(Banner).filter(Banner.is_deleted == False)
    
    if active_only:
        query = query.filter(Banner.is_active == True)
        
        # Filter by date range - banner is active if:
        # - start_date is NULL or start_date <= now
        # - end_date is NULL or end_date >= now
        now = datetime.now()
        query = query.filter(
            or_(Banner.start_date.is_(None), Banner.start_date <= now)
        ).filter(
            or_(Banner.end_date.is_(None), Banner.end_date >= now)
        )
    
    # Order by position (ascending) - lower numbers appear first
    banners = query.order_by(Banner.position.asc(), Banner.created_at.desc()).all()
    
    return BannerListResponse(
        status="success",
        message=f"Retrieved {len(banners)} banner(s).",
        data=[format_banner_response(banner) for banner in banners]
    )


@router.get("/{banner_id}", response_model=BannerSingleResponse)
def get_banner(
    banner_id: int,
    db: Session = Depends(get_db)
):
    """Get a single banner by ID"""
    banner = db.query(Banner).filter(
        Banner.id == banner_id,
        Banner.is_deleted == False
    ).first()
    
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner not found"
        )
    
    return BannerSingleResponse(
        status="success",
        message="Banner retrieved successfully.",
        data=format_banner_response(banner)
    )


@router.post("", response_model=BannerSingleResponse)
def create_banner(
    banner_data: BannerCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new banner.
    Note: Use POST /banners/upload-image to upload banner image first.
    """
    # Convert action to dict if provided
    action_dict = None
    if banner_data.action:
        action_dict = banner_data.action.dict(exclude_none=True)
    
    # Convert dates to datetimes
    start_datetime = convert_date_to_datetime(banner_data.start_date)
    end_datetime = convert_date_to_datetime(banner_data.end_date)
    
    # Validate date range
    if start_datetime and end_datetime and end_datetime < start_datetime:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date"
        )
    
    # Create banner
    new_banner = Banner(
        title=banner_data.title,
        subtitle=banner_data.subtitle,
        image_url=banner_data.image_url or "",
        action=action_dict,
        position=banner_data.position,
        is_active=banner_data.is_active,
        start_date=start_datetime,
        end_date=end_datetime
    )
    
    db.add(new_banner)
    db.commit()
    db.refresh(new_banner)
    
    return BannerSingleResponse(
        status="success",
        message="Banner created successfully.",
        data=format_banner_response(new_banner)
    )


@router.post("/upload-image", response_model=BannerSingleResponse)
async def upload_banner_image(
    file: UploadFile = File(...),
    banner_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    """
    Upload banner image to S3.
    If banner_id is provided, updates existing banner's image_url.
    If banner_id is not provided, creates a new banner with the uploaded image.
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
    
    # Generate unique filename
    timestamp = int(uuid.uuid4().hex[:8], 16)
    filename = f"{timestamp}{file_ext}"
    
    # Determine content type
    content_type = file.content_type or CONTENT_TYPE_MAP.get(file_ext, "image/jpeg")
    
    try:
        s3_service = get_banner_image_s3_service()
        
        if banner_id:
            # Update existing banner
            banner = db.query(Banner).filter(
                Banner.id == banner_id,
                Banner.is_deleted == False
            ).first()
            
            if not banner:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Banner not found"
                )
            
            # Delete old image from S3 if exists
            if banner.image_url:
                try:
                    s3_service.delete_banner_image(banner.image_url)
                except Exception as e:
                    logger.warning(f"Failed to delete old banner image from S3: {str(e)}")
            
            # Upload new image
            image_url = s3_service.upload_banner_image(
                banner_id=banner.id,
                filename=filename,
                file_content=file_content,
                content_type=content_type
            )
            
            # Update banner
            banner.image_url = image_url
            db.commit()
            db.refresh(banner)
            
            return BannerSingleResponse(
                status="success",
                message="Banner image uploaded successfully.",
                data=format_banner_response(banner)
            )
        else:
            # Create new banner with uploaded image
            image_url = s3_service.upload_banner_image(
                banner_id=0,  # Temporary ID, will be updated after banner creation
                filename=filename,
                file_content=file_content,
                content_type=content_type
            )
            
            # Create new banner
            new_banner = Banner(
                title=None,
                subtitle=None,
                image_url=image_url,
                action=None,
                position=0,
                is_active=True,
                start_date=None,
                end_date=None
            )
            
            db.add(new_banner)
            db.commit()
            db.refresh(new_banner)
            
            # Update S3 key with actual banner ID (re-upload with correct key)
            # This is optional - you can keep the original key or re-upload
            # For simplicity, we'll keep the original upload
            
            return BannerSingleResponse(
                status="success",
                message="Banner created with image successfully.",
                data=format_banner_response(new_banner)
            )
            
    except ValueError as e:
        # S3 not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 configuration error: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Error uploading banner image to S3: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload image to S3: {str(e)}"
        )


@router.put("/{banner_id}", response_model=BannerSingleResponse)
def update_banner(
    banner_id: int,
    banner_data: BannerUpdate,
    db: Session = Depends(get_db)
):
    """
    Update an existing banner.
    Only provided fields will be updated.
    """
    banner = db.query(Banner).filter(
        Banner.id == banner_id,
        Banner.is_deleted == False
    ).first()
    
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner not found"
        )
    
    # Update fields if provided
    update_data = banner_data.dict(exclude_unset=True, exclude_none=True)
    
    if 'title' in update_data:
        banner.title = update_data['title']
    if 'subtitle' in update_data:
        banner.subtitle = update_data['subtitle']
    if 'image_url' in update_data:
        banner.image_url = update_data['image_url']
    if 'position' in update_data:
        banner.position = update_data['position']
    if 'is_active' in update_data:
        banner.is_active = update_data['is_active']
    if 'start_date' in update_data:
        banner.start_date = convert_date_to_datetime(update_data['start_date'])
    if 'end_date' in update_data:
        banner.end_date = convert_date_to_datetime(update_data['end_date'])
    if 'action' in update_data:
        # Convert action to dict
        action_obj = update_data['action']
        if isinstance(action_obj, dict):
            banner.action = action_obj
        else:
            banner.action = action_obj.dict(exclude_none=True) if action_obj else None
    
    # Validate date range
    if banner.start_date and banner.end_date and banner.end_date < banner.start_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="end_date must be after start_date"
        )
    
    db.commit()
    db.refresh(banner)
    
    return BannerSingleResponse(
        status="success",
        message="Banner updated successfully.",
        data=format_banner_response(banner)
    )


@router.delete("/{banner_id}")
def delete_banner(
    banner_id: int,
    db: Session = Depends(get_db)
):
    """
    Soft delete a banner.
    Deletes the banner image from S3 and marks banner as deleted.
    """
    banner = db.query(Banner).filter(
        Banner.id == banner_id,
        Banner.is_deleted == False
    ).first()
    
    if not banner:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Banner not found"
        )
    
    # Delete image from S3
    if banner.image_url:
        try:
            s3_service = get_banner_image_s3_service()
            s3_service.delete_banner_image(banner.image_url)
        except Exception as e:
            logger.warning(f"Failed to delete banner image from S3: {str(e)}")
    
    # Soft delete banner
    from Login_module.Utils.datetime_utils import now_ist
    banner.is_deleted = True
    banner.deleted_at = now_ist()
    
    db.commit()
    
    return {
        "status": "success",
        "message": "Banner deleted successfully."
    }

