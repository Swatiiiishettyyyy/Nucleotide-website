from .Member_model import Member, RelationType
from .Member_audit_model import MemberAuditLog
from sqlalchemy.orm import Session
from fastapi import HTTPException
from typing import Optional
from datetime import datetime

def save_member(
    db: Session,
    user,
    req,
    category: str = "genome_testing",
    plan_type: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
):
    """
    Save or update member.
    Validates that member is not already in a conflicting plan type.
    """
    # Check for duplicate member in same category
    if req.member_id == 0:  # New member
        # Check if member with same name AND relation already exists in same category
        # This allows same name with different relations (e.g., "John" as self and "John" as child)
        existing = db.query(Member).filter(
            Member.user_id == user.id,
            Member.name == req.name,
            Member.relation == RelationType[req.relation.upper()] if hasattr(RelationType, req.relation.upper()) else RelationType.OTHER,
            Member.associated_category == category
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=400,
                detail=f"Member '{req.name}' with relation '{req.relation}' already exists in {category} category. Cannot add duplicate."
            )
        
        # If adding to family plan, check if member is already in personal/couple plan
        if plan_type == "family":
            conflicting_member = db.query(Member).filter(
                Member.user_id == user.id,
                Member.name == req.name,
                Member.associated_category == category,
                Member.associated_plan_type.in_(["single", "couple"])
            ).first()
            
            if conflicting_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"Member '{req.name}' is already associated with a personal/couple plan. Cannot add to family plan."
                )
        else:
            # If adding to personal/couple, check if member is in family plan
            conflicting_member = db.query(Member).filter(
                Member.user_id == user.id,
                Member.name == req.name,
                Member.associated_category == category,
                Member.associated_plan_type == "family"
            ).first()
            
            if conflicting_member:
                raise HTTPException(
                    status_code=400,
                    detail=f"Member '{req.name}' is already associated with a family plan. Cannot add to personal/couple plan."
                )
    
    # Convert relation string to enum
    try:
        relation_enum = RelationType[req.relation.upper()] if hasattr(RelationType, req.relation.upper()) else RelationType.OTHER
    except:
        relation_enum = RelationType.OTHER
    
    old_data = None
    
    if req.member_id == 0:
        # Create new member
        member = Member(
            user_id=user.id,
            name=req.name,
            relation=relation_enum,
            age=req.age,
            gender=req.gender,
            mobile=req.mobile,
            associated_category=category,
            associated_plan_type=plan_type
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
            "mobile": req.mobile,
            "category": category,
            "plan_type": plan_type
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
            return None
        
        # Store old data before update
        old_data = {
            "name": member.name,
            "relation": str(member.relation.value) if hasattr(member.relation, 'value') else str(member.relation),
            "age": member.age,
            "gender": member.gender,
            "mobile": member.mobile
        }
        
        member.name = req.name
        member.relation = relation_enum
        member.age = req.age
        member.gender = req.gender
        member.mobile = req.mobile
        # Don't update category/plan_type on edit (to maintain integrity)
        db.commit()
        
        # Audit log for update
        new_data = {
            "name": req.name,
            "relation": req.relation,
            "age": req.age,
            "gender": req.gender,
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
    return member

def get_members_by_user(db: Session, user, category: Optional[str] = None, plan_type: Optional[str] = None):
    """Get members for user, optionally filtered by category and plan_type"""
    query = db.query(Member).filter(Member.user_id == user.id)
    
    if category:
        query = query.filter(Member.associated_category == category)
    if plan_type:
        query = query.filter(Member.associated_plan_type == plan_type)
    
    return query.all()