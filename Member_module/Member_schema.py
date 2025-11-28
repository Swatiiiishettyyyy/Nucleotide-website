from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field, validator

class MemberRequest(BaseModel):
    member_id: int = Field(..., description="Member ID (for updates, use 0 for new members)", ge=0)
    name: str = Field(..., description="Member name", min_length=1, max_length=100)
    relation: str = Field(..., description="Relation type (self/spouse/child/parent/sibling/other)", min_length=1)
    age: int = Field(..., description="Member age", ge=0, le=150)
    gender: str = Field(..., description="Gender (M/F/Other)", max_length=20)
    dob: date = Field(..., description="Date of birth")
    mobile: str = Field(..., description="Mobile number (10 digits)", min_length=10, max_length=10)
    
    @validator('age')
    def validate_age(cls, v):
        if v is not None and (v < 0 or v > 150):
            raise ValueError('Age must be between 0 and 150')
        return v
    
    @validator('gender')
    def validate_gender(cls, v):
        if v and v.upper() not in ['M', 'F', 'MALE', 'FEMALE', 'OTHER']:
            raise ValueError('Gender must be M, F, or Other')
        return v.upper() if v else None

    @validator('dob')
    def validate_dob(cls, v: Optional[date]):
        if v and v > date.today():
            raise ValueError('Date of birth cannot be in the future')
        return v
    
    @validator('mobile')
    def validate_mobile(cls, v):
        if v:
            # Basic mobile validation (10 digits)
            v = v.strip().replace(" ", "").replace("-", "")
            if len(v) != 10 or not v.isdigit():
                raise ValueError('Mobile number must be 10 digits')
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