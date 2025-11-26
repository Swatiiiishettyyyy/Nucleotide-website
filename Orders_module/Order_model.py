"""
Order model - stores order information and payment details.
No COD option, no refund policy.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, Enum, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from database import Base
import enum


class OrderStatus(str, enum.Enum):
    """Order tracking statuses"""
    ORDER_CONFIRMED = "order_confirmed"
    SCHEDULED = "scheduled"
    SCHEDULE_CONFIRMED_BY_LAB = "schedule_confirmed_by_lab"
    SAMPLE_COLLECTED = "sample_collected"
    SAMPLE_RECEIVED_BY_LAB = "sample_received_by_lab"
    TESTING_IN_PROGRESS = "testing_in_progress"
    REPORT_READY = "report_ready"


class PaymentStatus(str, enum.Enum):
    """Payment status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentMethod(str, enum.Enum):
    """Payment methods (No COD)"""
    RAZORPAY = "razorpay"
    # Add other online payment methods as needed


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)  # Unique order number
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Primary address can be NULL if original address is deleted (we use snapshot for order details)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True, index=True)
    
    # Order totals
    subtotal = Column(Float, nullable=False)
    delivery_charge = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    coupon_code = Column(String(50), nullable=True, index=True)  # Applied coupon code
    coupon_discount = Column(Float, default=0.0)  # Discount from coupon
    total_amount = Column(Float, nullable=False)  # Final amount paid
    
    # Payment details
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.RAZORPAY)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.PENDING, index=True)
    razorpay_order_id = Column(String(255), nullable=True, unique=True, index=True)  # Razorpay order ID
    razorpay_payment_id = Column(String(255), nullable=True, unique=True, index=True)  # Razorpay payment ID
    razorpay_signature = Column(String(255), nullable=True)  # Razorpay signature for verification
    payment_date = Column(DateTime(timezone=True), nullable=True)
    
    # Order status tracking
    order_status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.ORDER_CONFIRMED, index=True)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Technician and lab information
    scheduled_date = Column(DateTime(timezone=True), nullable=True)  # When technician will visit
    technician_name = Column(String(100), nullable=True)
    technician_contact = Column(String(20), nullable=True)
    lab_name = Column(String(200), nullable=True)
    
    # Additional notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
    address = relationship("Address")


class OrderItem(Base):
    """
    Order items - links orders to products and members.
    Each order item represents one product purchased for one member.
    Each item has its own status for tracking per-address delivery.
    """
    __tablename__ = "order_items"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    # These foreign keys allow NULL because we use OrderSnapshot for data integrity
    # If original product/member/address is deleted, FK becomes NULL but snapshot preserves data
    product_id = Column(Integer, ForeignKey("products.ProductId", ondelete="SET NULL"), nullable=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="SET NULL"), nullable=True)
    
    # Product snapshot at time of order (from snapshot table)
    snapshot_id = Column(Integer, ForeignKey("order_snapshots.id"), nullable=True)
    
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)  # Price at time of order
    total_price = Column(Float, nullable=False)  # quantity * unit_price
    
    # Per-item status tracking (for different addresses in couple/family packs)
    order_status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.ORDER_CONFIRMED, index=True)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", backref="items")
    product = relationship("Product")
    member = relationship("Member")
    address = relationship("Address")
    snapshot = relationship("OrderSnapshot")


class OrderSnapshot(Base):
    """
    Order snapshot - captures cart state at time of order.
    Stores product details, member details, address details as they were when order was placed.
    """
    __tablename__ = "order_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Snapshot of product details at order time
    product_data = Column(JSON, nullable=False)  # {ProductId, Name, Price, SpecialPrice, plan_type, category, etc.}
    
    # Snapshot of member details at order time
    member_data = Column(JSON, nullable=False)  # {id, name, relation, age, gender, mobile}
    
    # Snapshot of address details at order time
    address_data = Column(JSON, nullable=False)  # {id, address_label, street_address, city, state, postal_code, etc.}
    
    # Snapshot of cart item details
    cart_item_data = Column(JSON, nullable=True)  # Original cart item data if needed
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    order = relationship("Order", backref="snapshots")


class OrderStatusHistory(Base):
    """
    Order status history - tracks all status changes for an order.
    """
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=True, index=True)  # Null for order-level updates
    status = Column(Enum(OrderStatus), nullable=False, index=True)
    previous_status = Column(Enum(OrderStatus), nullable=True)
    notes = Column(Text, nullable=True)  # Additional notes about status change
    changed_by = Column(String(100), nullable=True)  # Who changed the status (user_id or "system")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    order = relationship("Order", backref="status_history")
    order_item = relationship("OrderItem", backref="status_history")


