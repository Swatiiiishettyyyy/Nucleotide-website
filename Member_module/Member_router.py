from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from deps import get_db
from .Member_schema import MemberRequest, MemberResponse, MemberListResponse, MemberData
from .Member_crud import save_member, get_members_by_user
from .Member_model import Member
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

# Delete member
@router.delete("/delete/{member_id}")
def delete_member_api(
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """Delete member. Prevents deletion if member is linked to cart items.
    Note: Members can be deleted even if associated with confirmed orders,
    since orders use OrderSnapshot to preserve data integrity.
    """
    from Cart_module.Cart_model import CartItem
    from Product_module.Product_model import Product
    from .Member_audit_model import MemberAuditLog
    import uuid
    
    # Verify member exists and belongs to user
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )
    
    # Check if member is linked to any cart items
    cart_items = (
        db.query(CartItem, Product)
        .join(Product, CartItem.product_id == Product.ProductId)
        .filter(
            CartItem.member_id == member_id,
            CartItem.user_id == user.id
        )
        .all()
    )
    
    if cart_items:
        # Get product names and group IDs for better error message
        conflicts = []
        for cart_item, product in cart_items:
            conflicts.append({
                "product_id": product.ProductId,
                "product_name": product.Name,
                "plan_type": product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type)
            })
        
        # Group by product
        from collections import defaultdict
        product_conflicts = defaultdict(list)
        for conflict in conflicts:
            product_conflicts[conflict["product_name"]].append(conflict["plan_type"])
        
        conflict_details = ", ".join([
            f"{name} ({'/'.join(set(types))})" 
            for name, types in product_conflicts.items()
        ])
        
        raise HTTPException(
            status_code=422,
            detail=f"Member '{member.name}' is associated with {len(cart_items)} cart item(s) for product(s): {conflict_details}."
        )
    
    # Note: We don't check orders because confirmed orders use OrderSnapshot,
    # so deleting/editing members won't affect existing orders
    
    # Store member data before deletion for audit log
    old_data = {
        "member_id": member_id,
        "name": member.name,
        "relation": str(member.relation.value) if hasattr(member.relation, 'value') else str(member.relation),
        "age": member.age,
        "gender": member.gender,
        "dob": member.dob.isoformat() if member.dob else None,
        "mobile": member.mobile,
        "category": member.associated_category,
        "plan_type": member.associated_plan_type
    }
    
    # Get IP and user agent for audit log
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    # Store member name before deletion
    member_name = member.name
    member_identifier = f"{member.name} ({member.mobile})"
    
    # Create audit log for deletion BEFORE deleting the member
    # This ensures the foreign key constraint is satisfied
    audit = MemberAuditLog(
        user_id=user.id,
        member_id=member_id,  # Member still exists at this point
        member_name=member_name,
        member_identifier=member_identifier,
        event_type="DELETED",
        old_data=old_data,
        new_data=None,  # No new data for deletion
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(audit)
    
    # Now delete the member
    db.delete(member)
    
    # Commit both operations in a single transaction
    db.commit()
    
    return {
        "status": "success",
        "message": f"Member '{member_name}' deleted successfully."
    }