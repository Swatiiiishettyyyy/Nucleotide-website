"""
Coupon service for validating and applying coupons.
"""
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from datetime import datetime
from typing import Optional, Tuple
import logging
from .Coupon_model import Coupon, CartCoupon, CouponType, CouponStatus

logger = logging.getLogger(__name__)


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
    
    # Normalize coupon code (uppercase and strip whitespace)
    normalized_code = coupon_code.upper().strip()
    logger.info(f"Validating coupon code: '{coupon_code}' (normalized: '{normalized_code}')")
    
    # Try multiple query methods for better compatibility
    # Method 1: Case-insensitive using func.upper() (works for most databases)
    coupon = db.query(Coupon).filter(
        func.upper(Coupon.coupon_code) == normalized_code
    ).first()
    
    # Method 2: If first method fails, try direct comparison with normalized input
    # (fallback for databases that don't support func.upper properly)
    if not coupon:
        # Get all coupons and compare in Python (fallback)
        all_coupons = db.query(Coupon).all()
        for c in all_coupons:
            if c.coupon_code and c.coupon_code.upper().strip() == normalized_code:
                coupon = c
                break
    
    if not coupon:
        # Check if any coupons exist at all (for debugging)
        total_coupons = db.query(Coupon).count()
        logger.warning(f"Coupon '{normalized_code}' not found. Total coupons in database: {total_coupons}")
        if total_coupons > 0:
            # Log first few coupon codes for debugging
            sample_coupons = db.query(Coupon.coupon_code).limit(5).all()
            sample_codes = [c[0] for c in sample_coupons]
            logger.debug(f"Sample coupon codes in DB: {sample_codes}")
            # Return more helpful error message
            return None, 0.0, f"Invalid coupon code '{normalized_code}'. Available coupons: {', '.join(sample_codes[:3])}..." if len(sample_codes) > 0 else "Invalid coupon code"
        else:
            logger.error("No coupons found in database!")
            return None, 0.0, "Invalid coupon code. No coupons available in the system."
    
    logger.info(f"Found coupon: {coupon.coupon_code} (ID: {coupon.id}, Status: {coupon.status})")
    
    # Check if coupon is active
    if coupon.status != CouponStatus.ACTIVE:
        logger.warning(f"Coupon '{coupon.coupon_code}' is not active. Status: {coupon.status}")
        return None, 0.0, f"Coupon '{coupon.coupon_code}' is not active (status: {coupon.status.value})"
    
    # Check validity period
    now = datetime.utcnow()
    if coupon.valid_from and now < coupon.valid_from:
        logger.warning(f"Coupon '{coupon.coupon_code}' is not yet valid. Valid from: {coupon.valid_from}, Current: {now}")
        return None, 0.0, f"Coupon '{coupon.coupon_code}' is not yet valid. Valid from: {coupon.valid_from.strftime('%Y-%m-%d %H:%M:%S')}"
    
    if coupon.valid_until and now > coupon.valid_until:
        logger.warning(f"Coupon '{coupon.coupon_code}' has expired. Valid until: {coupon.valid_until}, Current: {now}")
        return None, 0.0, f"Coupon '{coupon.coupon_code}' has expired. Valid until: {coupon.valid_until.strftime('%Y-%m-%d %H:%M:%S')}"
    
    # Note: user_id validation removed - all coupons are applicable to all users
    # Usage limits are tracked via max_uses and cart_coupons table
    
    # Check minimum order amount
    if subtotal_amount < coupon.min_order_amount:
        logger.warning(f"Coupon '{coupon.coupon_code}' requires minimum order of ₹{coupon.min_order_amount}, but subtotal is ₹{subtotal_amount}")
        return None, 0.0, f"Minimum amount of ₹{coupon.min_order_amount} needed to apply this coupon. Your cart total is ₹{subtotal_amount}. Add items worth ₹{coupon.min_order_amount - subtotal_amount:.2f} more to apply this coupon."
    
    # Check total usage limit (max_uses is optional, not required)
    if coupon.max_uses is not None:
        total_uses = db.query(func.count(CartCoupon.id)).filter(
            CartCoupon.coupon_id == coupon.id
        ).scalar()
        
        if total_uses >= coupon.max_uses:
            logger.warning(f"Coupon '{coupon.coupon_code}' usage limit reached. Used: {total_uses}/{coupon.max_uses}")
            return None, 0.0, f"Coupon '{coupon.coupon_code}' usage limit reached ({coupon.max_uses} uses)"
    
    # Calculate discount amount
    discount_amount = 0.0
    
    if coupon.discount_type == CouponType.PERCENTAGE:
        # Percentage discount
        discount_amount = (subtotal_amount * coupon.discount_value) / 100.0
        
        # Apply max discount cap if set (checking max_discount_amount field)
        if coupon.max_discount_amount is not None:
            discount_amount = min(discount_amount, coupon.max_discount_amount)

    elif coupon.discount_type == CouponType.FIXED:
        # Fixed amount discount
        discount_amount = min(coupon.discount_value, subtotal_amount)  # Can't discount more than subtotal
        # Also check max_discount_amount for fixed coupons if set
        if coupon.max_discount_amount is not None:
            discount_amount = min(discount_amount, coupon.max_discount_amount)

    return coupon, discount_amount, ""


def apply_coupon_to_cart(
    db: Session,
    user_id: int,
    coupon_code: str,
    subtotal_amount: float
) -> Tuple[bool, float, str, Optional[Coupon]]:
    """
    Apply coupon to cart and record the application.
    Updates existing CartCoupon record if one exists for this user, otherwise creates new one.
    
    Returns:
        Tuple of (success, discount_amount, message, coupon_object)
    """
    coupon, discount_amount, error_message = validate_and_calculate_discount(
        db, coupon_code, user_id, subtotal_amount
    )
    
    if not coupon:
        return False, 0.0, error_message or "Invalid coupon", None
    
    # Check if user already has a coupon applied, update it instead of creating new one
    existing_cart_coupon = db.query(CartCoupon).filter(
        CartCoupon.user_id == user_id
    ).first()
    
    if existing_cart_coupon:
        # Update existing record
        existing_cart_coupon.coupon_id = coupon.id
        existing_cart_coupon.coupon_code = coupon.coupon_code
        existing_cart_coupon.discount_amount = discount_amount
        existing_cart_coupon.applied_at = datetime.utcnow()
        db.commit()
        db.refresh(existing_cart_coupon)
        logger.info(f"Updated existing CartCoupon record (ID: {existing_cart_coupon.id}) for user {user_id}")
    else:
        # Create new record
        cart_coupon = CartCoupon(
            user_id=user_id,
            coupon_id=coupon.id,
            coupon_code=coupon.coupon_code,
            discount_amount=discount_amount
        )
        db.add(cart_coupon)
        db.commit()
        db.refresh(cart_coupon)
        logger.info(f"Created new CartCoupon record (ID: {cart_coupon.id}) for user {user_id}")
    
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


def get_coupon_usage_count(db: Session, coupon_id: int) -> int:
    """
    Get the total number of times a coupon has been used.
    """
    return db.query(func.count(CartCoupon.id)).filter(
        CartCoupon.coupon_id == coupon_id
    ).scalar()


def is_coupon_usage_limit_reached(db: Session, coupon: Coupon) -> bool:
    """
    Check if a coupon has reached its max_uses limit.
    Returns True if limit is reached, False otherwise.
    """
    if coupon.max_uses is None:
        # No limit set, so limit is never reached
        return False
    
    total_uses = get_coupon_usage_count(db, coupon.id)
    return total_uses >= coupon.max_uses
