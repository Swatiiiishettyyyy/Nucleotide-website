from pydantic import BaseModel
from typing import Optional, List

class CartAdd(BaseModel):
    product_id: int
    quantity: int = 1


class CartUpdate(BaseModel):
    quantity: int


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
    delivery_charge: float
    grand_total: float

    class Config:
        orm_mode = True


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