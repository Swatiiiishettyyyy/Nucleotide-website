from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from deps import get_db
from .Member_schema import MemberRequest, MemberResponse, MemberListResponse, MemberData, EditMemberRequest
from .Member_crud import save_member, get_members_by_user
from .Member_model import Member
from Login_module.Utils.auth_user import get_current_user

router = APIRouter(prefix="/member", tags=["Member"])

# Create new member
@router.post("/save", response_model=MemberResponse)
def save_member_api(
    req: MemberRequest,
    request: Request,
    category_id: Optional[int] = Query(None, description="Category ID (defaults to Genetic Testing)"),
    plan_type: Optional[str] = Query(None, description="Plan type: single, couple, or family"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Create a new member (requires authentication).
    Use member_id = 0 for new members.
    Relation validation is handled by schema validator - it will reject empty or whitespace-only values.
    """
    # Set member_id to 0 for new members
    req.member_id = 0
    
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
        raise HTTPException(status_code=404, detail="Failed to create member")

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

# Update existing member
@router.put("/edit/{member_id}", response_model=MemberResponse)
def edit_member_api(
    member_id: int,
    req: EditMemberRequest,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Update an existing member (requires authentication).
    
    This endpoint autofills existing member details when member_id is provided.
    You can send only the fields you want to change - missing fields will be autofilled from existing member.
    
    Workflow:
    1. Send PUT request with member_id in path and only fields you want to change in body
    2. Endpoint autofills missing fields from existing member
    3. Cannot edit member if it's associated with cart items.
    4. Category and plan_type cannot be changed during edit (preserved from existing member).
    
    Example: To change only name, send: {"name": "New Name"}
    All other fields will be autofilled from existing member.
    """
    # Fetch existing member for autofill
    existing_member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id
    ).first()
    
    if not existing_member:
        raise HTTPException(status_code=404, detail="Member not found or does not belong to you")
    
    # Autofill: Merge existing member data with request data (request takes precedence)
    # Get relation value - use directly from req object (already validated and trimmed by EditMemberRequest validator)
    if req.relation is not None:
        # Relation was provided in request - use it (already validated and trimmed by validator)
        # The validator ensures it's not empty and trims it, so we can use it directly
        relation_value = req.relation
    else:
        # Relation not provided - use existing value from database
        relation_value = existing_member.relation
    
    # Ensure relation_value is not empty (safety check)
    if not relation_value or not str(relation_value).strip():
        raise HTTPException(
            status_code=422,
            detail="Relation cannot be empty. Please provide a valid relation value."
        )
    
    # Convert to string and trim to ensure consistency
    relation_value = str(relation_value).strip()
    
    # Convert other fields to dict for autofill
    req_dict = req.dict(exclude_unset=True, exclude_none=True)
    
    # Create complete MemberRequest with autofilled data
    # Fields sent in request will override existing values
    # Fields not sent will be autofilled from existing member
    complete_req = MemberRequest(
        member_id=member_id,
        name=req_dict.get('name', existing_member.name),
        relation=relation_value,  # Use the validated and trimmed relation value
        age=req_dict.get('age', existing_member.age),
        gender=req_dict.get('gender', existing_member.gender),
        dob=req_dict.get('dob', existing_member.dob),
        mobile=req_dict.get('mobile', existing_member.mobile)
    )
    
    # Get IP and user agent
    ip_address = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    correlation_id = str(uuid.uuid4())
    
    # For edit, category_id and plan_type are not used (preserved from existing member)
    member, family_status = save_member(
        db, user, complete_req,
        category_id=None,  # Not used for edit
        plan_type=None,    # Not used for edit
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    if not member:
        raise HTTPException(status_code=404, detail="Member not found or does not belong to you")

    message = "Member updated successfully."
    if family_status:
        mandatory_remaining = family_status.get("mandatory_slots_remaining", 0)
        total_members = family_status.get("total_members")
        if mandatory_remaining > 0:
            message = (
                f"Member updated. Add {mandatory_remaining} more mandatory family member(s) "
                f"to reach the required 3 (current: {total_members}/4)."
            )
        elif family_status.get("optional_slot_available", False):
            message = (
                f"Member updated. Family plan has {total_members}/4 members; "
                "you may add the optional slot."
            )
        else:
            message = "Member updated. Family plan slots are full (4/4)."

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
        # Read relation from database - it should be a string value
        relation_value = str(m.relation) if m.relation is not None else ""
        
        data.append({
            "member_id": m.id,
            "name": m.name,
            "relation": relation_value,  # Read relation as string from database
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
        "relation": str(member.relation),  # Now a string, no need for .value check
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