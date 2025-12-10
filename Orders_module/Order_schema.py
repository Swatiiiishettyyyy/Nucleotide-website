"""
Order schemas for request/response models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateOrderRequest(BaseModel):
    """Request to create order from all cart items for the user"""
    cart_id: int = Field(..., description="Cart ID (primary cart item ID - used as reference. All cart items for the authenticated user will be included in the order)", gt=0)


class MemberDetails(BaseModel):
    """Member details"""
    member_id: Optional[int] = None
    name: str
    relation: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    dob: Optional[str] = None
    mobile: Optional[str] = None


class AddressDetails(BaseModel):
    """Address details"""
    address_id: Optional[int] = None
    address_label: Optional[str] = None
    street_address: Optional[str] = None
    landmark: Optional[str] = None
    locality: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class MemberAddressMapping(BaseModel):
    """Member-address mapping with full details"""
    member: MemberDetails
    address: AddressDetails
    order_item_id: int
    quantity: int
    unit_price: float  # SpecialPrice at time of order
    order_status: str  # Per-item status
    status_updated_at: Optional[datetime] = None
    scheduled_date: Optional[datetime] = None  # When technician will visit for this item
    technician_name: Optional[str] = None  # Technician assigned to this item
    technician_contact: Optional[str] = None  # Technician contact for this item


class OrderItemData(BaseModel):
    """Order item data grouped by product"""
    product_id: Optional[int] = None  # Can be NULL if product was deleted (snapshot preserves data)
    product_name: str
    group_id: Optional[str] = None  # Group ID to distinguish different packs of same product
    member_ids: List[int]  # List of member IDs in this product group
    address_ids: List[int]  # List of unique address IDs used
    member_address_map: List[MemberAddressMapping]  # Full member-address mapping with details
    quantity: int
    total_amount: float


class OrderResponse(BaseModel):
    """Order response"""
    order_id: int
    order_number: str
    user_id: int
    address_id: Optional[int] = None  # Can be NULL if address was deleted (snapshot preserves data)
    subtotal: Optional[float] = None
    discount: Optional[float] = None
    coupon_code: Optional[str] = None
    coupon_discount: Optional[float] = None
    delivery_charge: Optional[float] = None
    total_amount: float
    payment_status: str
    order_status: str
    razorpay_order_id: Optional[str] = None
    created_at: datetime
    items: List[OrderItemData]


class RazorpayOrderResponse(BaseModel):
    """Razorpay order creation response"""
    order_id: int
    order_number: str
    razorpay_order_id: str
    amount: float
    currency: str = "INR"


class VerifyPaymentRequest(BaseModel):
    """Razorpay payment verification request"""
    razorpay_order_id: str = Field(..., description="Razorpay order ID from create order response", min_length=1)
    razorpay_payment_id: str = Field(..., description="Razorpay payment ID from payment gateway", min_length=1)
    razorpay_signature: str = Field(..., description="Razorpay signature for verification", min_length=1)
    order_id: int = Field(..., description="Order ID from create order response", gt=0)


class PaymentVerificationResponse(BaseModel):
    """Payment verification response"""
    status: str
    message: str
    order_id: int
    order_number: str
    payment_status: str


class UpdateOrderStatusRequest(BaseModel):
    """Request to update order status - flexible status transitions allowed"""
    status: str = Field(..., description="OrderStatus enum value (can transition from any stage to any stage)", min_length=1)
    notes: str = Field(..., description="Additional notes about status change")
    order_item_id: Optional[int] = Field(None, description="Update specific order item (optional)", gt=0)
    address_id: Optional[int] = Field(None, description="Update all items with this address (optional)", gt=0)
    scheduled_date: Optional[datetime] = Field(None, description="Scheduled date for technician visit (optional)")
    technician_name: Optional[str] = Field(None, description="Technician name (optional)")
    technician_contact: Optional[str] = Field(None, description="Technician contact (optional)")


class ProductPlanInfo(BaseModel):
    """Product/Plan information with pricing"""
    product_id: Optional[int] = None
    product_name: str
    plan_type: Optional[str] = None  # single, couple, family
    quantity: int
    unit_price: float  # Price per unit at time of order


class OrderItemTracking(BaseModel):
    """Order item tracking - clean mapping of member, address, product, and status"""
    order_item_id: int
    product_id: Optional[int] = None  # Product ID reference
    product_name: str  # Product name
    plan_type: Optional[str] = None  # single, couple, family
    group_id: Optional[str] = None  # Group ID to distinguish different packs of same product
    quantity: int  # Quantity for this product
    unit_price: float  # Unit price for this product
    member: MemberDetails  # Member details for this order item
    address: AddressDetails  # Address details for this order item
    current_status: str  # Current status of this order item
    previous_status: Optional[str] = None  # Previous status of this order item
    status_updated_at: Optional[datetime] = None  # When status was last updated
    scheduled_date: Optional[datetime] = None  # Scheduled date for this order item
    technician_name: Optional[str] = None  # Technician assigned to this order item
    technician_contact: Optional[str] = None  # Technician contact for this order item
    created_at: Optional[datetime] = None  # When this order item was created
    status_history: List[dict]  # Complete status history for this order item (sorted by date, newest first)


class ProductGroupSummary(BaseModel):
    """Summary of products in the order - grouped to avoid redundancy"""
    product_id: Optional[int] = None
    product_name: str
    plan_type: Optional[str] = None
    quantity: int  # Total quantity of this product
    unit_price: float
    order_item_ids: List[int]  # Order item IDs that belong to this product group

class OrderTrackingResponse(BaseModel):
    """Order tracking information - clean and clear order details grouped by order items"""
    order_id: int
    order_number: str
    order_date: datetime  # When order was placed
    payment_status: str  # pending, completed, failed, cancelled
    current_status: str  # Overall order status (order_confirmed, scheduled, etc.)
    # Order pricing breakdown
    subtotal: float  # Subtotal before discounts
    product_discount: Optional[float] = None  # Discount from product pricing
    coupon_code: Optional[str] = None
    coupon_discount: float  # Discount from coupon
    delivery_charge: float
    total_amount: float  # Final amount paid
    # Order items - clean mapping of member, address, product, and status, grouped by product
    order_items: List[OrderItemTracking]  # All order items grouped by product_id (sorted)


class OrderItemTrackingResponse(BaseModel):
    """Per-order-item tracking information"""
    order_id: int
    order_number: str
    order_item_id: int
    current_status: str
    status_history: List[dict]
    member: dict
    address: dict
    product: dict
    quantity: int
    unit_price: float
    scheduled_date: Optional[datetime] = None
    technician_name: Optional[str] = None
    technician_contact: Optional[str] = None

