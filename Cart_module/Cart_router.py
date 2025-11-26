from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional, List
import uuid
from datetime import datetime

from database import SessionLocal
from .Cart_model import CartItem
from Product_module.Product_model import Product, PlanType
from Address_module.Address_model import Address
from Member_module.Member_model import Member
from Login_module.User.user_model import User
from .Cart_schema import CartAdd, CartUpdate, ApplyCouponRequest
from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from .Cart_audit_crud import create_audit_log
from .coupon_service import (
    apply_coupon_to_cart,
    get_applied_coupon,
    remove_coupon_from_cart,
    validate_and_calculate_discount
)

router = APIRouter(prefix="/cart", tags=["Cart"])


def get_client_info(request: Request):
    """Extract client IP and user agent from request"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


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
        product = db.query(Product).filter(Product.ProductId == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        category_name = product.category.name if product.category else "this category"
        
        # Normalize address_id to list (schema validator already ensures it's a list)
        address_ids = item.address_id if isinstance(item.address_id, list) else [item.address_id]
        num_addresses = len(address_ids)
        num_members = len(item.member_ids)
        
        # Validate address count: either 1 shared address or 1 per member
        if num_addresses != 1 and num_addresses != num_members:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Address count mismatch. Provide either 1 shared address or {num_members} addresses "
                    f"(one per member). Got {num_addresses} address(es) for {num_members} member(s)."
                )
            )
        
        # Validate all addresses exist and belong to user
        addresses = db.query(Address).filter(
            Address.id.in_(address_ids),
            Address.user_id == current_user.id
        ).all()
        
        if len(addresses) != num_addresses:
            found_ids = {addr.id for addr in addresses}
            missing_ids = [aid for aid in address_ids if aid not in found_ids]
            raise HTTPException(
                status_code=422,
                detail=f"Address(es) {missing_ids} not found or do not belong to you."
            )
        
        # Validate member_ids are unique (no duplicates)
        if len(item.member_ids) != len(set(item.member_ids)):
            raise HTTPException(
                status_code=422,
                detail="Duplicate member IDs are not allowed. Each member can only be added once per product."
            )
        
        # Validate members exist and belong to user
        members = db.query(Member).filter(
            Member.id.in_(item.member_ids),
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
                CartItem.user_id == current_user.id,
                CartItem.member_id.in_(item.member_ids),
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
        existing_cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == item.product_id
        ).all()
        
        if existing_cart_items:
            # Group by group_id to check member sets
            from collections import defaultdict
            grouped_existing = defaultdict(list)
            for ci in existing_cart_items:
                group_key = ci.group_id or f"single_{ci.id}"
                grouped_existing[group_key].append(ci)
            
            requested_member_ids = set(item.member_ids)
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
        
        # Map members to addresses
        # If 1 address provided, use it for all members; otherwise use one address per member
        member_address_map = {}
        if num_addresses == 1:
            # Single shared address for all members
            shared_address_id = address_ids[0]
            for member in members:
                member_address_map[member.id] = shared_address_id
        else:
            # One address per member (in order)
            for idx, member in enumerate(members):
                member_address_map[member.id] = address_ids[idx]
        
        created_cart_items = []
        
        try:
            # Create cart items: one row per member with their assigned address
            for member in members:
                assigned_address_id = member_address_map[member.id]
                cart_item = CartItem(
                    user_id=current_user.id,
                    product_id=item.product_id,
                    address_id=assigned_address_id,
                    member_id=member.id,
                    quantity=item.quantity,
                    group_id=group_id  # Link all items for this product purchase
                )
                db.add(cart_item)
                created_cart_items.append(cart_item)
            
            # Commit all items together (transaction safety)
            db.commit()
            
            # Refresh all created items
            for cart_item in created_cart_items:
                db.refresh(cart_item)
        except Exception as e:
            # Rollback on any error to prevent partial data
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"Error adding items to cart: {str(e)}"
            )
        
        # Build member-address mapping for response
        member_address_response = [
            {"member_id": mid, "address_id": aid}
            for mid, aid in member_address_map.items()
        ]
        
        # Audit log
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="ADD",
            entity_type="CART_ITEM",
            entity_id=created_cart_items[0].id,
            cart_id=created_cart_items[0].id,
            details={
                "product_id": product.ProductId,
                "plan_type": product.plan_type.value,
                "quantity": item.quantity,
                "member_ids": item.member_ids,
                "address_ids": address_ids,
                "member_address_map": member_address_map,
                "cart_items_created": len(created_cart_items),
                "group_id": group_id
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
                "cart_id": created_cart_items[0].id,  # Primary cart item ID
                "product_id": product.ProductId,
                "address_ids": address_ids,
                "member_ids": item.member_ids,
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
        CartItem.user_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    old_quantity = cart_item.quantity
    group_id = cart_item.group_id
    
    try:
        # If item has a group_id, update all items in the group (for couple/family products)
        if group_id:
            # Update all items in the group
            group_items = db.query(CartItem).filter(
                CartItem.group_id == group_id,
                CartItem.user_id == current_user.id
            ).all()
            
            for item in group_items:
                item.quantity = update.quantity
            updated_count = len(group_items)
        else:
            # Single item, update just this one
            cart_item.quantity = update.quantity
            updated_count = 1
        
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
            cart_id=cart_item.id,
            details={
                "product_id": product.ProductId,
                "old_quantity": old_quantity,
                "new_quantity": update.quantity,
                "group_id": group_id,
                "items_updated": updated_count
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
        CartItem.user_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product_id = cart_item.product_id
    quantity = cart_item.quantity
    group_id = cart_item.group_id
    
    # If item has a group_id, delete all items in the group (for couple/family products)
    if group_id:
        # Delete all items in the group
        deleted_items = db.query(CartItem).filter(
            CartItem.group_id == group_id,
            CartItem.user_id == current_user.id
        ).all()
        
        deleted_count = len(deleted_items)
        for item in deleted_items:
            db.delete(item)
    else:
        # Single item, delete just this one
        db.delete(cart_item)
        deleted_count = 1
    
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
        details={
            "product_id": product_id,
            "quantity": quantity,
            "group_id": group_id,
            "items_deleted": deleted_count
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
    """Clear all cart items for current user (requires authentication)"""
    
    deleted_count = db.query(CartItem).filter(
        CartItem.user_id == current_user.id
    ).delete()
    db.commit()
    
    # Audit log
    ip, user_agent = get_client_info(request)
    correlation_id = str(uuid.uuid4())
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CLEAR",
        entity_type="CART",
        details={
            "items_deleted": deleted_count
        },
        ip_address=ip,
        user_agent=user_agent,
        username=current_user.name or current_user.mobile,
        correlation_id=correlation_id
    )
    
    return {
        "status": "success",
        "message": f"Cleared {deleted_count} item(s) from the cart."
    }


@router.get("/view")
def view_cart(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    View cart items for current user (requires authentication).
    Returns cart items with product_id, address_id, cart_id, member_id.
    Groups items by group_id for couple/family products.
    """
    
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == current_user.id
    ).order_by(CartItem.group_id, CartItem.created_at).all()
    
    if not cart_items:
        # Audit log
        ip, user_agent = get_client_info(request)
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="VIEW",
            entity_type="CART",
            details={"items_count": 0},
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
    delivery_charge = 50
    cart_item_details = []
    
    # Group items by group_id to show couple/family products together
    grouped_items = {}
    for item in cart_items:
        group_key = item.group_id or f"single_{item.id}"
        if group_key not in grouped_items:
            grouped_items[group_key] = []
        grouped_items[group_key].append(item)

    for group_key, items in grouped_items.items():
        # Use first item as representative (all items in group have same product, quantity)
        # Note: addresses may differ per member
        item = items[0]
        product = item.product
        member_ids = [i.member_id for i in items]
        
        # Build member-address mapping for this group
        member_address_map = [
            {"member_id": i.member_id, "address_id": i.address_id}
            for i in items
        ]
        
        # Get unique address IDs (may be 1 or multiple)
        address_ids = list(set(i.address_id for i in items))
        
        # Calculate total (quantity * price) - price is already for the plan, not per member
        total = item.quantity * product.SpecialPrice
        subtotal_amount += total

        cart_item_details.append({
            "cart_id": item.id,  # Primary cart item ID
            "cart_item_ids": [i.id for i in items],  # All cart item IDs in this group
            "product_id": product.ProductId,
            "address_ids": address_ids,  # List of unique address IDs used
            "address_id": address_ids[0] if len(address_ids) == 1 else None,  # Backward compatibility: single address if all same
            "member_ids": member_ids,
            "member_address_map": member_address_map,  # Per-member address mapping
            "product_name": product.Name,
            "product_images": product.Images,
            "plan_type": product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type),
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "quantity": item.quantity,
            "members_count": len(items),  # 1 for single, 2 for couple, 3-4 for family
            "total_amount": total,
            "group_id": item.group_id
        })

    # Get applied coupon if any
    applied_coupon = get_applied_coupon(db, current_user.id)
    coupon_amount = 0.0
    coupon_code = None
    
    if applied_coupon:
        # Re-validate coupon to ensure it's still valid
        coupon, discount, error = validate_and_calculate_discount(
            db, applied_coupon.coupon_code, current_user.id, subtotal_amount
        )
        if coupon and not error:
            coupon_amount = discount
            coupon_code = applied_coupon.coupon_code
        else:
            # Coupon is no longer valid, remove it
            remove_coupon_from_cart(db, current_user.id)
            coupon_amount = 0.0
            coupon_code = None
    
    # Calculate discount amount (from product discounts, if any)
    discount_amount = 0.0  # Can be calculated from product.Discount if needed
    
    # Calculate total savings
    you_save = discount_amount + coupon_amount
    
    # Calculate grand total
    grand_total = subtotal_amount + delivery_charge - coupon_amount - discount_amount
    # Ensure grand total is not negative
    grand_total = max(0.0, grand_total)

    summary = {
        "cart_id": cart_items[0].id if cart_items else 0,
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
        action="VIEW",
        entity_type="CART",
        details={
            "items_count": len(cart_items),
            "product_groups": len(grouped_items),
            "grand_total": grand_total
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
        # Get user's cart items to calculate subtotal
        cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id
        ).all()
        
        if not cart_items:
            raise HTTPException(
                status_code=400,
                detail="Cart is empty. Add items to cart before applying coupon."
            )
        
        # Calculate subtotal
        subtotal_amount = 0.0
        grouped_items = {}
        for item in cart_items:
            group_key = item.group_id or f"single_{item.id}"
            if group_key not in grouped_items:
                grouped_items[group_key] = []
            grouped_items[group_key].append(item)
        
        for group_key, items in grouped_items.items():
            item = items[0]
            product = item.product
            subtotal_amount += item.quantity * product.SpecialPrice
        
        # Remove any previously applied coupon
        remove_coupon_from_cart(db, current_user.id)
        
        # Apply new coupon
        success, discount_amount, message, coupon = apply_coupon_to_cart(
            db, current_user.id, request_data.coupon_code, subtotal_amount
        )
        
        if not success:
            raise HTTPException(status_code=400, detail=message)
        
        # Update all cart items with coupon code
        for item in cart_items:
            item.coupon_code = coupon.coupon_code
        db.commit()
        
        # Calculate delivery charge and grand total
        delivery_charge = 50.0
        grand_total = subtotal_amount + delivery_charge - discount_amount
        grand_total = max(0.0, grand_total)
        
        # Audit log
        ip, user_agent = get_client_info(request)
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="APPLY_COUPON",
            entity_type="CART",
            details={
                "coupon_code": coupon.coupon_code,
                "discount_amount": discount_amount,
                "subtotal": subtotal_amount,
                "grand_total": grand_total
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
                "discount_amount": discount_amount,
                "you_save": discount_amount,
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
        # Remove coupon application
        removed = remove_coupon_from_cart(db, current_user.id)
        
        if not removed:
            return {
                "status": "success",
                "message": "No coupon was applied to your cart."
            }
        
        # Remove coupon code from cart items
        cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.coupon_code.isnot(None)
        ).all()
        
        for item in cart_items:
            item.coupon_code = None
        db.commit()
        
        # Audit log
        ip, user_agent = get_client_info(request)
        correlation_id = str(uuid.uuid4())
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="REMOVE_COUPON",
            entity_type="CART",
            details={},
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