from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from deps import get_db
from .Member_schema import MemberRequest, MemberResponse, MemberListResponse, MemberData
from .Member_crud import save_member, get_members_by_user
from Login_module.Utils.auth_user import get_current_user

router = APIRouter(prefix="/member", tags=["Member"])

# Save or update member
@router.post("/save", response_model=MemberResponse)
def save_member_api(
    req: MemberRequest,
    request: Request,
    category: str = Query("genome_testing", description="Category of the product"),
    plan_type: Optional[str] = Query(None, description="Plan type: single, couple, or family"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    member = save_member(
        db, user, req,
        category=category,
        plan_type=plan_type,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found for editing")

    return {
        "status": "success",
        "message": "Member saved successfully."
    }

# Get list of members for user
@router.get("/list", response_model=MemberListResponse)
def get_member_list(
    category: Optional[str] = Query(None, description="Filter by category"),
    plan_type: Optional[str] = Query(None, description="Filter by plan type"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    members = get_members_by_user(db, user, category=category, plan_type=plan_type)
    data = []
    for m in members:
        data.append({
            "member_id": m.id,
            "name": m.name,
            "relation": m.relation.value if hasattr(m.relation, 'value') else str(m.relation),
            "age": m.age,
            "gender": m.gender,
            "mobile": m.mobile
        })
    return {
        "status": "success",
        "message": "Member list fetched successfully.",
        "data": data
    }