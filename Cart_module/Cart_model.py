from sqlalchemy import Column, Integer, ForeignKey, DateTime, func, String, Boolean
from sqlalchemy.orm import relationship
from database import Base

class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(Integer, primary_key=True, index=True)
    cart_id = Column(Integer, nullable=True, index=True)  # Cart ID for grouping cart items
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("products.ProductId"), nullable=False, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id"), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id"), nullable=False, index=True)
    quantity = Column(Integer, nullable=False, default=1)
    
    # For couple/family products: link multiple cart items together
    # All items for the same product purchase share the same group_id
    group_id = Column(String(100), nullable=False, index=True)  # UUID or timestamp-based ID
    
    # Soft delete flag
    is_deleted = Column(Boolean, nullable=False, default=False, index=True)  # True if cart item is deleted/cleared
    
    # Note: Coupon tracking is handled by cart_coupons table, not in cart_items
    # This keeps cart items clean and coupons are managed at cart level
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Relationships
    user = relationship("User")
    product = relationship("Product")
    address = relationship("Address")
    member = relationship("Member")