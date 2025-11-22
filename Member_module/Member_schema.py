from pydantic import BaseModel, validator
from typing import List, Optional

class MemberRequest(BaseModel):
    member_id: int
    name: str
    relation: str
    age: Optional[int] = None
    gender: Optional[str] = None  # M, F, Other
    mobile: Optional[str] = None
    
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
    mobile: Optional[str] = None

class MemberResponse(BaseModel):
    status: str
    message: str

class MemberListResponse(BaseModel):
    status: str
    message: str
    data: List[MemberData]