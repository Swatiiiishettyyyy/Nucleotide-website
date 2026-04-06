"""
Coupon model for managing discount coupons.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, func, Enum, ForeignKey, UniqueConstraint, CheckConstraint
from sqlalchemy.orm import relationship
from database import Base
from Login_module.Utils.datetime_utils import now_ist
import enum


class CouponType(str, enum.Enum):
    """Coupon discount types"""
    PERCENTAGE = "percentage"  # Discount as percentage (e.g., 10% off)
    FIXED = "fixed"  # Fixed amount discount (e.g., ₹100 off)


class CouponStatus(str, enum.Enum):
    """Coupon status"""
    ACTIVE = "active"
    INACTIVE = "inactive"
    EXPIRED = "expired"


class Coupon(Base):
    """
    Coupon table for managing discount coupons.
    """
    __tablename__ = "coupons"

    id = Column(Integer, primary_key=True, index=True)
    coupon_code = Column(String(50), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)

    # Discount details
    discount_type = Column(Enum(CouponType), nullable=False, default=CouponType.PERCENTAGE)
    discount_value = Column(Float, nullable=False)

    # Minimum order amount to apply coupon
    min_order_amount = Column(Float, default=0.0, nullable=False)

    # Maximum discount cap (for percentage coupons)
    max_discount_amount = Column(Float, nullable=True)

    # Usage limits
    max_uses = Column(Integer, nullable=True)  # Total confirmed-order uses allowed (None = unlimited)
    max_uses_per_user = Column(Integer, nullable=True, default=1)  # Per-user limit (None = unlimited, default 1)

    # Validity period
    valid_from = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)

    # Status
    status = Column(Enum(CouponStatus), nullable=False, default=CouponStatus.ACTIVE, index=True)

    # Optional product restriction: comma-separated plan_type values e.g. "individual,couple"
    # None / empty = applicable to all plan types
    allowed_plan_types = Column(String(255), nullable=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=now_ist)

    # Relationships
    cart_applications = relationship("CartCoupon", back_populates="coupon", cascade="all, delete-orphan")
    usages = relationship("CouponUsage", back_populates="coupon", cascade="all, delete-orphan")
    allowed_users = relationship("CouponAllowedUser", back_populates="coupon", cascade="all, delete-orphan")


class CartCoupon(Base):
    """
    Tracks coupon applications to carts (temporary — removed after order confirm).
    """
    __tablename__ = "cart_coupons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    coupon_code = Column(String(50), nullable=False, index=True)
    discount_amount = Column(Float, nullable=False, default=0.0)
    applied_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)

    coupon = relationship("Coupon", back_populates="cart_applications")


class CouponUsage(Base):
    """
    Permanent record of coupon usage — one row per confirmed order that used a coupon.
    This is the source of truth for max_uses enforcement.
    """
    __tablename__ = "coupon_usages"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    coupon_code = Column(String(50), nullable=False, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    order_id = Column(Integer, nullable=False, index=True)
    order_number = Column(String(50), nullable=False)
    discount_amount = Column(Float, nullable=False, default=0.0)
    used_at = Column(DateTime(timezone=True), default=now_ist, nullable=False)

    coupon = relationship("Coupon", back_populates="usages")



class CouponAllowedUser(Base):
    """
    Restricts a coupon to specific users (by user_id or mobile number).
    If a coupon has any rows here, only those users/mobiles may apply it.
    """
    __tablename__ = "coupon_allowed_users"

    id = Column(Integer, primary_key=True, index=True)
    coupon_id = Column(Integer, ForeignKey("coupons.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    mobile = Column(String(100), nullable=True, index=True)

    __table_args__ = (
        UniqueConstraint("coupon_id", "user_id", name="uq_coupon_user_id"),
        UniqueConstraint("coupon_id", "mobile", name="uq_coupon_mobile"),
        CheckConstraint("user_id IS NOT NULL OR mobile IS NOT NULL", name="ck_coupon_allowed_users_not_both_null"),
    )

    coupon = relationship("Coupon", back_populates="allowed_users")
