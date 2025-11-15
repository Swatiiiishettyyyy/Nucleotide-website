from pydantic import BaseModel
from typing import List

class MemberRequest(BaseModel):
    member_id: int
    name: str
    relation: str

class MemberData(BaseModel):
    member_id: int
    name: str
    relation: str

class MemberResponse(BaseModel):
    status: str
    message: str

class MemberListResponse(BaseModel):
    status: str
    message: str
    data: List[MemberData]