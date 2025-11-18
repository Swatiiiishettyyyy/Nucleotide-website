from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from typing import Optional

from database import SessionLocal
from .Cart_model import CartItem
from Product_module.Product_model import Product
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
    """Add item to cart (requires authentication)"""
    
    # Check if product exists
    product = db.query(Product).filter(Product.ProductId == item.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check if item already exists in user's cart
    cart_item = db.query(CartItem).filter(
        CartItem.product_id == item.product_id,
        CartItem.user_id == current_user.id
    ).first()
    
    ip, user_agent = get_client_info(request)
    
    if cart_item:
        # Update existing cart item
        old_quantity = cart_item.quantity
        cart_item.quantity += item.quantity
        db.commit()
        db.refresh(cart_item)
        
        # Audit log
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
                "new_quantity": cart_item.quantity,
                "quantity_added": item.quantity
            },
            ip_address=ip,
            user_agent=user_agent
        )
    else:
        # Create new cart item
        cart_item = CartItem(
            user_id=current_user.id,
            product_id=item.product_id,
            quantity=item.quantity
        )
        db.add(cart_item)
        db.commit()
        db.refresh(cart_item)
        
        # Audit log
        create_audit_log(
            db=db,
            user_id=current_user.id,
            action="ADD",
            entity_type="CART_ITEM",
            entity_id=cart_item.id,
            cart_id=cart_item.id,
            details={
                "product_id": product.ProductId,
                "quantity": cart_item.quantity
            },
            ip_address=ip,
            user_agent=user_agent
        )

    return {
        "status": "success",
        "message": "Product added to cart successfully.",
        "data": {
            "cart_item_id": cart_item.id,
            "product_id": product.ProductId,
            "quantity": cart_item.quantity,
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "total_amount": cart_item.quantity * product.SpecialPrice
        }
    }


@router.put("/update/{cart_item_id}")
def update_cart_item(
    cart_item_id: int,
    update: CartUpdate,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update cart item quantity (requires authentication)"""
    
    cart_item = db.query(CartItem).filter(
        CartItem.id == cart_item_id,
        CartItem.user_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    old_quantity = cart_item.quantity
    cart_item.quantity = update.quantity
    db.commit()
    db.refresh(cart_item)

    product = cart_item.product
    
    # Audit log
    ip, user_agent = get_client_info(request)
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
            "new_quantity": cart_item.quantity
        },
        ip_address=ip,
        user_agent=user_agent
    )
    
    return {
        "status": "success",
        "message": "Cart item updated successfully.",
        "data": {
            "cart_item_id": cart_item.id,
            "product_id": product.ProductId,
            "quantity": cart_item.quantity,
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "total_amount": cart_item.quantity * product.SpecialPrice
        }
    }


@router.delete("/delete/{cart_item_id}")
def delete_cart_item(
    cart_item_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete cart item (requires authentication)"""
    
    cart_item = db.query(CartItem).filter(
        CartItem.id == cart_item_id,
        CartItem.user_id == current_user.id
    ).first()
    
    if not cart_item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    product_id = cart_item.product_id
    quantity = cart_item.quantity
    
    db.delete(cart_item)
    db.commit()

    # Audit log
    ip, user_agent = get_client_info(request)
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="DELETE",
        entity_type="CART_ITEM",
        entity_id=cart_item_id,
        details={
            "product_id": product_id,
            "quantity": quantity
        },
        ip_address=ip,
        user_agent=user_agent
    )

    return {
        "status": "success",
        "message": f"Cart item {cart_item_id} deleted successfully."
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
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="CLEAR",
        entity_type="CART",
        details={
            "items_deleted": deleted_count
        },
        ip_address=ip,
        user_agent=user_agent
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
    """View cart items for current user (requires authentication)"""
    
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == current_user.id
    ).all()
    
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

    for item in cart_items:
        product = item.product
        total = item.quantity * product.SpecialPrice
        subtotal_amount += total

        cart_item_details.append({
            "cart_item_id": item.id,
            "product_id": product.ProductId,
            "product_name": product.Name,
            "product_images": product.Images,
            "price": product.Price,
            "special_price": product.SpecialPrice,
            "quantity": item.quantity,
            "total_amount": total
        })

    grand_total = subtotal_amount + delivery_charge

    summary = {
        "total_items": len(cart_items),
        "subtotal_amount": subtotal_amount,
        "delivery_charge": delivery_charge,
        "grand_total": grand_total
    }

    # Audit log
    ip, user_agent = get_client_info(request)
    create_audit_log(
        db=db,
        user_id=current_user.id,
        action="VIEW",
        entity_type="CART",
        details={
            "items_count": len(cart_items),
            "grand_total": grand_total
        },
        ip_address=ip,
        user_agent=user_agent
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