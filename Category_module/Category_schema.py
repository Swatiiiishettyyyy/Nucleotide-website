from pydantic import BaseModel, Field, validator


class CategoryCreate(BaseModel):
    name: str = Field(..., description="Category name", min_length=1, max_length=100)

    @validator("name")
    def validate_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Category name cannot be empty.")
        return value


class CategoryResponse(BaseModel):
    id: int
    name: str

    class Config:
        from_attributes = True


class CategoryListResponse(BaseModel):
    status: str
    message: str
    data: list[CategoryResponse]


class CategorySingleResponse(BaseModel):
    status: str
    message: str
    data: CategoryResponse

