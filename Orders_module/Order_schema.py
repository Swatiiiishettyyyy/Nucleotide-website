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


class AddressTrackingData(BaseModel):
    """Tracking data grouped by address"""
    address_id: Optional[int] = None  # Can be NULL if address was deleted (snapshot preserves data)
    address_label: Optional[str] = None
    address_details: Optional[dict] = None
    members: List[dict]  # List of members at this address
    current_status: str
    status_history: List[dict]


class OrderTrackingResponse(BaseModel):
    """Order tracking information"""
    order_id: int
    order_number: str
    current_status: str  # Overall order status
    status_history: List[dict]  # Order-level status history
    address_tracking: List[AddressTrackingData]  # Per-address tracking


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

