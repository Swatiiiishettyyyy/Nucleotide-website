from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from typing import Optional, List
import uuid
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

from database import SessionLocal
from .Cart_model import CartItem, Cart
from Product_module.Product_model import Product, PlanType
from Address_module.Address_model import Address
from Member_module.Member_model import Member
from Login_module.User.user_model import User
from .Cart_schema import CartAdd, CartUpdate, ApplyCouponRequest, CouponCreate
from deps import get_db
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.Utils.datetime_utils import to_ist_isoformat
from .Cart_audit_crud import create_audit_log
from .coupon_service import (
    apply_coupon_to_cart,
    get_applied_coupon,
    remove_coupon_from_cart,
    validate_and_calculate_discount,
    is_coupon_usage_limit_reached,
    get_coupon_usage_count
)
from .Coupon_model import Coupon, CouponType, CouponStatus

router = APIRouter(prefix="/cart", tags=["Cart"])


def get_client_info(request: Request):
    """Extract client IP and user agent from request"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


def get_or_create_user_cart(db: Session, user_id: int) -> Cart:
    """
    Get or create active cart for user.
    Ensures one active cart per user by deactivating any other active carts.
    """
    # Get all active carts for this user
    active_carts = db.query(Cart).filter(
        Cart.user_id == user_id,
        Cart.is_active == True
    ).all()
    
    if len(active_carts) > 1:
        # Multiple active carts - deactivate all except the first one
        for c in active_carts[1:]:
            c.is_active = False
        cart = active_carts[0]
        db.flush()
        logger.warning(f"Found multiple active carts for user {user_id}. Deactivated {len(active_carts) - 1} cart(s).")
    elif len(active_carts) == 1:
        # One active cart exists
        cart = active_carts[0]
    else:
        # No active cart exists - create new one
        cart = Cart(
            user_id=user_id,
            is_active=True
        )
        db.add(cart)
        db.flush()
        db.refresh(cart)
        logger.info(f"Created new cart {cart.id} for user {user_id}")
    
    return cart


@router.post("/add")
def add_to_cart(
    item: CartAdd,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Add item to cart (requires authentication).
    For couple products, creates 2 rows in cart_items table.
    For family products, creates 3-4 rows (3 mandatory + 1 optional).
    Every cart item must be linked with member_id and address_id.
    Addresses can be the same for all members or different for each member.
    """
    try:
        # Check if product exists
        product = db.query(Product).filter(Product.ProductId == item.product_id, Product.is_deleted == False).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        category_name = product.category.name if product.category else "this category"
        
        # Extract member_ids and address_ids from member_address_map
        member_ids = [mapping.member_id for mapping in item.member_address_map]
        address_ids = [mapping.address_id for mapping in item.member_address_map]
        num_members = len(member_ids)
        num_addresses = len(set(address_ids))  # Unique address count
        
        # Validate all addresses exist and belong to user
        unique_address_ids = list(set(address_ids))
        addresses = db.query(Address).filter(
            Address.id.in_(unique_address_ids),
            Address.user_id == current_user.id,
            Address.is_deleted == False
        ).all()
        
        if len(addresses) != len(unique_address_ids):
            found_ids = {addr.id for addr in addresses}
            missing_ids = [aid for aid in unique_address_ids if aid not in found_ids]
            raise HTTPException(
                status_code=422,
                detail=f"Address(es) {missing_ids} not found or do not belong to you."
            )
        
        # Validate members exist and belong to user
        members = db.query(Member).filter(
            Member.id.in_(member_ids),
            Member.user_id == current_user.id
        ).all()
        
        if len(members) != num_members:
            raise HTTPException(
                status_code=422,
                detail="One or more member IDs not found for this user."
            )
        
        # Check if any of these members are already in cart for another product
        # within the same category (ignore address differences)
        conflicting_members = (
            db.query(CartItem, Product, Member)
            .join(Product, CartItem.product_id == Product.ProductId)
            .join(Member, CartItem.member_id == Member.id)
            .filter(
                Product.is_deleted == False,
                Member.is_deleted == False
            )
            .filter(
                CartItem.user_id == current_user.id,
                CartItem.member_id.in_(member_ids),
                Product.category_id == product.category_id,
                CartItem.product_id != item.product_id
            )
            .all()
        )
        
        if conflicting_members:
            conflicts = []
            for cart_item, existing_product, member_obj in conflicting_members:
                conflicts.append({
                    "member_id": member_obj.id,
                    "member_name": member_obj.name,
                    "existing_product_id": existing_product.ProductId,
                    "existing_product_name": existing_product.Name,
                    "existing_plan_type": existing_product.plan_type.value if hasattr(existing_product.plan_type, "value") else str(existing_product.plan_type),
                })
            raise HTTPException(
                status_code=422,
                detail={
                    "message": (
                        f"Members already associated with another product in '{category_name}' category."
                    ),
                    "conflicts": conflicts
                }
            )
        
        # Check if same product with same members already exists in cart
        # (ignore address differences - addresses can be changed)
        # Exclude deleted items (is_deleted = True)
        existing_cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == item.product_id,
            CartItem.is_deleted == False  # Exclude deleted/cleared items
        ).all()
        
        if existing_cart_items:
            # Group by group_id to check member sets
            from collections import defaultdict
            grouped_existing = defaultdict(list)
            for ci in existing_cart_items:
                group_key = ci.group_id or f"single_{ci.id}"
                grouped_existing[group_key].append(ci)
            
            requested_member_ids = set(member_ids)
            for group_key, group_items in grouped_existing.items():
                existing_member_ids = set(ci.member_id for ci in group_items)
                if existing_member_ids == requested_member_ids:
                    raise HTTPException(
                        status_code=422,
                        detail="This product with the same members is already in your cart."
                    )
        
        # Validate member count matches product plan type
        if product.plan_type == PlanType.SINGLE and num_members != 1:
            raise HTTPException(
                status_code=422,
                detail=f"Single plan requires exactly 1 member, got {num_members}."
            )
        elif product.plan_type == PlanType.COUPLE and num_members != 2:
            raise HTTPException(
                status_code=422,
                detail=f"Couple plan requires exactly 2 members, got {num_members}."
            )
        elif product.plan_type == PlanType.FAMILY:
            if num_members < 3 or num_members > 4:
                raise HTTPException(
                    status_code=422,
                    detail=f"Family plan requires 3-4 members (3 mandatory + 1 optional), got {num_members}."
                )
        
        ip, user_agent = get_client_info(request)
        
        # Generate unique group_id using full UUID for better uniqueness
        group_id = f"{current_user.id}_{product.ProductId}_{uuid.uuid4().hex}"
        
        # Get or create user's active cart
        cart = get_or_create_user_cart(db, current_user.id)
        cart_id = cart.id
        
        # Build member_address_map from request (already validated)
        member_address_map = {
            mapping.member_id: mapping.address_id 
            for mapping in item.member_address_map
        }
        
        # Create a lookup for members by ID
        members_by_id = {member.id: member for member in members}
        
        created_cart_items = []
        
        try:
            # Create cart items: one row per member with their assigned address
            # Process in the order specified in member_address_map
            for mapping in item.member_address_map:
                member = members_by_id[mapping.member_id]
                cart_item = CartItem(
                    user_id=current_user.id,
                    cart_id=cart_id,  # Use cart.id from cart table
                    product_id=item.product_id,
                    address_id=mapping.address_id,
                    member_id=mapping.member_id,
                    quantity=item.quantity,
                    group_id=group_id  # Link all items for this product purchase
                )
                db.add(cart_item)
                created_cart_items.append(cart_item)
            
            # Update cart's last_activity_at
            from Login_module.Utils.datetime_utils import now_ist
            cart.last_activity_at = now_ist()
            
            # Flush to get IDs for all items
            db.flush()
            
            # Commit all items together (transaction safety)
            db.commit()
            
            # Refresh all created items to get database values
            for cart_item in created_cart_items:
                db.refresh(cart_item)
                logger.info(f"CartItem {cart_item.id} created with cart_id: {cart_item.cart_id}")
        except Exception as e:
            # Rollback on any error to prevent partial data
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error adding items to cart: {str(e)}"
            )
        
        # Safety check: ensure cart items were created
        if not created_cart_items:
            raise HTTPException(
                status_code=500,
                detail="No cart items were created. This should not happen."
            )
        
        # Build member-address mapping for response (preserve order from request)
        member_address_response = [
            {"member_id": mapping.member_id, "address_id": mapping.address_id}
            for mapping in item.member_address_map
        ]
        
        # Extract unique address IDs for response
        unique_address_ids = list(set(address_ids))
        
        # Audit log
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="ADD",
            entity_type="CART_ITEM",
            entity_id=created_cart_items[0].id,
            cart_id=cart_id,  # Use proper cart.id
            details={
                "product_id": product.ProductId,
                "plan_type": product.plan_type.value,
                "quantity": item.quantity,
                "member_ids": member_ids,
                "address_ids": unique_address_ids,
                "member_address_map": member_address_map,
                "cart_items_created": len(created_cart_items),
                "group_id": group_id,
                "cart_id": cart_id
            },
            ip_address=ip,
            user_agent=user_agent,
            username=current_user.name or current_user.mobile,  # Pass directly to avoid lookup
            correlation_id=correlation_id
        )
        
        return {
            "status": "success",
            "message": "Product added to cart successfully.",
            "data": {
                "cart_item_ids": [ci.id for ci in created_cart_items],
                "cart_id": cart_id,  # Proper cart.id from cart table
                "product_id": product.ProductId,
                "address_ids": unique_address_ids,
                "member_ids": member_ids,
                "member_address_map": member_address_response,
                "quantity": item.quantity,
                "plan_type": product.plan_type.value,
                "price": product.Price,
                "special_price": product.SpecialPrice,
                "total_amount": item.quantity * product.SpecialPrice,
                "items_created": len(created_cart_items)  # 1 for single, 2 for couple, 3-4 for family
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error adding to cart: {str(e)}")


@router.put("/update/{cart_item_id}")
def update_cart_item(
    cart_item_id: int,
    update: CartUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update cart item quantity (requires authentication).
    For couple/family products, updates all items in the group.
    """
    
    cart_item = db.query(CartItem).filter(
        CartItem.id == cart_item_id,
        CartItem.user_id == current_user.id,
        CartItem.is_deleted == False
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    old_quantity = cart_item.quantity
    group_id = cart_item.group_id
    cart_id = cart_item.cart_id
    
    try:
        # If item has a group_id, update all items in the group (for couple/family products)
        if group_id:
            # Update all items in the group (exclude deleted items)
            group_items = db.query(CartItem).filter(
                CartItem.group_id == group_id,
                CartItem.user_id == current_user.id,
                CartItem.is_deleted == False
            ).all()
            
            for item in group_items:
                item.quantity = update.quantity
            updated_count = len(group_items)
        else:
            # Single item, update just this one
            cart_item.quantity = update.quantity
            updated_count = 1
        
        # Update cart's last_activity_at
        if cart_id:
            cart = db.query(Cart).filter(
                Cart.id == cart_id,
                Cart.user_id == current_user.id  # Security: verify cart belongs to user
            ).first()
            if cart:
                from Login_module.Utils.datetime_utils import now_ist
                cart.last_activity_at = now_ist()
        
        db.commit()
        db.refresh(cart_item)

        product = cart_item.product
        
        # Audit log
        ip, user_agent = get_client_info(request)
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="UPDATE",
            entity_type="CART_ITEM",
            entity_id=cart_item.id,
            cart_id=cart_id,  # Use proper cart.id
            details={
                "product_id": product.ProductId,
                "old_quantity": old_quantity,
                "new_quantity": update.quantity,
                "group_id": group_id,
                "items_updated": updated_count,
                "cart_id": cart_id
            },
            ip_address=ip,
            user_agent=user_agent,
            username=current_user.name or current_user.mobile,
            correlation_id=correlation_id
        )
        
        return {
            "status": "success",
            "message": f"Cart item(s) updated successfully. {updated_count} item(s) updated.",
            "data": {
                "cart_item_id": cart_item.id,
                "product_id": product.ProductId,
                "quantity": update.quantity,
                "price": product.Price,
                "special_price": product.SpecialPrice,
                "total_amount": update.quantity * product.SpecialPrice,
                "items_updated": updated_count
            }
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error updating cart item: {str(e)}"
        )


@router.delete("/delete/{cart_item_id}")
def delete_cart_item(
    cart_item_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Delete cart item (requires authentication).
    For couple/family products, deletes all items in the group (all members).
    """
    
    cart_item = db.query(CartItem).filter(
        CartItem.id == cart_item_id,
        CartItem.user_id == current_user.id,
        CartItem.is_deleted == False  # Only allow deleting non-deleted items
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found or already deleted")

    product_id = cart_item.product_id
    quantity = cart_item.quantity
    group_id = cart_item.group_id
    cart_id = cart_item.cart_id
    
    # If item has a group_id, soft delete all items in the group (for couple/family products)
    if group_id:
        # Soft delete all items in the group (exclude already deleted items)
        deleted_items = db.query(CartItem).filter(
            CartItem.group_id == group_id,
            CartItem.user_id == current_user.id,
            CartItem.is_deleted == False
        ).all()
        
        deleted_count = len(deleted_items)
        for item in deleted_items:
            item.is_deleted = True
    else:
        # Single item, soft delete just this one
        cart_item.is_deleted = True
        deleted_count = 1
    
    # Update cart's last_activity_at
    if cart_id:
        cart = db.query(Cart).filter(
            Cart.id == cart_id,
            Cart.user_id == current_user.id  # Security: verify cart belongs to user
        ).first()
        if cart:
            from Login_module.Utils.datetime_utils import now_ist
            cart.last_activity_at = now_ist()
    
    db.commit()

    # Audit log
    ip, user_agent = get_client_info(request)
    correlation_id = str(uuid.uuid4())
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        entity_type="CART_ITEM",
        entity_id=cart_item_id,
        cart_id=cart_id,  # Use proper cart.id
        details={
            "product_id": product_id,
            "quantity": quantity,
            "group_id": group_id,
            "items_deleted": deleted_count,
            "cart_id": cart_id
        },
        ip_address=ip,
        user_agent=user_agent,
        username=current_user.name or current_user.mobile,
        correlation_id=correlation_id
    )

    return {
        "status": "success",
        "message": f"Cart item(s) deleted successfully. {deleted_count} item(s) removed."
    }


@router.delete("/clear")
def clear_cart(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Clear all cart items for current user (requires authentication) - soft delete"""
    
    # Get user's active cart first (or create if doesn't exist but has items)
    cart = db.query(Cart).filter(
        Cart.user_id == current_user.id,
        Cart.is_active == True
    ).first()
    
    # Get cart items first to check if user has any
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == current_user.id,
        CartItem.is_deleted == False
    ).all()
    
    # If cart doesn't exist but user has items, create cart
    if not cart and cart_items:
        cart = get_or_create_user_cart(db, current_user.id)
        # Update items to use the new cart_id
        for item in cart_items:
            if not item.cart_id:
                item.cart_id = cart.id
    
    cart_id = cart.id if cart else None
    
    # Soft delete: set is_deleted = True instead of actually deleting
    # Query via cart_id if available, otherwise use all items we found
    if cart_id and cart_items:
        # Re-query with cart_id to ensure we get all items
        cart_items = db.query(CartItem).filter(
            CartItem.cart_id == cart_id,
            CartItem.is_deleted == False
        ).all()
    
    deleted_count = len(cart_items)
    for item in cart_items:
        item.is_deleted = True
    
    # Remove applied coupon when cart is cleared
    # This ensures coupon is not applied to new items added after clearing
    coupon_removed = remove_coupon_from_cart(db, current_user.id)
    if coupon_removed:
        logger.info(f"Removed coupon from cart when clearing cart for user {current_user.id}")
    
    # Update cart's last_activity_at
    if cart:
        from Login_module.Utils.datetime_utils import now_ist
        cart.last_activity_at = now_ist()
    
    db.commit()
    
    # Audit log - now with proper cart_id
    ip, user_agent = get_client_info(request)
    correlation_id = str(uuid.uuid4())
    create_audit_log(
        db=db,
        user_id=current_user.id,
        cart_id=cart_id,  # Fixed: Now includes cart_id
        action="CLEAR",
        entity_type="CART",
        details={
            "items_deleted": deleted_count,
            "cart_id": cart_id,
            "coupon_removed": coupon_removed  # Track if coupon was removed
        },
        ip_address=ip,
        user_agent=user_agent,
        username=current_user.name or current_user.mobile,
        correlation_id=correlation_id
    )
    
    message = f"Cleared {deleted_count} item(s) from the cart."
    if coupon_removed:
        message += " Applied coupon has been removed."
    
    return {
        "status": "success",
        "message": message
    }


@router.get("/view")
def view_cart(
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Optional[Member] = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    View cart items for current user (requires authentication).
    All cart items are visible to all members of the same user.
    The cart is the same regardless of which member profile is viewing it.
    All items for a user share the same cart_id.
    Returns cart items with product_id, address_id, cart_id, member_id.
    Groups items by group_id for couple/family products.
    """
    # Get user's active cart (or create if doesn't exist and has items)
    cart = db.query(Cart).filter(
        Cart.user_id == current_user.id,
        Cart.is_active == True
    ).first()
    
    # Get all cart items for user (don't filter by member yet - need to check plan types)
    # First try to get items via cart_id if cart exists
    if cart:
        query = db.query(CartItem).options(
            joinedload(CartItem.member),
            joinedload(CartItem.address),
            joinedload(CartItem.product)
        ).filter(
            CartItem.cart_id == cart.id,
            CartItem.is_deleted == False  # Exclude deleted/cleared items
        )
    else:
        # Fallback for backward compatibility - query by user_id
        query = db.query(CartItem).options(
            joinedload(CartItem.member),
            joinedload(CartItem.address),
            joinedload(CartItem.product)
        ).filter(
            CartItem.user_id == current_user.id,
            CartItem.is_deleted == False  # Exclude deleted/cleared items
        )
    
    all_cart_items = query.order_by(CartItem.group_id, CartItem.created_at).unique().all()
    
    # If cart doesn't exist but user has items, create cart now
    if not cart and all_cart_items:
        cart = get_or_create_user_cart(db, current_user.id)
        # Update items to use the new cart_id
        for item in all_cart_items:
            if not item.cart_id:
                item.cart_id = cart.id
        db.flush()  # Flush instead of commit - let the endpoint commit
    
    cart_id = cart.id if cart else None
    
    # All cart items are visible to all members of the same user
    # Cart is the same regardless of which member profile is viewing it
    cart_items = all_cart_items
    
    if not cart_items:
        # Audit log
        ip, user_agent = get_client_info(request)
        create_audit_log(
            db=db,
            user_id=current_user.id,
            cart_id=cart_id,  # Include cart_id even for empty cart (may be None if no cart exists)
            action="VIEW",
            entity_type="CART",
            details={"items_count": 0, "cart_id": cart_id},
            ip_address=ip,
            user_agent=user_agent
        )
        
        return {
            "status": "success",
            "message": "Cart is empty.",
            "data": {
                "cart_summary": None,
                "cart_items": []
            }
        }

    subtotal_amount = 0
    delivery_charge = 0
    cart_item_details = []
    
    # Group items by group_id to show couple/family products together
    grouped_items = {}
    for item in cart_items:
        group_key = item.group_id or f"single_{item.id}"
        if group_key not in grouped_items:
            grouped_items[group_key] = []
        grouped_items[group_key].append(item)

    for group_key, items in grouped_items.items():
        # Skip if group is empty (should not happen, but safety check)
        if not items:
            continue
            
        # Use first item as representative (all items in group have same product, quantity)
        # Note: addresses may differ per member
        item = items[0]
        product = item.product
        
        # Skip if product is deleted or missing
        if not product:
            continue
            
        member_ids = [i.member_id for i in items]
        
        # Build member-address mapping with full details for this group
        member_address_map = []
        for i in items:
            member = i.member
            address = i.address
            
            member_details = {
                "member_id": member.id if member else i.member_id,
                "name": member.name if member else "Unknown",
                "relation": str(member.relation) if member else None,  # Now a string, no need for .value check
                "age": member.age if member else None,
                "gender": member.gender if member else None,
                "dob": to_ist_isoformat(member.dob) if member and member.dob else None,
                "mobile": member.mobile if member else None
            }
            
            address_details = {
                "address_id": address.id if address else i.address_id,
                "address_label": address.address_label if address else None,
                "street_address": address.street_address if address else None,
                "landmark": address.landmark if address else None,
                "locality": address.locality if address else None,
                "city": address.city if address else None,
                "state": address.state if address else None,
                "postal_code": address.postal_code if address else None,
                "country": address.country if address else None
            }
            
            member_address_map.append({
                "member": member_details,
                "address": address_details
            })
        
        # Get unique address IDs (may be 1 or multiple)
        address_ids = list(set(i.address_id for i in items))
        
        # Calculate total (quantity * price) - price is already for the plan, not per member
        total = item.quantity * product.SpecialPrice
        subtotal_amount += total
        
        # Calculate discount per item (difference between price and special_price)
        discount_per_item = product.Price - product.SpecialPrice

        cart_item_details.append({
            "cart_id": item.cart_id,  # Simple cart_id number
            "cart_item_ids": [i.id for i in items],  # All cart item IDs in this group
            "product_id": product.ProductId,
            "address_ids": address_ids,  # List of unique address IDs used
            "member_ids": member_ids,
            "member_address_map": member_address_map,  # Per-member address mapping with full details
            "product_name": product.Name,
            "product_images": product.Images,
            "plan_type": product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type),
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "quantity": item.quantity,
            "members_count": len(items),  # 1 for single, 2 for couple, 3-4 for family
            "discount_per_item": discount_per_item,
            "total_amount": total,
            "group_id": item.group_id
        })

    # Get applied coupon if any
    applied_coupon = get_applied_coupon(db, current_user.id)
    coupon_amount = 0.0
    coupon_code = None
    
    if applied_coupon:
        # Re-validate and recalculate discount (cart total might have changed)
        # Pass cart_items for product type validation (e.g., FAMILYCOUPLE30 coupon)
        coupon, calculated_discount, error_message = validate_and_calculate_discount(
            db, applied_coupon.coupon_code, current_user.id, subtotal_amount, cart_items
        )
        
        if coupon and not error_message:
            # Coupon is valid - use the recalculated discount
            coupon_amount = calculated_discount
            coupon_code = applied_coupon.coupon_code
            
            # Update the stored discount amount if it changed significantly
            if abs(applied_coupon.discount_amount - calculated_discount) > 0.01:
                applied_coupon.discount_amount = calculated_discount
                db.commit()
                logger.info(f"Updated coupon discount from {applied_coupon.discount_amount} to {calculated_discount} for user {current_user.id}")
        else:
            # Validation failed - log the error but keep using the stored discount
            # This ensures the coupon shows in cart even if validation temporarily fails
            # (e.g., cart total changed, but coupon is still technically valid)
            logger.warning(f"Coupon validation warning for '{applied_coupon.coupon_code}': {error_message}. Using stored discount.")
            coupon_amount = applied_coupon.discount_amount
            coupon_code = applied_coupon.coupon_code
            
            # Only remove if coupon is truly invalid (expired, deleted, inactive)
            if error_message and any(keyword in error_message.lower() for keyword in ["expired", "has expired", "not active", "invalid coupon code"]):
                logger.warning(f"Removing invalid coupon '{applied_coupon.coupon_code}'. Error: {error_message}")
                remove_coupon_from_cart(db, current_user.id)
                coupon_amount = 0.0
                coupon_code = None
    else:
        # No coupon applied - coupons are tracked in cart_coupons table
        # No need to check cart items for coupon codes anymore
        pass
    
    # Calculate discount amount (from product discounts - per product group, not per cart item row)
    # For couple/family products, there are multiple cart item rows but discount applies once per product
    total_product_discount = 0
    processed_groups = set()
    for item in cart_items:
        # Skip if product is deleted or missing
        if not item.product:
            continue
            
        group_key = item.group_id or f"single_{item.id}"
        if group_key not in processed_groups:
            # Calculate discount once per product group
            discount_per_item = item.product.Price - item.product.SpecialPrice
            total_product_discount += discount_per_item * item.quantity
            processed_groups.add(group_key)
    discount_amount = total_product_discount
    
    # Calculate total savings
    you_save = discount_amount + coupon_amount
    
    # Calculate grand total
    # Note: subtotal_amount already uses SpecialPrice (product discount is already applied)
    # So we only subtract coupon_amount, not discount_amount
    grand_total = subtotal_amount + delivery_charge - coupon_amount
    # Ensure grand total is not negative
    grand_total = max(0.0, grand_total)

    # Get cart_id from cart or first item
    if not cart_id and cart_items:
        cart_id = cart_items[0].cart_id if cart_items[0].cart_id else None

    summary = {
        "cart_id": cart_id,  # Proper cart.id from cart table
        "total_items": len(grouped_items),  # Number of product groups
        "total_cart_items": len(cart_items),  # Total individual cart items
        "subtotal_amount": subtotal_amount,
        "discount_amount": discount_amount,
        "coupon_amount": coupon_amount,
        "coupon_code": coupon_code,
        "you_save": you_save,
        "delivery_charge": delivery_charge,
        "grand_total": grand_total
    }

    # Audit log
    ip, user_agent = get_client_info(request)
    correlation_id = str(uuid.uuid4())
    create_audit_log(
        db=db,
        user_id=current_user.id,
        cart_id=cart_id,  # Include cart_id
        action="VIEW",
        entity_type="CART",
        details={
            "items_count": len(cart_items),
            "product_groups": len(grouped_items),
            "grand_total": grand_total,
            "cart_id": cart_id
        },
        ip_address=ip,
        user_agent=user_agent,
        username=current_user.name or current_user.mobile,
        correlation_id=correlation_id
    )

    return {
        "status": "success",
        "message": "Cart data fetched successfully.",
        "data": {
            "user_id": current_user.id,
            "username": current_user.name or current_user.mobile,
            "cart_summary": summary,
            "cart_items": cart_item_details
        }
    }


@router.post("/apply-coupon")
def apply_coupon(
    request_data: ApplyCouponRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Apply coupon code to cart (requires authentication).
    Validates coupon and calculates discount amount.
    Shows 'You Save' amount in response.
    """
    try:
        # Get user's active cart (or create if doesn't exist and has items)
        cart = db.query(Cart).filter(
            Cart.user_id == current_user.id,
            Cart.is_active == True
        ).first()
        
        # Get user's cart items to calculate subtotal (exclude deleted items)
        if cart:
            cart_items = db.query(CartItem).filter(
                CartItem.cart_id == cart.id,
                CartItem.is_deleted == False
            ).all()
        else:
            # Fallback for backward compatibility
            cart_items = db.query(CartItem).filter(
                CartItem.user_id == current_user.id,
                CartItem.is_deleted == False
            ).all()
            
            # If cart doesn't exist but user has items, create cart
            if cart_items:
                cart = get_or_create_user_cart(db, current_user.id)
                # Update items to use the new cart_id
                for item in cart_items:
                    if not item.cart_id:
                        item.cart_id = cart.id
                db.flush()  # Flush - will be committed with coupon application
        
        if not cart_items:
            raise HTTPException(
                status_code=400,
                detail="Cart is empty. Add items to cart before applying coupon."
            )
        
        cart_id = cart.id if cart else None
        
        # Calculate subtotal and product discount
        subtotal_amount = 0.0
        grouped_items = {}
        for item in cart_items:
            group_key = item.group_id or f"single_{item.id}"
            if group_key not in grouped_items:
                grouped_items[group_key] = []
            grouped_items[group_key].append(item)
        
        for group_key, items in grouped_items.items():
            # Skip if group is empty (should not happen, but safety check)
            if not items:
                continue
                
            item = items[0]
            product = item.product
            
            # Skip if product is deleted or missing
            if not product:
                continue
                
            subtotal_amount += item.quantity * product.SpecialPrice
        
        # Calculate product discount (from product discounts - per product group, not per cart item row)
        total_product_discount = 0.0
        processed_groups = set()
        for item in cart_items:
            # Skip if product is deleted or missing
            if not item.product:
                continue
                
            group_key = item.group_id or f"single_{item.id}"
            if group_key not in processed_groups:
                # Calculate discount once per product group
                discount_per_item = item.product.Price - item.product.SpecialPrice
                total_product_discount += discount_per_item * item.quantity
                processed_groups.add(group_key)
        
        # Remove any previously applied coupon
        remove_coupon_from_cart(db, current_user.id)
        
        # Apply new coupon (tracked in cart_coupons table, not in cart_items)
        # Pass cart_items for product type validation (e.g., FAMILYCOUPLE30 coupon)
        success, coupon_discount_amount, message, coupon = apply_coupon_to_cart(
            db, current_user.id, request_data.coupon_code, subtotal_amount, cart_items
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # Coupon is now tracked in cart_coupons table, no need to update cart_items
        
        # Calculate delivery charge and grand total (matching cart view calculation)
        # Note: subtotal_amount already uses SpecialPrice (product discount is already applied)
        # So we only subtract coupon_discount_amount, not total_product_discount
        delivery_charge = 0.0
        grand_total = subtotal_amount + delivery_charge - coupon_discount_amount
        grand_total = max(0.0, grand_total)
        
        # Calculate total savings
        you_save = total_product_discount + coupon_discount_amount
        
        # Audit log
        ip, user_agent = get_client_info(request)
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            cart_id=cart_id,  # Include cart_id
            action="APPLY_COUPON",
            entity_type="CART",
            details={
                "coupon_code": coupon.coupon_code,
                "coupon_discount_amount": coupon_discount_amount,
                "product_discount_amount": total_product_discount,
                "subtotal": subtotal_amount,
                "grand_total": grand_total,
                "cart_id": cart_id
            },
            ip_address=ip,
            user_agent=user_agent,
            username=current_user.name or current_user.mobile,
            correlation_id=correlation_id
        )
        
        return {
            "status": "success",
            "message": message,
            "data": {
                "coupon_code": coupon.coupon_code,
                "coupon_description": coupon.description,
                "discount_type": coupon.discount_type.value,
                "discount_value": coupon.discount_value,
                "coupon_discount_amount": coupon_discount_amount,  # Discount from coupon
                "product_discount_amount": total_product_discount,  # Discount from product pricing
                "you_save": you_save,  # Total savings (product discount + coupon discount)
                "subtotal_amount": subtotal_amount,
                "delivery_charge": delivery_charge,
                "grand_total": grand_total
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error applying coupon: {str(e)}")


@router.delete("/remove-coupon")
def remove_coupon(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Remove applied coupon from cart (requires authentication).
    """
    try:
        # Get user's active cart for audit log (or create if doesn't exist)
        cart = db.query(Cart).filter(
            Cart.user_id == current_user.id,
            Cart.is_active == True
        ).first()
        
        # If no cart exists, create one (even if empty, for consistency)
        if not cart:
            cart = get_or_create_user_cart(db, current_user.id)
        
        cart_id = cart.id if cart else None
        
        # Remove coupon application
        removed = remove_coupon_from_cart(db, current_user.id)
        
        if not removed:
            return {
                "status": "success",
                "message": "No coupon was applied to your cart."
            }
        
        # Coupon removal is handled by remove_coupon_from_cart which removes from cart_coupons table
        # No need to update cart_items anymore
        
        # Audit log
        ip, user_agent = get_client_info(request)
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            cart_id=cart_id,  # Include cart_id
            action="REMOVE_COUPON",
            entity_type="CART",
            details={"cart_id": cart_id},
            ip_address=ip,
            user_agent=user_agent,
            username=current_user.name or current_user.mobile,
            correlation_id=correlation_id
        )
        
        return {
            "status": "success",
            "message": "Coupon removed successfully."
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error removing coupon: {str(e)}")


@router.get("/list-coupons")
def list_coupons(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all available coupons that users can apply.
    Only shows coupons that:
    - Are active
    - Are within validity period
    - Have not reached their max_uses limit
    """
    try:
        coupons = db.query(Coupon).filter(
            Coupon.status == CouponStatus.ACTIVE
        ).all()
        
        coupon_list = []
        from Login_module.Utils.datetime_utils import now_ist, to_ist
        now = now_ist()
        
        for coupon in coupons:
            # Check if coupon is within validity period
            # Normalize coupon datetime fields to IST to avoid timezone comparison issues
            valid_from_ist = to_ist(coupon.valid_from) if coupon.valid_from else None
            valid_until_ist = to_ist(coupon.valid_until) if coupon.valid_until else None
            
            is_within_validity = (
                (not valid_from_ist or now >= valid_from_ist) and
                (not valid_until_ist or now <= valid_until_ist)
            )
            
            if not is_within_validity:
                continue  # Skip expired or not yet valid coupons
            
            # Check if coupon has reached its usage limit
            if is_coupon_usage_limit_reached(db, coupon):
                continue  # Skip coupons that have reached max_uses limit
            
            # Get current usage count for display
            current_uses = get_coupon_usage_count(db, coupon.id)
            
            coupon_list.append({
                "id": coupon.id,
                "coupon_code": coupon.coupon_code,
                "description": coupon.description,
                "status": coupon.status.value,
                "discount_type": coupon.discount_type.value,
                "discount_value": coupon.discount_value,
                "min_order_amount": coupon.min_order_amount,
                "max_discount_amount": coupon.max_discount_amount,
                "max_uses": coupon.max_uses,
                "current_uses": current_uses,  # Show how many times it's been used
                "remaining_uses": coupon.max_uses - current_uses if coupon.max_uses else None,
                "valid_from": to_ist_isoformat(coupon.valid_from),
                "valid_until": to_ist_isoformat(coupon.valid_until),
                "created_at": to_ist_isoformat(coupon.created_at)
            })
        
        return {
            "status": "success",
            "message": f"Found {len(coupon_list)} available coupon(s)",
            "data": {
                "total_coupons": len(coupon_list),
                "coupons": coupon_list
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error listing coupons: {str(e)}")


@router.post("/create-coupon")
def create_coupon(
    coupon_data: CouponCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new coupon (no authentication required).
    This allows adding coupons to the database.
    """
    try:
        # Check if coupon code already exists
        existing_coupon = db.query(Coupon).filter(
            func.upper(Coupon.coupon_code) == coupon_data.coupon_code.upper()
        ).first()
        
        if existing_coupon:
            raise HTTPException(
                status_code=400,
                detail=f"Coupon code '{coupon_data.coupon_code}' already exists"
            )
        
        # Create new coupon
        new_coupon = Coupon(
            coupon_code=coupon_data.coupon_code.upper().strip(),
            description=coupon_data.description,
            # user_id removed - all coupons are applicable to all users
            discount_type=CouponType(coupon_data.discount_type),
            discount_value=coupon_data.discount_value,
            min_order_amount=coupon_data.min_order_amount,
            max_discount_amount=coupon_data.max_discount_amount,
            max_uses=coupon_data.max_uses,  # Optional, not required
            valid_from=coupon_data.valid_from,
            valid_until=coupon_data.valid_until,
            status=CouponStatus(coupon_data.status)
        )
        
        db.add(new_coupon)
        db.commit()
        db.refresh(new_coupon)
        
        return {
            "status": "success",
            "message": f"Coupon '{new_coupon.coupon_code}' created successfully",
            "data": {
                "id": new_coupon.id,
                "coupon_code": new_coupon.coupon_code,
                "description": new_coupon.description,
                "discount_type": new_coupon.discount_type.value,
                "discount_value": new_coupon.discount_value,
                # user_id removed - all coupons are applicable to all users
                "min_order_amount": new_coupon.min_order_amount,
                "max_discount_amount": new_coupon.max_discount_amount,
                "max_uses": new_coupon.max_uses,
                "valid_from": to_ist_isoformat(new_coupon.valid_from),
                "valid_until": to_ist_isoformat(new_coupon.valid_until),
                "status": new_coupon.status.value
            }
        }
    except HTTPException:
        db.rollback()
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error creating coupon: {str(e)}")

