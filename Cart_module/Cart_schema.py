from pydantic import BaseModel, validator
from typing import Optional, List, Union

class CartAdd(BaseModel):
    product_id: int
    address_id: Union[int, List[int]]  # Single address (shared) or list of addresses (one per member)
    member_ids: List[int]  # List of member IDs - for couple: 2 members, for family: 3-4 members (3 mandatory + 1 optional)
    quantity: int = 1
    
    @validator('member_ids')
    def validate_member_ids(cls, v):
        if not v or len(v) == 0:
            raise ValueError('At least one member_id is required')
        if len(v) > 4:
            raise ValueError('Maximum 4 members allowed per product')
        return v
    
    @validator('address_id')
    def normalize_address_id(cls, v):
        """Normalize address_id to always be a list for easier processing."""
        if isinstance(v, int):
            return [v]
        if isinstance(v, list):
            if not v:
                raise ValueError('At least one address_id is required')
            if len(v) > 4:
                raise ValueError('Maximum 4 addresses allowed (one per member)')
            return v
        raise ValueError('address_id must be an integer or a list of integers')


class CartUpdate(BaseModel):
    quantity: int
    
    @validator('quantity')
    def validate_quantity(cls, v):
        if v < 1:
            raise ValueError('Quantity must be at least 1')
        return v


class CartItemResponse(BaseModel):
    cart_id: int
    user_id: Optional[int] = None
    product_id: int
    quantity: int
    price: float
    special_price: float
    total_amount: float
    cart_items_count: int

    class Config:
        orm_mode = True


# ---------------- NEW CART RESPONSE SCHEMAS ---------------- #

class CartItemDetail(BaseModel):
    cart_item_id: int
    product_id: int
    product_name: str
    product_image: str
    price: float
    special_price: float
    quantity: int
    total_amount: float

    class Config:
        orm_mode = True


class CartSummary(BaseModel):
    cart_id: int
    total_items: int
    subtotal_amount: float
    discount_amount: float
    coupon_amount: float = 0.0  # Discount from coupon
    coupon_code: Optional[str] = None  # Applied coupon code
    you_save: float = 0.0  # Total savings (discount + coupon)
    delivery_charge: float
    grand_total: float

    class Config:
        orm_mode = True


class ApplyCouponRequest(BaseModel):
    coupon_code: str
    
    @validator('coupon_code')
    def validate_coupon_code(cls, v):
        if not v or not v.strip():
            raise ValueError('Coupon code is required')
        return v.strip().upper()


class CartData(BaseModel):
    cart_summary: CartSummary
    cart_items: List[CartItemDetail]

    class Config:
        orm_mode = True


class CartResponse(BaseModel):
    status: str
    message: str
    data: CartData

    class Config:
        orm_mode = True