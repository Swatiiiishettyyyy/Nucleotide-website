from pydantic import BaseModel
from typing import List, Optional


# Create Body
class ProductCreate(BaseModel):
    Name: str
    Price: float
    SpecialPrice: float
    ShortDescription: str
    Discount: Optional[str] = None
    Description: Optional[str] = None
    Images: Optional[List[str]] = None


# Single Product Response Shape
class ProductResponse(BaseModel):
    ProductId: int
    Name: str
    Price: float
    SpecialPrice: float
    ShortDescription: str
    Discount: Optional[str] = None
    Description: Optional[str] = None
    Images: Optional[List[str]] = None

    class Config:
        orm_mode = True


# Wrapper for Product List Response
class ProductListResponse(BaseModel):
    status: str
    message: str
    data: List[ProductResponse]


# Wrapper for Single Product (Add / Update)
class ProductSingleResponse(BaseModel):
    status: str
    message: str
    data: ProductResponse