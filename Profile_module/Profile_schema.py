from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional


class EditProfileRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255, example="John Doe")
    email: EmailStr = Field(..., example="john.doe@example.com")
    mobile: str = Field(..., min_length=10, max_length=15, example="9876543210")

    @validator('mobile')
    def validate_mobile(cls, v):
        # Remove any spaces or special characters
        cleaned = ''.join(filter(str.isdigit, v))
        if len(cleaned) < 10 or len(cleaned) > 15:
            raise ValueError('Mobile number must be between 10 and 15 digits')
        return cleaned
    
    @validator('name')
    def validate_name(cls, v):
        if v.strip() == '':
            raise ValueError('Name cannot be empty or just whitespace')
        return v.strip()

    class Config:
        json_schema_extra = {
            "example": {
                "name": "John Doe",
                "email": "john.doe@example.com",
                "mobile": "9876543210"
            }
        }


class UserProfileData(BaseModel):
    user_id: int
    name: Optional[str]
    email: Optional[str]
    mobile: Optional[str]
    profile_photo_url: Optional[str] = None

    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "name": "John Doe",
                "email": "john.doe@example.com",
                "mobile": "9876543210"
            }
        }


class EditProfileResponse(BaseModel):
    status: str
    message: str
    data: UserProfileData

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Profile updated successfully.",
                "data": {
                    "user_id": 1,
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "mobile": "9876543210"
                }
            }
        }


class GetProfileResponse(BaseModel):
    status: str
    message: str
    data: UserProfileData

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Profile retrieved successfully.",
                "data": {
                    "user_id": 1,
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "mobile": "9876543210",
                    "profile_photo_url": "profile_photos/1_abc12345.jpg"
                }
            }
        }


class UploadPhotoResponse(BaseModel):
    status: str
    message: str
    data: UserProfileData

    class Config:
        json_schema_extra = {
            "example": {
                "status": "success",
                "message": "Profile photo uploaded successfully.",
                "data": {
                    "user_id": 1,
                    "name": "John Doe",
                    "email": "john.doe@example.com",
                    "mobile": "9876543210",
                    "profile_photo_url": "profile_photos/1_abc12345.jpg"
                }
            }
        }