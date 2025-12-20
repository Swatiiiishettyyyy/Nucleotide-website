from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile, File, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
import uuid
from pathlib import Path
import os

from deps import get_db
from .Member_schema import (
    MemberRequest, MemberResponse, MemberListResponse, MemberData, EditMemberRequest,
    InitiateTransferRequest, InitiateTransferResponse
)
from .Member_crud import save_member, get_members_by_user
from .Member_transfer_crud import (
    create_transfer_log, get_pending_transfer_by_phone,
    execute_member_transfer
)
from .Member_model import Member
from .Member_transfer_model import MemberTransferLog
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.Utils import security
from Login_module.Utils.datetime_utils import to_ist_isoformat
from Login_module.Device.Device_session_crud import get_device_session

router = APIRouter(prefix="/member", tags=["Member"])
security_scheme = HTTPBearer()

# Helper function to generate new token with selected_member_id
def generate_token_with_member(
    db: Session,
    user_id: int,
    session_id: int,
    device_platform: str,
    selected_member_id: Optional[int] = None
) -> str:
    """
    Generate a new JWT token with selected_member_id.
    Validates session before generating token.
    Raises HTTPException if session is invalid.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    # Validate session exists and is active
    session = get_device_session(db, session_id)
    if not session:
        logger.error(f"Session {session_id} not found when generating token for user {user_id}")
        raise HTTPException(
            status_code=401,
            detail="Session not found"
        )
    
    if not session.is_active:
        logger.error(f"Session {session_id} is inactive when generating token for user {user_id}")
        raise HTTPException(
            status_code=401,
            detail="Session is inactive"
        )
    
    # Validate member belongs to user and is not deleted if member_id is provided
    if selected_member_id:
        member = db.query(Member).filter(
            Member.id == selected_member_id,
            Member.user_id == user_id,
            Member.is_deleted == False
        ).first()
        if not member:
            logger.error(f"Member {selected_member_id} not found, doesn't belong to user {user_id}, or is deleted")
            raise HTTPException(
                status_code=404,
                detail="Member not found or doesn't belong to you"
            )
    
    from dotenv import load_dotenv
    import os
    load_dotenv()
    ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 86400))
    
    token_data = {
        "sub": str(user_id),
        "session_id": str(session_id),
        "device_platform": device_platform
    }
    if selected_member_id:
        token_data["selected_member_id"] = str(selected_member_id)
    
    try:
        return security.create_access_token(token_data, expires_delta=ACCESS_TOKEN_EXPIRE_SECONDS)
    except Exception as e:
        logger.error(f"Error creating access token for user {user_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Error generating access token"
        )

# Create new member
@router.post("/save", response_model=MemberResponse)
def save_member_api(
    req: MemberRequest,
    request: Request,
    category_id: Optional[int] = Query(None, description="Category ID (defaults to Genetic Testing)"),
    plan_type: Optional[str] = Query(None, description="Plan type: single, couple, or family"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
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

    # Check if this is the first member for the user (check BEFORE creating to avoid race condition)
    # Count existing non-deleted members before the one we just created
    existing_member_count = db.query(Member).filter(
        Member.user_id == user.id,
        Member.id != member.id,
        Member.is_deleted == False
    ).count()
    is_first_member = existing_member_count == 0
    
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

    response = {
        "status": "success",
        "message": message
    }
    
    # If this is the first member, auto-select it and return new token
    if is_first_member:
        try:
            # Extract token from credentials dependency (more reliable than manual extraction)
            token = credentials.credentials
            payload = security.decode_access_token(token)
            session_id = payload.get("session_id")
            device_platform = payload.get("device_platform", "unknown")
            
            if not session_id:
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"No session_id in token for user {user.id} when creating first member")
            else:
                # generate_token_with_member now validates session internally
                new_token = generate_token_with_member(
                    db=db,
                    user_id=user.id,
                    session_id=int(session_id),
                    device_platform=device_platform,
                    selected_member_id=member.id
                )
                response["token"] = new_token
                response["token_type"] = "Bearer"
        except HTTPException:
            # Re-raise HTTP exceptions (like invalid token, invalid session)
            # Don't fail member creation, but log the error
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"HTTP error generating token for first member (user {user.id}, member {member.id})", exc_info=True)
            # Continue without token - member is still created successfully
        except Exception as e:
            # Log error but don't fail the member creation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error generating token for first member (user {user.id}, member {member.id}): {str(e)}", exc_info=True)
            # Continue without token - member is still created successfully

    return response

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
        Member.user_id == user.id,
        Member.is_deleted == False
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

# Initiate member transfer
@router.post("/{member_id}/initiate-transfer", response_model=InitiateTransferResponse)
def initiate_member_transfer(
    member_id: int,
    req: InitiateTransferRequest,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Initiate transfer of a member to their own account.
    Sends OTP to member's phone number for verification.
    """
    from Login_module.OTP import otp_manager
    from Login_module.Utils.rate_limiter import get_client_ip
    from Login_module.Utils.datetime_utils import now_ist
    from datetime import timedelta
    import os
    
    # Validate member exists and belongs to user
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found or doesn't belong to you"
        )
    
    # Validate phone number matches member's phone
    normalized_phone = req.phone_number.strip().replace(" ", "").replace("-", "")
    if normalized_phone != member.mobile:
        raise HTTPException(
            status_code=400,
            detail="Phone number does not match member's registered phone number"
        )
    
    # Check if member is already transferred
    if member.transferred_from_user_id is not None:
        raise HTTPException(
            status_code=400,
            detail="Member has already been transferred to another account"
        )
    
    # Check if there's already a pending transfer for this member
    existing_transfer = db.query(MemberTransferLog).filter(
        MemberTransferLog.old_member_id == member_id,
        MemberTransferLog.transfer_status.in_(["PENDING_OTP", "OTP_VERIFIED"])
    ).first()
    
    if existing_transfer:
        raise HTTPException(
            status_code=400,
            detail="A transfer request is already pending for this member. Please complete or cancel the existing transfer."
        )
    
    # Check for active cart items with group_id (family/couple plans)
    from Cart_module.Cart_model import CartItem
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == user.id,
        CartItem.member_id == member_id
    ).all()
    
    if cart_items:
        # Check if any items are in a group with other members
        group_ids = {item.group_id for item in cart_items if item.group_id}
        for group_id in group_ids:
            group_items = db.query(CartItem).filter(
                CartItem.group_id == group_id,
                CartItem.user_id == user.id
            ).all()
            other_member_items = [gi for gi in group_items if gi.member_id != member_id]
            if other_member_items:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot transfer member with active items in a family/couple plan cart. Please complete the purchase or remove items from cart first."
                )
    
    # Generate OTP
    OTP_EXPIRY_SECONDS = int(os.getenv("OTP_EXPIRY_SECONDS", 120))
    otp_code = otp_manager.generate_otp()
    otp_expires_at = now_ist() + timedelta(seconds=OTP_EXPIRY_SECONDS)
    
    # Store OTP in Redis (reuse existing OTP system)
    country_code = "+91"  # Default, can be made configurable
    otp_manager.store_otp(country_code, normalized_phone, otp_code, expires_in=OTP_EXPIRY_SECONDS)
    
    # Create transfer log
    client_ip = get_client_ip(request)
    user_agent = request.headers.get("user-agent")
    
    transfer_log = create_transfer_log(
        db=db,
        old_user_id=user.id,
        old_member_id=member_id,
        member_phone=normalized_phone,
        initiated_by_user_id=user.id,
        ip_address=client_ip,
        user_agent=user_agent,
        otp_code=otp_code,
        otp_expires_at=otp_expires_at
    )
    
    return InitiateTransferResponse(
        status="success",
        message=f"OTP sent to {normalized_phone}. Please verify OTP to complete transfer.",
        transfer_log_id=transfer_log.id
    )


