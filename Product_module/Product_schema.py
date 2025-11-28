from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field, validator

from Category_module.Category_schema import (
    CategoryListResponse,
    CategoryResponse,
    CategorySingleResponse,
)


class PlanTypeEnum(str, Enum):
    SINGLE = "single"
    COUPLE = "couple"
    FAMILY = "family"


class ProductCreate(BaseModel):
    Name: str = Field(..., description="Product name", min_length=1, max_length=200)
    Price: float = Field(..., description="Product price (MRP)", gt=0)
    SpecialPrice: float = Field(..., description="Product special price (sale price)", gt=0)
    ShortDescription: str = Field(..., description="Short description of the product", min_length=1, max_length=500)
    Discount: str = Field(..., description="Discount information (e.g., '10%')", max_length=50)
    Description: str = Field(..., description="Full product description", max_length=2000)
    Images: List[str] = Field(..., description="List of product image URLs", min_items=1)
    plan_type: PlanTypeEnum = Field(..., description="Product plan type (single/couple/family)")
    max_members: int = Field(..., description="Maximum members allowed (1-4)", ge=1, le=4)
    category_id: int = Field(..., description="Category ID", gt=0)

    @validator("max_members", always=True)
    def set_default_max_members(cls, value: Optional[int], values: dict) -> int:
        if value:
            return value
        plan_type = values.get("plan_type", PlanTypeEnum.SINGLE)
        return {
            PlanTypeEnum.SINGLE: 1,
            PlanTypeEnum.COUPLE: 2,
            PlanTypeEnum.FAMILY: 4,
        }[plan_type]


class ProductResponse(BaseModel):
    ProductId: int
    Name: str
    Price: float
    SpecialPrice: float
    ShortDescription: str
    Discount: Optional[str] = None
    Description: Optional[str] = None
    Images: Optional[List[str]] = None
    plan_type: PlanTypeEnum
    max_members: int
    category: CategoryResponse

    class Config:
        orm_mode = True


class ProductListResponse(BaseModel):
    status: str
    message: str
    data: List[ProductResponse]


class ProductSingleResponse(BaseModel):
    status: str
    message: str
    data: ProductResponse