from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from Category_module.Category_schema import (
    CategoryCreate,
    CategoryListResponse,
    CategorySingleResponse,
)
from Product_module.Product_model import Category
from Product_module.category_service import create_category
from deps import get_db

router = APIRouter(prefix="/categories", tags=["Categories"])


@router.get("/", response_model=CategoryListResponse)
def list_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).order_by(Category.name.asc()).all()
    return {
        "status": "success",
        "message": "Category list fetched successfully.",
        "data": categories,
    }


@router.post(
    "/",
    response_model=CategorySingleResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_category(payload: CategoryCreate, db: Session = Depends(get_db)):
    category = create_category(db, payload.name)
    return {
        "status": "success",
        "message": "Category created successfully.",
        "data": category,
    }

