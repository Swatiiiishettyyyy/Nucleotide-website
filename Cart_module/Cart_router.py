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
from .Cart_schema import CartAdd, CartUpdate
from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from .Cart_audit_crud import create_audit_log

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
    Every cart item must be linked with member_id and address_id.
    """
    try:
        # Check if product exists
        product = db.query(Product).filter(Product.ProductId == item.product_id).first()
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")

        category_name = product.category.name if product.category else "this category"
        
        # Validate address exists and belongs to user
        address = db.query(Address).filter(
            Address.id == item.address_id,
            Address.user_id == current_user.id
        ).first()
        if not address:
            raise HTTPException(status_code=404, detail="Address not found or does not belong to you")
        
        # Validate member_ids are unique (no duplicates)
        if len(item.member_ids) != len(set(item.member_ids)):
            raise HTTPException(
                status_code=400,
                detail="Duplicate member IDs are not allowed. Each member can only be added once per product."
            )
        
        # Validate members exist and belong to user
        members = db.query(Member).filter(
            Member.id.in_(item.member_ids),
            Member.user_id == current_user.id
        ).all()
        
        if len(members) != len(item.member_ids):
            raise HTTPException(status_code=404, detail="One or more members not found")
        
        # Check if any of these members are already in cart for another product
        # within the same category
        existing_cart_members = (
            db.query(CartItem)
            .join(Product, CartItem.product_id == Product.ProductId)
            .filter(
                CartItem.user_id == current_user.id,
                CartItem.member_id.in_(item.member_ids),
                Product.category_id == product.category_id,
                CartItem.product_id != item.product_id
            )
            .first()
        )
        
        if existing_cart_members:
            raise HTTPException(
                status_code=400,
                detail=(
                    "One or more members in this request already belong to another "
                    f"product in the '{category_name}' category. "
                    "A member cannot subscribe to multiple products in the same category."
                )
            )
        
        # Check if same product with same members and address already exists in cart
        # For couple/family products, check by group_id or by matching all member_ids
        existing_cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id,
            CartItem.product_id == item.product_id,
            CartItem.address_id == item.address_id
        ).all()
        
        if existing_cart_items:
            # Check if all member_ids match (for couple/family, check group)
            existing_member_ids = set(ci.member_id for ci in existing_cart_items)
            requested_member_ids = set(item.member_ids)
            
            if existing_member_ids == requested_member_ids:
                raise HTTPException(
                    status_code=400,
                    detail="This product with the same members and address is already in your cart."
                )
        
        # Validate member count matches product plan type
        if product.plan_type == PlanType.SINGLE and len(item.member_ids) != 1:
            raise HTTPException(
                status_code=400,
                detail=f"Single plan requires exactly 1 member, got {len(item.member_ids)}"
            )
        elif product.plan_type == PlanType.COUPLE and len(item.member_ids) != 2:
            raise HTTPException(
                status_code=400,
                detail=f"Couple plan requires exactly 2 members, got {len(item.member_ids)}"
            )
        elif product.plan_type == PlanType.FAMILY and len(item.member_ids) != 4:
            raise HTTPException(
                status_code=400,
                detail=f"Family plan requires exactly 4 members, got {len(item.member_ids)}"
            )
        
        ip, user_agent = get_client_info(request)
        
        # Generate unique group_id using full UUID for better uniqueness
        group_id = f"{current_user.id}_{product.ProductId}_{uuid.uuid4().hex}"
        
        created_cart_items = []
        
        try:
            # For couple products: create 2 rows, one for each member
            # For family products: create 4 rows, one for each member
            # For single products: create 1 row
            for member in members:
                cart_item = CartItem(
                    user_id=current_user.id,
                    product_id=item.product_id,
                    address_id=item.address_id,
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
                "address_id": item.address_id,
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
                "address_id": item.address_id,
                "member_ids": item.member_ids,
                "quantity": item.quantity,
                "plan_type": product.plan_type.value,
                "price": product.Price,
                "special_price": product.SpecialPrice,
                "total_amount": item.quantity * product.SpecialPrice,
                "items_created": len(created_cart_items)  # 1 for single, 2 for couple, 4 for family
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
        # Use first item as representative (all items in group have same product, quantity, address)
        item = items[0]
        product = item.product
        member_ids = [i.member_id for i in items]
        
        # Calculate total (quantity * price) - price is already for the plan, not per member
        total = item.quantity * product.SpecialPrice
        subtotal_amount += total

        cart_item_details.append({
            "cart_id": item.id,  # Primary cart item ID
            "cart_item_ids": [i.id for i in items],  # All cart item IDs in this group
            "product_id": product.ProductId,
            "address_id": item.address_id,
            "member_ids": member_ids,
            "product_name": product.Name,
            "product_images": product.Images,
            "plan_type": product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type),
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "quantity": item.quantity,
            "members_count": len(items),  # 1 for single, 2 for couple, 4 for family
            "total_amount": total,
            "group_id": item.group_id
        })

    grand_total = subtotal_amount + delivery_charge

    summary = {
        "total_items": len(grouped_items),  # Number of product groups
        "total_cart_items": len(cart_items),  # Total individual cart items
        "subtotal_amount": subtotal_amount,
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