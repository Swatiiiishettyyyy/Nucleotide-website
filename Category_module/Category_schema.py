from pydantic import BaseModel, validator


class CategoryCreate(BaseModel):
    name: str

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
        orm_mode = True


class CategoryListResponse(BaseModel):
    status: str
    message: str
    data: list[CategoryResponse]


class CategorySingleResponse(BaseModel):
    status: str
    message: str
    data: CategoryResponse

