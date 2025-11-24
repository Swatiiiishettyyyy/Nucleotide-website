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
    category_id: Optional[int] = Query(None, description="Category ID (defaults to Genetic Testing)"),
    plan_type: Optional[str] = Query(None, description="Plan type: single, couple, or family"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    # Get IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    member, family_status = save_member(
        db, user, req,
        category_id=category_id,
        plan_type=plan_type,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found for editing")

    message = "Member saved successfully."
    if family_status:
        mandatory_remaining = family_status.get("mandatory_slots_remaining", 0)
        total_members = family_status.get("total_members")
        if mandatory_remaining > 0:
            message = (
                f"Member saved. Add {mandatory_remaining} more mandatory family member(s) "
                f"to reach the required 3 (current: {total_members}/4)."
            )
        elif family_status.get("optional_slot_available", False):
            message = (
                f"Member saved. Family plan has {total_members}/4 members; "
                "you may add the optional slot."
            )
        else:
            message = "Member saved. Family plan slots are full (4/4)."

    return {
        "status": "success",
        "message": message
    }

# Get list of members for user
@router.get("/list", response_model=MemberListResponse)
def get_member_list(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    plan_type: Optional[str] = Query(None, description="Filter by plan type"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    members = get_members_by_user(db, user, category=category_id, plan_type=plan_type)
    data = []
    for m in members:
        data.append({
            "member_id": m.id,
            "name": m.name,
            "relation": m.relation.value if hasattr(m.relation, 'value') else str(m.relation),
            "age": m.age,
            "gender": m.gender,
            "dob": m.dob.isoformat() if m.dob else None,
            "mobile": m.mobile
        })
    return {
        "status": "success",
        "message": "Member list fetched successfully.",
        "data": data
    }