# Get list of members for user
@router.get("/list", response_model=MemberListResponse)
def get_member_list(
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    plan_type: Optional[str] = Query(None, description="Filter by plan type"),
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    members = get_members_by_user(db, user, category=category_id, plan_type=plan_type)
    
    # Import genetic test CRUD for checking participant status
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    
    data = []
    for m in members:
        # Read relation from database - it should be a string value
        relation_value = str(m.relation) if m.relation is not None else ""
        
        # Check if member has taken genetic test
        participant_info = get_participant_info(db, member_id=m.id)
        has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
        
        data.append({
            "member_id": m.id,
            "name": m.name,
            "relation": relation_value,  # Read relation as string from database
            "age": m.age,
            "gender": m.gender,
            "dob": m.dob.isoformat() if m.dob else None,
            "mobile": m.mobile,
            "profile_photo_url": m.profile_photo_url,
            "has_taken_genetic_test": has_taken_genetic_test
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
        Member.user_id == user.id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found"
        )
    
    # Prevent deletion of "Self" member (primary account holder)
    # Check using is_self_profile flag (more reliable than relation string)
    # This ensures user always has at least one member and prevents "no members" state
    if member.is_self_profile:
        raise HTTPException(
            status_code=422,
            detail="This is your primary profile (Self). Primary profile cannot be deleted."
        )
    
    # Prevent deletion of the last remaining member (guards against mis-labeled first member)
    total_members = db.query(Member).filter(Member.user_id == user.id, Member.is_deleted == False).count()
    if total_members <= 1:
        raise HTTPException(
            status_code=422,
            detail=f"Cannot delete '{member.name}' - At least one member must remain on the account. Add another member before deleting this one."
        )
    
    # Check if member is linked to any cart items
    cart_items = (
        db.query(CartItem, Product)
        .join(Product, CartItem.product_id == Product.ProductId)
        .filter(
            CartItem.member_id == member_id,
            CartItem.user_id == user.id,
            Product.is_deleted == False
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
    
    # Soft delete the member
    from Login_module.Utils.datetime_utils import now_ist
    member.is_deleted = True
    member.deleted_at = now_ist()
    
    # Create audit log for deletion BEFORE commit
    audit = MemberAuditLog(
        user_id=user.id,
        member_id=member_id,
        member_name=member_name,
        member_identifier=member_identifier,
        event_type="DELETED",
        old_data=old_data,
        new_data={"is_deleted": True, "deleted_at": member.deleted_at.isoformat() if member.deleted_at else None} if member.deleted_at else {"is_deleted": True},
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(audit)
    
    # Commit both operations in a single transaction
    db.commit()
    
    # Check if deleted member was currently selected
    # Get current selection from token using credentials dependency
    selected_member_id = None
    session_id = None
    device_platform = "unknown"
    
    try:
        # Use credentials dependency for reliable token extraction
        from fastapi.security import HTTPAuthorizationCredentials
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]
            payload = security.decode_access_token(token)
            selected_member_id = payload.get("selected_member_id")
            session_id = payload.get("session_id")
            device_platform = payload.get("device_platform", "unknown")
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Error extracting token info during member deletion: {str(e)}")
        # Continue without token update - member deletion still succeeds
    
    response = {
        "status": "success",
        "message": f"Member '{member_name}' deleted successfully."
    }
    
    # If deleted member was selected, switch to another member
    if selected_member_id and int(selected_member_id) == member_id:
        # Find another member to switch to
        remaining_member = db.query(Member).filter(
            Member.user_id == user.id,
            Member.id != member_id,
            Member.is_deleted == False
        ).order_by(Member.created_at.asc()).first()
        
        if remaining_member and session_id:
            # generate_token_with_member now validates session internally
            try:
                new_token = generate_token_with_member(
                    db=db,
                    user_id=user.id,
                    session_id=int(session_id),
                    device_platform=device_platform,
                    selected_member_id=remaining_member.id
                )
                response["token"] = new_token
                response["token_type"] = "Bearer"
                response["message"] = f"Member '{member_name}' deleted. Switched to '{remaining_member.name}' profile."
            except HTTPException:
                # Session invalid - log but don't fail deletion
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Session invalid when generating token after member deletion", exc_info=True)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error generating token after member deletion: {str(e)}", exc_info=True)
        elif not remaining_member and session_id:
            # No members left, clear selection
            # generate_token_with_member now validates session internally
            try:
                new_token = generate_token_with_member(
                    db=db,
                    user_id=user.id,
                    session_id=int(session_id),
                    device_platform=device_platform,
                    selected_member_id=None
                )
                response["token"] = new_token
                response["token_type"] = "Bearer"
            except HTTPException:
                # Session invalid - log but don't fail deletion
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Session invalid when generating token after member deletion (no members left)", exc_info=True)
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error generating token after member deletion (no members left): {str(e)}", exc_info=True)
    
    return response


# Switch profile endpoint
@router.post("/select/{member_id}")
def select_member_api(
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
    credentials: HTTPAuthorizationCredentials = Depends(security_scheme)
):
    """
    Switch to a different member profile.
    Returns new JWT token with updated selected_member_id.
    """
    # Validate member exists and belongs to user
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found or does not belong to you"
        )
    
    # Get current session info from token
    token = credentials.credentials
    try:
        payload = security.decode_access_token(token)
        session_id = payload.get("session_id")
        device_platform = payload.get("device_platform", "unknown")
        
        if not session_id:
            raise HTTPException(
                status_code=400,
                detail="Invalid session - session_id missing in token"
            )
        
        # generate_token_with_member now validates session internally, so we don't need to validate here
        # Generate new token with selected member
        new_token = generate_token_with_member(
            db=db,
            user_id=user.id,
            session_id=int(session_id),
            device_platform=device_platform,
            selected_member_id=member_id
        )
        
        return {
            "status": "success",
            "message": f"Switched to '{member.name}' profile.",
            "data": {
                "member_id": member.id,
                "name": member.name,
                "relation": str(member.relation),
                "age": member.age,
                "gender": member.gender,
                "dob": member.dob.isoformat() if member.dob else None,
                "mobile": member.mobile,
                "profile_photo_url": member.profile_photo_url
            },
            "token": new_token,
            "token_type": "Bearer"
        }
    except HTTPException:
        # Re-raise HTTP exceptions (invalid session, etc.)
        raise
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Unexpected error switching profile for user {user.id} to member {member_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Error switching profile: {str(e)}"
        )


# Get current selected member endpoint
@router.get("/current")
def get_current_member_api(
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user),
    current_member = Depends(get_current_member)
):
    """
    Get currently selected member profile.
    If no member is selected in token, returns the default member (first/self member).
    Returns member details if available, null only if user has no members.
    """
    # If no member selected in token, fall back to default member (first/self member)
    if not current_member:
        # Try to get self profile member first
        default_member = db.query(Member).filter(
            Member.user_id == current_user.id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        # If no self profile, get the first member (oldest by created_at)
        if not default_member:
            default_member = db.query(Member).filter(
                Member.user_id == current_user.id,
                Member.is_deleted == False
            ).order_by(Member.created_at.asc()).first()
        
        # If still no member found, return null
        if not default_member:
            return {
                "status": "success",
                "message": "No member profile found.",
                "data": None
            }
        
        # Use default member
        current_member = default_member
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=current_member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    return {
        "status": "success",
        "message": "Current member profile retrieved successfully.",
        "data": {
            "member_id": current_member.id,
            "name": current_member.name,
            "relation": str(current_member.relation),
            "age": current_member.age,
            "gender": current_member.gender,
            "dob": current_member.dob.isoformat() if current_member.dob else None,
            "mobile": current_member.mobile,
            "profile_photo_url": current_member.profile_photo_url,
            "has_taken_genetic_test": has_taken_genetic_test
        }
    }


# Allowed image file extensions
ALLOWED_PHOTO_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_PHOTO_FILE_SIZE = 5 * 1024 * 1024  # 5MB

# Content type mapping
CONTENT_TYPE_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp"
}


@router.post("/{member_id}/upload-photo")
async def upload_member_photo(
    member_id: int,
    file: UploadFile = File(...),
    request: Request = None,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Upload profile photo for a member to S3.
    Accepts image files (jpg, jpeg, png, gif, webp) up to 5MB.
    """
    # Validate member exists and belongs to user
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found or does not belong to you"
        )
    
    # Validate file extension
    file_ext = Path(file.filename).suffix.lower() if file.filename else ""
    if file_ext not in ALLOWED_PHOTO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file type. Allowed types: {', '.join(ALLOWED_PHOTO_EXTENSIONS)}"
        )
    
    # Read file content to check size
    file_content = await file.read()
    file_size = len(file_content)
    
    if file_size > MAX_PHOTO_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File size exceeds maximum allowed size of {MAX_PHOTO_FILE_SIZE // (1024 * 1024)}MB"
        )
    
    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File is empty"
        )
    
    # Generate unique filename: timestamp.ext
    timestamp = int(uuid.uuid4().hex[:8], 16)  # Use part of UUID as timestamp-like identifier
    filename = f"{timestamp}{file_ext}"
    
    # Determine content type
    content_type = file.content_type or CONTENT_TYPE_MAP.get(file_ext, "image/jpeg")
    
    # Delete old profile photo from S3 if exists
    if member.profile_photo_url:
        try:
            from .Member_s3_service import get_member_photo_s3_service
            s3_service = get_member_photo_s3_service()
            s3_service.delete_member_photo(member.profile_photo_url)
        except Exception as e:
            # Log but don't fail if old photo deletion fails
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete old member profile photo from S3: {str(e)}")
    
    # Upload to S3
    try:
        from .Member_s3_service import get_member_photo_s3_service
        s3_service = get_member_photo_s3_service()
        profile_photo_url = s3_service.upload_member_photo(
            member_id=member_id,
            filename=filename,
            file_content=file_content,
            content_type=content_type
        )
    except ValueError as e:
        # S3 not configured
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"S3 configuration error: {str(e)}"
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error uploading member photo to S3: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload photo to S3: {str(e)}"
        )
    
    # Update member profile with S3 URL
    member.profile_photo_url = profile_photo_url
    db.commit()
    db.refresh(member)
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    return {
        "status": "success",
        "message": "Member profile photo uploaded successfully.",
        "data": {
            "member_id": member.id,
            "name": member.name,
            "relation": str(member.relation),
            "age": member.age,
            "gender": member.gender,
            "dob": member.dob.isoformat() if member.dob else None,
            "mobile": member.mobile,
            "profile_photo_url": member.profile_photo_url,
            "has_taken_genetic_test": has_taken_genetic_test
        }
    }


@router.delete("/{member_id}/delete-photo")
def delete_member_photo(
    member_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user = Depends(get_current_user)
):
    """
    Delete profile photo for a member from S3.
    """
    # Validate member exists and belongs to user
    member = db.query(Member).filter(
        Member.id == member_id,
        Member.user_id == user.id,
        Member.is_deleted == False
    ).first()
    
    if not member:
        raise HTTPException(
            status_code=404,
            detail="Member not found or does not belong to you"
        )
    
    if not member.profile_photo_url:
        raise HTTPException(
            status_code=404,
            detail="Member does not have a profile photo"
        )
    
    # Delete file from S3
    try:
        from .Member_s3_service import get_member_photo_s3_service
        s3_service = get_member_photo_s3_service()
        s3_service.delete_member_photo(member.profile_photo_url)
    except Exception as e:
        # Log but don't fail if S3 deletion fails (photo might already be deleted)
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(f"Failed to delete member profile photo from S3: {str(e)}")
    
    # Remove photo URL from database
    member.profile_photo_url = None
    db.commit()
    db.refresh(member)
    
    # Check if member has taken genetic test
    from GeneticTest_module.GeneticTest_crud import get_participant_info
    participant_info = get_participant_info(db, member_id=member.id)
    has_taken_genetic_test = participant_info.get("has_taken_genetic_test", False) if participant_info else False
    
    return {
        "status": "success",
        "message": "Member profile photo deleted successfully.",
        "data": {
            "member_id": member.id,
            "name": member.name,
            "relation": str(member.relation),
            "age": member.age,
            "gender": member.gender,
            "dob": member.dob.isoformat() if member.dob else None,
            "mobile": member.mobile,
            "profile_photo_url": None,
            "has_taken_genetic_test": has_taken_genetic_test
        }
    }
