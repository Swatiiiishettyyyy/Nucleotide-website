from .Member_model import Member
from .Member_audit_model import MemberAuditLog
from sqlalchemy.orm import Session
from sqlalchemy import or_, text
from fastapi import HTTPException
from typing import Any, Dict, Optional, Union

from Product_module.category_service import resolve_category

_VALID_PLAN_TYPES = {"single", "couple", "family"}


def _normalize_relation(relation: Optional[str]) -> str:
    """Convert incoming relation string to normalized string. Accepts any string value.
    No default value - relation must be provided by user.
    Stores exactly what user enters (trimmed), never stores empty string or whitespace.
    """
    # Ensure relation is provided
    if relation is None:
        raise ValueError("Relation is required and cannot be empty")
    
    # Convert to string (in case it's not already)
    relation_str = str(relation)
    
    # Trim the relation string
    relation_trimmed = relation_str.strip()
    
    # Ensure it's not empty after trimming (catches empty strings and whitespace-only strings)
    if not relation_trimmed:
        raise ValueError("Relation cannot be empty or whitespace only")
    
    # Return the trimmed value - store exactly what user enters
    # No enum restriction - user can enter any relation string
    return relation_trimmed


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
        Member.is_deleted == False
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
    Save or update member (create if member_id=0, update if member_id>0).
    For new members: category_id and plan_type are required.
    For existing members: category_id and plan_type are ignored (preserved from existing member).
    Validates that member is not already in a conflicting plan type.
    Prevents editing if member is associated with cart items.
    """
    plan_type_normalized = _normalize_plan_type(plan_type)
    family_status: Optional[Dict[str, Any]] = None

    category_obj = resolve_category(db, category_id)
    category_name = category_obj.name
    category_filter = or_(
        Member.associated_category_id == category_obj.id,
        Member.associated_category == category_name
    )

    # Get relation value from request - it's already validated and trimmed by schema validator
    # The validator ensures it's not empty and trims it, so we can use it directly
    # Store exactly what user enters (already trimmed by validator)
    
    # Get relation value directly from request object
    # The Pydantic validator has already validated and trimmed it
    if not hasattr(req, 'relation'):
        raise ValueError("Relation field is missing from request object")
    
    # Get the relation value - validator should have already validated and trimmed it
    relation_value = req.relation
    
    if relation_value is None:
        raise ValueError("Relation is required and cannot be None")
    
    # Convert to string and ensure it's trimmed (validator should have done this)
    relation_to_store = str(relation_value).strip()
    
    # CRITICAL: Final safety check - ensure relation is not empty
    # This should never happen if validator is working, but we check anyway
    if not relation_to_store:
        # Get additional debug info
        debug_info = f"req.relation={repr(req.relation)}, type={type(req.relation)}"
        try:
            if hasattr(req, 'dict'):
                debug_info += f", dict={req.dict()}"
        except:
            pass
        
        raise HTTPException(
            status_code=422,
            detail=(
                f"Relation cannot be empty. The validator should have prevented this. "
                f"Debug info: {debug_info}. "
                f"Please ensure you are sending a non-empty relation value in your request."
            )
        )
    
    # Store the relation exactly as entered (trimmed) - no enum restrictions, accepts any string value

    # Check for duplicate member in same category
    if req.member_id == 0:  # New member
        # Check if member with same name AND relation already exists in same category
        # This allows same name with different relations (e.g., "John" as self and "John" as child)
        existing = db.query(Member).filter(
            Member.user_id == user.id,
            Member.name == req.name,
            Member.relation == relation_to_store,
            category_filter,
            Member.is_deleted == False
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Member '{req.name}' with relation '{req.relation}' already exists "
                    f"in the '{category_name}' category."
                )
            )
        
        # If adding to family plan, check if member is already in personal/couple plan
        if plan_type_normalized == "family":
            conflicting_member = db.query(Member).filter(
                Member.user_id == user.id,
                Member.name == req.name,
                category_filter,
                Member.associated_plan_type.in_(["single", "couple"]),
                Member.is_deleted == False
            ).first()
            
            if conflicting_member:
                plan = conflicting_member.associated_plan_type or "another plan"
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Member '{req.name}' is already associated with your '{plan}' plan "
                        f"in the '{category_name}' category. Remove them from that plan before adding to family."
                    )
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
                Member.associated_plan_type == "family",
                Member.is_deleted == False
            ).first()
            
            if conflicting_member:
                plan = conflicting_member.associated_plan_type or "family"
                raise HTTPException(
                    status_code=422,
                    detail=(
                        f"Member '{req.name}' is already associated with your '{plan}' plan "
                        f"in the '{category_name}' category. Remove them before assigning to another plan."
                    )
                )
    
    old_data = None
    
    # If editing existing member, check if member is in cart
    if req.member_id != 0:
        from Cart_module.Cart_model import CartItem
        from Product_module.Product_model import Product
        
        # Check if member is linked to any cart items
        cart_items = (
            db.query(CartItem, Product)
            .join(Product, CartItem.product_id == Product.ProductId)
            .filter(
                CartItem.member_id == req.member_id,
                CartItem.user_id == user.id,
                Product.is_deleted == False
            )
            .all()
        )
        
        if cart_items:
            # Get product names and plan types for better error message
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
                detail=f"Member '{req.name}' is associated with {len(cart_items)} cart item(s) for product(s): {conflict_details}. Please remove these items from your cart before editing the member."
            )
    
    if req.member_id == 0:
        # Create new member
        # CRITICAL: Ensure relation_to_store is not empty before creating member
        if not relation_to_store or len(relation_to_store.strip()) == 0:
            raise ValueError(
                f"Cannot create member with empty relation. "
                f"relation_to_store: '{relation_to_store}', "
                f"req.relation: '{req.relation}'"
            )
        
        # Check if this is the first member for the user
        existing_member_count = db.query(Member).filter(
            Member.user_id == user.id,
            Member.is_deleted == False
        ).count()
        is_first_member = existing_member_count == 0
        
        # Determine if this should be marked as self profile
        # Set is_self_profile = True if:
        # 1. This is the first member for the user, AND
        # 2. Relation is "Self" (case-insensitive check)
        relation_lower = relation_to_store.strip().lower()
        should_mark_as_self = is_first_member and relation_lower in ["self", "user", "account holder", "account_holder"]
        
        # For first member with "Self" relation, auto-populate mobile from user's login mobile
        # Extract last 10 digits from user.mobile to match member schema validation (exactly 10 digits)
        member_mobile = req.mobile
        if should_mark_as_self and user.mobile:
            # Extract digits only from user.mobile
            user_mobile_digits = ''.join(filter(str.isdigit, str(user.mobile)))
            # Take last 10 digits (handles cases where user.mobile might have country code)
            if len(user_mobile_digits) >= 10:
                member_mobile = user_mobile_digits[-10:]
            elif len(user_mobile_digits) > 0:
                # If less than 10 digits, use as-is (fallback - should not happen in normal flow)
                member_mobile = user_mobile_digits
        
        # Create member with the relation value
        # IMPORTANT: relation_to_store has been validated and is guaranteed to be non-empty
        member = Member(
            user_id=user.id,
            name=req.name,
            relation=relation_to_store,  # Store the validated and trimmed relation value
            age=req.age,
            gender=req.gender,
            dob=req.dob,
            mobile=member_mobile,
            email=getattr(req, 'email', None),  # Optional email field
            associated_category=category_name,
            associated_category_id=category_obj.id,
            associated_plan_type=plan_type_normalized,
            is_self_profile=should_mark_as_self  # Mark as self profile if first member with "Self" relation
        )
        db.add(member)
        db.flush()  # Flush to get the ID without committing
        
        # CRITICAL: Verify the relation was set correctly BEFORE commit
        if not member.relation or str(member.relation).strip() == "":
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=(
                    f"CRITICAL ERROR: Relation was set to empty value in member object! "
                    f"Expected: '{relation_to_store}', Got: '{member.relation}'. "
                    f"This should never happen. Please check the database schema and constraints."
                )
            )
        
        db.commit()
        db.refresh(member)
        
        # WORKAROUND: If relation is empty after commit, explicitly update it
        # This handles cases where database triggers or defaults might be interfering
        if not member.relation or str(member.relation).strip() == "":
            # Check the database column type to understand the issue
            column_info = None
            is_enum = False
            try:
                # Try to get column information (MySQL/PostgreSQL)
                if hasattr(db.bind, 'url') and 'mysql' in str(db.bind.url):
                    column_info = db.execute(
                        text("""
                            SELECT COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'members' 
                            AND COLUMN_NAME = 'relation'
                        """)
                    ).fetchone()
                    if column_info and 'enum' in str(column_info[0]).lower():
                        is_enum = True
                        # Try to fix it by altering the column to VARCHAR
                        try:
                            db.execute(text("ALTER TABLE members MODIFY COLUMN relation VARCHAR(50) NOT NULL"))
                            db.commit()
                        except Exception as alter_error:
                            pass  # If alter fails, continue with update attempt
                elif hasattr(db.bind, 'url') and 'postgresql' in str(db.bind.url):
                    column_info = db.execute(
                        text("""
                            SELECT data_type, column_default, is_nullable 
                            FROM information_schema.columns 
                            WHERE table_name = 'members' 
                            AND column_name = 'relation'
                        """)
                    ).fetchone()
                    if column_info and 'enum' in str(column_info[0]).lower():
                        is_enum = True
                        # Try to fix it by altering the column to VARCHAR
                        try:
                            db.execute(text("ALTER TABLE members ALTER COLUMN relation TYPE VARCHAR(50)"))
                            db.execute(text("ALTER TABLE members ALTER COLUMN relation SET NOT NULL"))
                            db.commit()
                        except Exception as alter_error:
                            pass  # If alter fails, continue with update attempt
            except Exception as e:
                pass  # Ignore errors in diagnostic query
            
            # Try direct UPDATE with the value
            db.execute(
                text("UPDATE members SET relation = :relation WHERE id = :id"),
                {"relation": relation_to_store, "id": member.id}
            )
            db.commit()
            
            # Verify by querying directly from database
            db_result = db.execute(
                text("SELECT relation FROM members WHERE id = :id"),
                {"id": member.id}
            ).fetchone()
            
            # Refresh the member object
            db.refresh(member)
            
            # Check both the direct query and the refreshed object
            db_value = db_result[0] if db_result and db_result[0] else None
            obj_value = member.relation if member.relation else None
            
            if (not db_value or str(db_value).strip() == "") and (not obj_value or str(obj_value).strip() == ""):
                # Get more diagnostic info
                db_type = "Unknown"
                if hasattr(db.bind, 'url'):
                    db_type = str(db.bind.url).split('://')[0] if '://' in str(db.bind.url) else str(db.bind.url)
                
                error_msg = (
                    f"CRITICAL ERROR: Unable to store relation value in database!\n"
                    f"Expected: '{relation_to_store}'\n"
                    f"Database value: '{db_value}'\n"
                    f"Object value: '{obj_value}'\n"
                    f"Database type: {db_type}\n"
                )
                
                if column_info:
                    error_msg += f"Column definition: {column_info}\n"
                    if is_enum:
                        error_msg += f"WARNING: Column is defined as ENUM type!\n"
                
                error_msg += (
                    f"\nThis indicates a database-level issue. The 'relation' column may be defined as ENUM.\n\n"
                    f"SOLUTION: Run this SQL to fix the column:\n"
                )
                
                if 'mysql' in db_type.lower():
                    error_msg += f"ALTER TABLE members MODIFY COLUMN relation VARCHAR(50) NOT NULL;\n"
                elif 'postgresql' in db_type.lower():
                    error_msg += (
                        f"ALTER TABLE members ALTER COLUMN relation TYPE VARCHAR(50);\n"
                        f"ALTER TABLE members ALTER COLUMN relation SET NOT NULL;\n"
                    )
                else:
                    error_msg += f"ALTER TABLE members ALTER COLUMN relation VARCHAR(50) NOT NULL;\n"
                
                raise HTTPException(status_code=500, detail=error_msg)
        
        # If this is the first member with "Self" relation (is_self_profile=True),
        # update user table fields from member details
        if should_mark_as_self:
            user.name = req.name
            if getattr(req, 'email', None):
                user.email = req.email
            # Update profile_photo_url if provided in member (though it's not in MemberRequest schema currently)
            # This allows future extensibility if profile_photo_url is added to the request
            if hasattr(member, 'profile_photo_url') and member.profile_photo_url:
                user.profile_photo_url = member.profile_photo_url
            db.flush()  # Flush user updates before committing audit log
        
        # Audit log for creation
        new_data = {
            "member_id": member.id,
            "name": req.name,
            "relation": req.relation,
            "age": req.age,
            "gender": req.gender,
            "dob": req.dob.isoformat() if req.dob else None,
            "mobile": req.mobile,
            "email": getattr(req, 'email', None),
            "category": category_name,
            "plan_type": plan_type_normalized
        }
        audit = MemberAuditLog(
            user_id=user.id,
            member_id=member.id,
            member_name=req.name,
            member_identifier=f"{req.name} ({req.mobile})",
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
            "member_id": member.id,
            "name": member.name,
            "relation": str(member.relation),  # Now a string, no need for .value check
            "age": member.age,
            "gender": member.gender,
            "dob": member.dob.isoformat() if member.dob else None,
            "mobile": member.mobile,
            "email": member.email,
            "category": member.associated_category,
            "plan_type": member.associated_plan_type
        }
        
        # Update member fields (category and plan_type are preserved from existing member)
        # Ensure relation_to_store is not empty before updating
        if not relation_to_store or len(relation_to_store.strip()) == 0:
            raise ValueError(f"Cannot update member with empty relation. Received: '{req.relation}'")
        
        # Prevent changing is_self_profile from True to False (primary profile protection)
        # Once a member is marked as self profile, it should remain so
        # is_self_profile is not updated during edit - it remains as set during creation
        
        member.name = req.name
        member.relation = relation_to_store  # Store the validated and trimmed relation value
        member.age = req.age
        member.gender = req.gender
        member.dob = req.dob
        member.mobile = req.mobile
        member.email = getattr(req, 'email', None)  # Optional email field
        # Note: category_id and plan_type are not updated on edit to maintain data integrity
        # Note: is_self_profile is not updated on edit to protect primary profile
        
        # Flush changes to database before commit to ensure they're tracked
        db.flush()
        db.commit()
        db.refresh(member)  # Refresh to get latest values from database
        
        # WORKAROUND: If relation is empty after commit, explicitly update it
        # This handles cases where database triggers or defaults might be interfering
        if not member.relation or str(member.relation).strip() == "":
            # Check the database column type to understand the issue
            column_info = None
            is_enum = False
            try:
                # Try to get column information (MySQL/PostgreSQL)
                if hasattr(db.bind, 'url') and 'mysql' in str(db.bind.url):
                    column_info = db.execute(
                        text("""
                            SELECT COLUMN_TYPE, COLUMN_DEFAULT, IS_NULLABLE 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'members' 
                            AND COLUMN_NAME = 'relation'
                        """)
                    ).fetchone()
                    if column_info and 'enum' in str(column_info[0]).lower():
                        is_enum = True
                        # Try to fix it by altering the column to VARCHAR
                        try:
                            db.execute(text("ALTER TABLE members MODIFY COLUMN relation VARCHAR(50) NOT NULL"))
                            db.commit()
                        except Exception as alter_error:
                            pass  # If alter fails, continue with update attempt
                elif hasattr(db.bind, 'url') and 'postgresql' in str(db.bind.url):
                    column_info = db.execute(
                        text("""
                            SELECT data_type, column_default, is_nullable 
                            FROM information_schema.columns 
                            WHERE table_name = 'members' 
                            AND column_name = 'relation'
                        """)
                    ).fetchone()
                    if column_info and 'enum' in str(column_info[0]).lower():
                        is_enum = True
                        # Try to fix it by altering the column to VARCHAR
                        try:
                            db.execute(text("ALTER TABLE members ALTER COLUMN relation TYPE VARCHAR(50)"))
                            db.execute(text("ALTER TABLE members ALTER COLUMN relation SET NOT NULL"))
                            db.commit()
                        except Exception as alter_error:
                            pass  # If alter fails, continue with update attempt
            except Exception as e:
                pass  # Ignore errors in diagnostic query
            
            # Try direct UPDATE with the value
            db.execute(
                text("UPDATE members SET relation = :relation WHERE id = :id"),
                {"relation": relation_to_store, "id": member.id}
            )
            db.commit()
            
            # Verify by querying directly from database
            db_result = db.execute(
                text("SELECT relation FROM members WHERE id = :id"),
                {"id": member.id}
            ).fetchone()
            
            # Refresh the member object
            db.refresh(member)
            
            # Check both the direct query and the refreshed object
            db_value = db_result[0] if db_result and db_result[0] else None
            obj_value = member.relation if member.relation else None
            
            if (not db_value or str(db_value).strip() == "") and (not obj_value or str(obj_value).strip() == ""):
                # Get more diagnostic info
                db_type = "Unknown"
                if hasattr(db.bind, 'url'):
                    db_type = str(db.bind.url).split('://')[0] if '://' in str(db.bind.url) else str(db.bind.url)
                
                error_msg = (
                    f"CRITICAL ERROR: Unable to update relation value in database!\n"
                    f"Expected: '{relation_to_store}'\n"
                    f"Database value: '{db_value}'\n"
                    f"Object value: '{obj_value}'\n"
                    f"Database type: {db_type}\n"
                )
                
                if column_info:
                    error_msg += f"Column definition: {column_info}\n"
                    if is_enum:
                        error_msg += f"WARNING: Column is defined as ENUM type!\n"
                
                error_msg += (
                    f"\nThis indicates a database-level issue. The 'relation' column may be defined as ENUM.\n\n"
                    f"SOLUTION: Run this SQL to fix the column:\n"
                )
                
                if 'mysql' in db_type.lower():
                    error_msg += f"ALTER TABLE members MODIFY COLUMN relation VARCHAR(50) NOT NULL;\n"
                elif 'postgresql' in db_type.lower():
                    error_msg += (
                        f"ALTER TABLE members ALTER COLUMN relation TYPE VARCHAR(50);\n"
                        f"ALTER TABLE members ALTER COLUMN relation SET NOT NULL;\n"
                    )
                else:
                    error_msg += f"ALTER TABLE members ALTER COLUMN relation VARCHAR(50) NOT NULL;\n"
                
                raise HTTPException(status_code=500, detail=error_msg)
        
        # Audit log for update - use actual stored values from database
        # Refresh member to ensure we have the latest values after any workarounds
        db.refresh(member)
        
        new_data = {
            "member_id": member.id,
            "name": member.name,  # Use actual stored value
            "relation": str(member.relation),  # Use actual stored value (after any workarounds)
            "age": member.age,  # Use actual stored value
            "gender": member.gender,  # Use actual stored value
            "dob": member.dob.isoformat() if member.dob else None,  # Use actual stored value
            "mobile": member.mobile,  # Use actual stored value
            "category": member.associated_category,
            "plan_type": member.associated_plan_type
        }
        
        audit = MemberAuditLog(
            user_id=user.id,
            member_id=member.id,
            member_name=member.name,  # Use actual stored value
            member_identifier=f"{member.name} ({member.mobile})",  # Use actual stored values
            event_type="UPDATED",  # Clear status indicating this is an edit
            old_data=old_data,  # Previous values before update
            new_data=new_data,  # New values after update - shows clear changes
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
    query = db.query(Member).filter(
        Member.user_id == user.id,
        Member.is_deleted == False
    )
    
    if category:
        if isinstance(category, int):
            query = query.filter(Member.associated_category_id == category)
        else:
            query = query.filter(Member.associated_category == category)
    if plan_type:
        query = query.filter(Member.associated_plan_type == plan_type)
    
    return query.all()