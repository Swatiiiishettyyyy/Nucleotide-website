"""
Order schemas for request/response models.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class CreateOrderRequest(BaseModel):
    """Request to create order from cart"""
    address_id: Optional[int] = Field(
        None,
        description="Optional shipping address ID. If omitted, the address from selected cart items will be used."
    )
    cart_item_ids: List[int] = Field(..., description="List of cart item IDs to order")


class OrderItemData(BaseModel):
    """Order item data"""
    order_item_id: int
    product_id: int
    product_name: str
    member_id: int
    member_name: str
    address_id: int
    address_label: Optional[str] = None
    quantity: int
    unit_price: float
    total_price: float


class OrderResponse(BaseModel):
    """Order response"""
    order_id: int
    order_number: str
    user_id: int
    address_id: int
    total_amount: float
    payment_status: str
    order_status: str
    razorpay_order_id: Optional[str] = None
    created_at: datetime
    items: List[OrderItemData]


class RazorpayOrderResponse(BaseModel):
    """Razorpay order creation response"""
    razorpay_order_id: str
    amount: float
    currency: str = "INR"
    order_id: int
    order_number: str


class VerifyPaymentRequest(BaseModel):
    """Razorpay payment verification request"""
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    order_id: int


class PaymentVerificationResponse(BaseModel):
    """Payment verification response"""
    status: str
    message: str
    order_id: int
    order_number: str
    payment_status: str


class UpdateOrderStatusRequest(BaseModel):
    """Request to update order status"""
    order_id: int
    status: str  # OrderStatus enum value
    notes: Optional[str] = None
    scheduled_date: Optional[datetime] = None
    technician_name: Optional[str] = None
    technician_contact: Optional[str] = None
    lab_name: Optional[str] = None


class OrderTrackingResponse(BaseModel):
    """Order tracking information"""
    order_id: int
    order_number: str
    current_status: str
    status_history: List[dict]
    estimated_completion: Optional[datetime] = None

