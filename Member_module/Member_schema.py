from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, validator

class MemberRequest(BaseModel):
    member_id: int = Field(..., description="Member ID (for updates, use 0 for new members)", ge=0)
    name: str = Field(..., description="Member name", min_length=1, max_length=30)
    relation: str = Field(..., description="Relation type (accepts any string value, cannot be empty)")
    age: int = Field(..., description="Member age", ge=0, le=100)
    gender: str = Field(..., description="Gender (M/F/Other)", max_length=10)
    dob: date = Field(..., description="Date of birth")
    mobile: str = Field(..., description="Mobile number (10 digits)", min_length=10, max_length=10)
    
    @validator('relation')
    def validate_relation(cls, v):
        # Ensure relation is provided and not empty
        # Accepts ANY string value - no enum restrictions
        if v is None:
            raise ValueError('Relation is required and cannot be empty')
        
        # Convert to string (handles any type)
        v_str = str(v) if not isinstance(v, str) else v
        
        # Reject empty strings immediately
        if v_str == "":
            raise ValueError('Relation is required and cannot be empty')
        
        # Trim the relation string (remove leading/trailing spaces)
        v_trimmed = v_str.strip()
        
        # Reject whitespace-only strings
        if not v_trimmed:
            raise ValueError('Relation cannot be empty or whitespace only')
        
        # Return the trimmed value - stores exactly what user enters (trimmed)
        # No enum restrictions - accepts any non-empty string value
        return v_trimmed
    
    @validator('age')
    def validate_age(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Age must be between 0 and 100')
        return v
    
    @validator('gender')
    def validate_gender(cls, v):
        if v:
            v_upper = v.upper().strip()
            # Accept m, f, or other (case insensitive)
            if v_upper not in ['M', 'F', 'OTHER', 'MALE', 'FEMALE']:
                raise ValueError('Gender must be M, F, or Other')
            # Normalize to M, F, or Other
            if v_upper in ['M', 'MALE']:
                return 'M'
            elif v_upper in ['F', 'FEMALE']:
                return 'F'
            else:
                return 'Other'
        return v

    @validator('dob')
    def validate_dob(cls, v: Optional[date]):
        if v:
            if v > date.today():
                raise ValueError('Date of birth cannot be in the future')
            # Check if age is reasonable (not more than 100 years old)
            age = (date.today() - v).days // 365
            if age > 100:
                raise ValueError('Date of birth indicates age greater than 100 years')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v:
            # Basic mobile validation (exactly 10 digits)
            v = v.strip().replace(" ", "").replace("-", "")
            if len(v) != 10 or not v.isdigit():
                raise ValueError('Mobile number must be exactly 10 digits')
        return v


class EditMemberRequest(BaseModel):
    """Request schema for editing member - all fields optional for autofill"""
    name: Optional[str] = Field(None, description="Member name", min_length=1, max_length=30)
    relation: Optional[str] = Field(None, description="Relation type (accepts any string value)", min_length=1)
    age: Optional[int] = Field(None, description="Member age", ge=0, le=100)
    gender: Optional[str] = Field(None, description="Gender (M/F/Other)", max_length=10)
    dob: Optional[date] = Field(None, description="Date of birth")
    mobile: Optional[str] = Field(None, description="Mobile number (10 digits)", min_length=10, max_length=10)
    
    @validator('relation')
    def validate_relation(cls, v):
        # If relation is provided (not None), it must not be empty after trimming
        # Accepts ANY string value - no enum restrictions
        if v is not None:
            # Convert to string (handles any type)
            v_str = str(v) if not isinstance(v, str) else v
            
            # Reject empty strings immediately
            if v_str == "":
                raise ValueError('Relation cannot be empty. Please provide a valid relation or omit this field to keep existing value.')
            
            # Trim the relation string (remove leading/trailing spaces)
            v_trimmed = v_str.strip()
            
            # Reject whitespace-only strings
            if not v_trimmed:
                raise ValueError('Relation cannot be empty or whitespace only. Please provide a valid relation or omit this field to keep existing value.')
            
            # Return trimmed value - stores exactly what user enters (trimmed)
            # No enum restrictions - accepts any non-empty string value
            return v_trimmed
        # If None, return as-is (will be autofilled from existing member)
        return v
    
    @validator('age')
    def validate_age(cls, v):
        if v is not None and (v < 0 or v > 100):
            raise ValueError('Age must be between 0 and 100')
        return v
    
    @validator('gender')
    def validate_gender(cls, v):
        if v:
            v_upper = v.upper().strip()
            # Accept m, f, or other (case insensitive)
            if v_upper not in ['M', 'F', 'OTHER', 'MALE', 'FEMALE']:
                raise ValueError('Gender must be M, F, or Other')
            # Normalize to M, F, or Other
            if v_upper in ['M', 'MALE']:
                return 'M'
            elif v_upper in ['F', 'FEMALE']:
                return 'F'
            else:
                return 'Other'
        return v

    @validator('dob')
    def validate_dob(cls, v: Optional[date]):
        if v:
            if v > date.today():
                raise ValueError('Date of birth cannot be in the future')
            # Check if age is reasonable (not more than 100 years old)
            age = (date.today() - v).days // 365
            if age > 100:
                raise ValueError('Date of birth indicates age greater than 100 years')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v is not None:
            # Basic mobile validation (exactly 10 digits)
            v = v.strip().replace(" ", "").replace("-", "")
            if len(v) != 10 or not v.isdigit():
                raise ValueError('Mobile number must be exactly 10 digits')
        return v

class MemberData(BaseModel):
    member_id: int
    name: str
    relation: str
    age: Optional[int] = None
    gender: Optional[str] = None
    dob: Optional[date] = None
    mobile: Optional[str] = None

class MemberResponse(BaseModel):
    status: str
    message: str

class MemberListResponse(BaseModel):
    status: str
    message: str
    data: List[MemberData]