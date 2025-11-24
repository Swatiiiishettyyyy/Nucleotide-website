from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, validator

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
    Name: str
    Price: float
    SpecialPrice: float
    ShortDescription: str
    Discount: Optional[str] = None
    Description: Optional[str] = None
    Images: Optional[List[str]] = None
    plan_type: PlanTypeEnum = PlanTypeEnum.SINGLE
    max_members: Optional[int] = None
    category_id: Optional[int] = None

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