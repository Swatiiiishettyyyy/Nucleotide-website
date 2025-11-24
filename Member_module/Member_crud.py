from .Member_model import Member, RelationType
from .Member_audit_model import MemberAuditLog
from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException
from typing import Any, Dict, Optional, Union

from Product_module.category_service import resolve_category

_VALID_PLAN_TYPES = {"single", "couple", "family"}


def _normalize_relation(relation: Optional[str]) -> RelationType:
    """Convert incoming relation string to RelationType enum."""
    if not relation:
        return RelationType.OTHER
    relation_key = relation.strip().upper()
    return RelationType.__members__.get(relation_key, RelationType.OTHER)


def _normalize_plan_type(plan_type: Optional[str]) -> Optional[str]:
    if not plan_type:
        return None
    plan = plan_type.strip().lower()
    if plan not in _VALID_PLAN_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported plan_type '{plan_type}'. Allowed values: single, couple, family.",
        )
    return plan


def _family_member_count(db: Session, user_id: int, category_filter, exclude_member_id: Optional[int] = None) -> int:
    """Count current family-plan members for a user/category."""
    query = db.query(Member).filter(
        Member.user_id == user_id,
        Member.associated_plan_type == "family",
        category_filter,
    )
    if exclude_member_id:
        query = query.filter(Member.id != exclude_member_id)
    return query.count()


def _build_family_plan_status(db: Session, user_id: int, member: Member) -> Optional[Dict[str, Any]]:
    """Return family-plan progress details for the member's category."""
    if member.associated_plan_type != "family":
        return None

    category_filter = or_(
        Member.associated_category_id == member.associated_category_id,
        Member.associated_category == member.associated_category,
    )
    total_members = _family_member_count(db, user_id, category_filter)
    mandatory_slots_remaining = max(0, 3 - total_members)
    optional_slot_available = total_members < 4

    if mandatory_slots_remaining > 0:
        status = "incomplete"
    elif optional_slot_available:
        status = "ready"
    else:
        status = "full"

    return {
        "total_members": total_members,
        "mandatory_slots_remaining": mandatory_slots_remaining,
        "optional_slot_available": optional_slot_available,
        "status": status,
    }

def save_member(
    db: Session,
    user,
    req,
    category_id: Optional[int] = None,
    plan_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """
    Save or update member.
    Validates that member is not already in a conflicting plan type.
    """
    plan_type_normalized = _normalize_plan_type(plan_type)
    family_status: Optional[Dict[str, Any]] = None

    category_obj = resolve_category(db, category_id)
    category_name = category_obj.name
    category_filter = or_(
        Member.associated_category_id == category_obj.id,
        Member.associated_category == category_name
    )

    relation_enum = _normalize_relation(req.relation)

    # Check for duplicate member in same category
    if req.member_id == 0:  # New member
        # Check if member with same name AND relation already exists in same category
        # This allows same name with different relations (e.g., "John" as self and "John" as child)
        existing = db.query(Member).filter(
            Member.user_id == user.id,
            Member.name == req.name,
            Member.relation == relation_enum,
            category_filter
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Member '{req.name}' with relation '{req.relation}' already exists in {category_name} category. Cannot add duplicate."
            )
        
        # If adding to family plan, check if member is already in personal/couple plan
        if plan_type_normalized == "family":
            conflicting_member = db.query(Member).filter(
                Member.user_id == user.id,
                Member.name == req.name,
                category_filter,
                Member.associated_plan_type.in_(["single", "couple"])
            ).first()
            
            if conflicting_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"Member '{req.name}' is already associated with a personal/couple plan. Cannot add to family plan."
                )

            current_family_members = _family_member_count(db, user.id, category_filter)
            if current_family_members >= 4:
                raise HTTPException(
                    status_code=400,
                    detail="Family plan allows up to 4 members (3 mandatory + 1 optional). Remove an existing member before adding a new one."
                )
        else:
            # If adding to personal/couple, check if member is in family plan
            conflicting_member = db.query(Member).filter(
                Member.user_id == user.id,
                Member.name == req.name,
                category_filter,
                Member.associated_plan_type == "family"
            ).first()
            
            if conflicting_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"Member '{req.name}' is already associated with a family plan. Cannot add to personal/couple plan."
                )
    
    old_data = None
    
    if req.member_id == 0:
        # Create new member
        member = Member(
            user_id=user.id,
            name=req.name,
            relation=relation_enum,
            age=req.age,
            gender=req.gender,
            dob=req.dob,
            mobile=req.mobile,
            associated_category=category_name,
            associated_category_id=category_obj.id,
            associated_plan_type=plan_type_normalized
        )
        db.add(member)
        db.commit()
        db.refresh(member)
        
        # Audit log for creation
        new_data = {
            "name": req.name,
            "relation": req.relation,
            "age": req.age,
            "gender": req.gender,
            "dob": req.dob.isoformat() if req.dob else None,
            "mobile": req.mobile,
            "category": category_name,
            "plan_type": plan_type_normalized
        }
        audit = MemberAuditLog(
            user_id=user.id,
            member_id=member.id,
            event_type="CREATED",
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        db.add(audit)
        db.commit()
    else:
        # Update existing member
        member = db.query(Member).filter_by(id=req.member_id, user_id=user.id).first()
        if not member:
            return None, None
        
        # Store old data before update
        old_data = {
            "name": member.name,
            "relation": str(member.relation.value) if hasattr(member.relation, 'value') else str(member.relation),
            "age": member.age,
            "gender": member.gender,
            "dob": member.dob.isoformat() if member.dob else None,
            "mobile": member.mobile
        }
        
        member.name = req.name
        member.relation = relation_enum
        member.age = req.age
        member.gender = req.gender
        member.dob = req.dob
        member.mobile = req.mobile
        # Don't update category/plan_type on edit (to maintain integrity)
        db.commit()
        
        # Audit log for update
        new_data = {
            "name": req.name,
            "relation": req.relation,
            "age": req.age,
            "gender": req.gender,
            "dob": req.dob.isoformat() if req.dob else None,
            "mobile": req.mobile
        }
        audit = MemberAuditLog(
            user_id=user.id,
            member_id=member.id,
            event_type="UPDATED",
            old_data=old_data,
            new_data=new_data,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id
        )
        db.add(audit)
        db.commit()

    family_status = _build_family_plan_status(db, user.id, member)
    return member, family_status

def get_members_by_user(db: Session, user, category: Optional[Union[int, str]] = None, plan_type: Optional[str] = None):
    """Get members for user, optionally filtered by category and plan_type"""
    query = db.query(Member).filter(Member.user_id == user.id)
    
    if category:
        if isinstance(category, int):
            query = query.filter(Member.associated_category_id == category)
        else:
            query = query.filter(Member.associated_category == category)
    if plan_type:
        query = query.filter(Member.associated_plan_type == plan_type)
    
    return query.all()