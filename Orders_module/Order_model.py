"""
Order model - stores order information and payment details.
No COD option, no refund policy.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, func, Enum, ForeignKey, Text, JSON, Boolean
from sqlalchemy.orm import relationship
from database import Base
import enum


class OrderStatus(str, enum.Enum):
    """Order tracking statuses"""
    CREATED = "created"  # Order exists, not confirmed (initial state)
    AWAITING_PAYMENT_CONFIRMATION = "awaiting_payment_confirmation"  # Payment initiated, waiting for Razorpay/bank confirmation
    CONFIRMED = "confirmed"  # Payment verified by webhook, order finalized
    PAYMENT_FAILED = "payment_failed"  # Payment failed - order not confirmed
    SCHEDULED = "scheduled"
    SCHEDULE_CONFIRMED_BY_LAB = "schedule_confirmed_by_lab"
    SAMPLE_COLLECTED = "sample_collected"
    SAMPLE_RECEIVED_BY_LAB = "sample_received_by_lab"
    TESTING_IN_PROGRESS = "testing_in_progress"
    REPORT_READY = "report_ready"


class PaymentStatus(str, enum.Enum):
    """Payment status - tracks money/transaction state"""
    NOT_INITIATED = "not_initiated"  # Order created, payment not started
    PENDING = "pending"  # Payment initiated, awaiting completion
    SUCCESS = "success"  # Frontend verified only (temporary, before webhook)
    VERIFIED = "verified"  # Webhook confirmed (final, order can be confirmed)
    FAILED = "failed"  # Payment failed


class PaymentMethod(str, enum.Enum):
    """Payment methods (No COD)"""
    RAZORPAY = "razorpay"
    # Add other online payment methods as needed


class Order(Base):
    __tablename__ = "orders"

    id = Column(Integer, primary_key=True, index=True)
    order_number = Column(String(50), unique=True, nullable=False, index=True)  # Unique order number
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Primary address reference (we use snapshot for order details, but keep FK for reference)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True, index=True)
    
    # Order totals
    subtotal = Column(Float, nullable=False)
    delivery_charge = Column(Float, default=0.0)
    discount = Column(Float, default=0.0)
    coupon_code = Column(String(50), nullable=True, index=True)  # Applied coupon code (None if no coupon)
    coupon_discount = Column(Float, default=0.0)  # Discount from coupon
    total_amount = Column(Float, nullable=False)  # Final amount paid
    
    # Payment details
    payment_method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.RAZORPAY)
    payment_status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.NOT_INITIATED, index=True)
    razorpay_order_id = Column(String(255), nullable=False, unique=True, index=True)  # Razorpay order ID
    razorpay_payment_id = Column(String(255), nullable=True, unique=True, index=True)  # Razorpay payment ID (filled after payment completion)
    razorpay_signature = Column(String(255), nullable=True)  # Razorpay signature for verification (filled after payment completion)
    payment_date = Column(DateTime(timezone=True), nullable=True)  # Payment date (filled after payment completion)
    
    # Order status tracking
    order_status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.CREATED, index=True)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Additional notes
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Transfer tracking fields
    linked_from_order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)  # Original order if this is a transferred copy
    is_transferred_copy = Column(Boolean, nullable=False, default=False, index=True)  # True if this order was created from transfer
    transferred_at = Column(DateTime(timezone=True), nullable=True)  # When transfer occurred

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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # User who placed the order
    # These foreign keys reference entities (we use OrderSnapshot for data integrity)
    # RESTRICT prevents deletion if referenced, ensuring IDs never become NULL
    product_id = Column(Integer, ForeignKey("products.ProductId", ondelete="RESTRICT"), nullable=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=True, index=True)
    address_id = Column(Integer, ForeignKey("addresses.id", ondelete="RESTRICT"), nullable=True)
    
    # Product snapshot at time of order (from snapshot table)
    snapshot_id = Column(Integer, ForeignKey("order_snapshots.id"), nullable=False)
    
    quantity = Column(Integer, default=1)
    unit_price = Column(Float, nullable=False)  # SpecialPrice at time of order (final price per unit)
    
    # Per-item status tracking (for different addresses in couple/family packs)
    order_status = Column(Enum(OrderStatus), nullable=False, default=OrderStatus.CREATED, index=True)
    status_updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Technician and scheduling information (per item, since items can have different addresses)
    scheduled_date = Column(DateTime(timezone=True), nullable=True)  # When technician will visit for this item
    technician_name = Column(String(100), nullable=True)  # Technician assigned to this item
    technician_contact = Column(String(20), nullable=True)  # Technician contact for this item
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Transfer tracking fields
    linked_from_order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True)  # Original order item if this is a transferred copy
    transferred_at = Column(DateTime(timezone=True), nullable=True)  # When transfer occurred
    
    # Relationships
    order = relationship("Order", backref="items")
    user = relationship("User")
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
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)  # User who placed the order
    
    # Snapshot of product details at order time
    product_data = Column(JSON, nullable=False)  # {ProductId, Name, Price, SpecialPrice, plan_type, category, etc.}
    
    # Snapshot of member details at order time
    member_data = Column(JSON, nullable=False)  # {id, name, relation, age, gender, mobile}
    
    # Snapshot of address details at order time
    address_data = Column(JSON, nullable=False)  # {id, address_label, street_address, city, state, postal_code, etc.}
    
    # Snapshot of cart item details (not required, can be empty)
    cart_item_data = Column(JSON, nullable=True)  # Original cart item data if needed (optional)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Transfer tracking fields
    linked_from_snapshot_id = Column(Integer, ForeignKey("order_snapshots.id", ondelete="SET NULL"), nullable=True)  # Original snapshot if this is a transferred copy
    transferred_at = Column(DateTime(timezone=True), nullable=True)  # When transfer occurred
    
    # Relationships
    order = relationship("Order", backref="snapshots")
    user = relationship("User")


class OrderStatusHistory(Base):
    """
    Order status history - tracks all status changes for an order.
    """
    __tablename__ = "order_status_history"

    id = Column(Integer, primary_key=True, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="CASCADE"), nullable=False, index=True)
    order_item_id = Column(Integer, ForeignKey("order_items.id", ondelete="CASCADE"), nullable=True, index=True)  # NULL for order-level status
    status = Column(Enum(OrderStatus), nullable=False, index=True)
    previous_status = Column(Enum(OrderStatus), nullable=True)  # NULL for initial status
    notes = Column(Text, nullable=False)  # Additional notes about status change
    changed_by = Column(String(100), nullable=False)  # Who changed the status (user_id or "system")
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    order = relationship("Order", backref="status_history")
    order_item = relationship("OrderItem", backref="status_history")


