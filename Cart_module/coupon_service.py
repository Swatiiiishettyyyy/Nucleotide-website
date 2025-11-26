"""
Coupon service for validating and applying coupons.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from typing import Optional, Tuple
from .Coupon_model import Coupon, CartCoupon, CouponType, CouponStatus


def validate_and_calculate_discount(
    db: Session,
    coupon_code: str,
    user_id: int,
    subtotal_amount: float
) -> Tuple[Optional[Coupon], float, str]:
    """
    Validate coupon and calculate discount amount.
    
    Returns:
        Tuple of (Coupon object or None, discount_amount, error_message)
    """
    if not coupon_code:
        return None, 0.0, ""
    
    # Find coupon by code
    coupon = db.query(Coupon).filter(
        Coupon.coupon_code == coupon_code.upper().strip()
    ).first()
    
    if not coupon:
        return None, 0.0, "Invalid coupon code"
    
    # Check if coupon is active
    if coupon.status != CouponStatus.ACTIVE:
        return None, 0.0, "Coupon is not active"
    
    # Check validity period
    now = datetime.utcnow()
    if coupon.valid_from and now < coupon.valid_from:
        return None, 0.0, "Coupon is not yet valid"
    
    if coupon.valid_until and now > coupon.valid_until:
        return None, 0.0, "Coupon has expired"
    
    # Check minimum order amount
    if subtotal_amount < coupon.min_order_amount:
        return None, 0.0, f"Minimum order amount of ₹{coupon.min_order_amount} required"
    
    # Check total usage limit
    if coupon.max_uses is not None:
        total_uses = db.query(func.count(CartCoupon.id)).filter(
            CartCoupon.coupon_id == coupon.id
        ).scalar()
        
        if total_uses >= coupon.max_uses:
            return None, 0.0, "Coupon usage limit reached"
    
    # Check per-user usage limit
    user_uses = db.query(func.count(CartCoupon.id)).filter(
        and_(
            CartCoupon.user_id == user_id,
            CartCoupon.coupon_id == coupon.id
        )
    ).scalar()
    
    if user_uses >= coupon.max_uses_per_user:
        return None, 0.0, "You have already used this coupon"
    
    # Calculate discount amount
    discount_amount = 0.0
    
    if coupon.discount_type == CouponType.PERCENTAGE:
        # Percentage discount
        discount_amount = (subtotal_amount * coupon.discount_value) / 100.0
        
        # Apply max discount cap if set
        if coupon.max_discount_amount is not None:
            discount_amount = min(discount_amount, coupon.max_discount_amount)
    
    elif coupon.discount_type == CouponType.FIXED:
        # Fixed amount discount
        discount_amount = min(coupon.discount_value, subtotal_amount)  # Can't discount more than subtotal
    
    return coupon, discount_amount, ""


def apply_coupon_to_cart(
    db: Session,
    user_id: int,
    coupon_code: str,
    subtotal_amount: float
) -> Tuple[bool, float, str, Optional[Coupon]]:
    """
    Apply coupon to cart and record the application.
    
    Returns:
        Tuple of (success, discount_amount, message, coupon_object)
    """
    coupon, discount_amount, error_message = validate_and_calculate_discount(
        db, coupon_code, user_id, subtotal_amount
    )
    
    if not coupon:
        return False, 0.0, error_message or "Invalid coupon", None
    
    # Record coupon application
    cart_coupon = CartCoupon(
        user_id=user_id,
        coupon_id=coupon.id,
        coupon_code=coupon.coupon_code,
        discount_amount=discount_amount
    )
    db.add(cart_coupon)
    db.commit()
    db.refresh(cart_coupon)
    
    return True, discount_amount, f"Coupon '{coupon.coupon_code}' applied successfully", coupon


def get_applied_coupon(
    db: Session,
    user_id: int
) -> Optional[CartCoupon]:
    """
    Get the most recently applied coupon for a user.
    """
    return db.query(CartCoupon).filter(
        CartCoupon.user_id == user_id
    ).order_by(CartCoupon.applied_at.desc()).first()


def remove_coupon_from_cart(
    db: Session,
    user_id: int
) -> bool:
    """
    Remove applied coupon from user's cart.
    Returns True if coupon was removed, False if no coupon was applied.
    """
    cart_coupon = get_applied_coupon(db, user_id)
    
    if cart_coupon:
        db.delete(cart_coupon)
        db.commit()
        return True
    
    return False

