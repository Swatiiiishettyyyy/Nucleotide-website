from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from .Product_model import Product, PlanType
from deps import get_db
from .Product_schema import (
    ProductCreate,
    ProductListResponse,
    ProductSingleResponse,
)
from .category_service import resolve_category

router = APIRouter(prefix="/products", tags=["Products"])


@router.post("/addProduct", response_model=ProductSingleResponse)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    category = resolve_category(db, payload.category_id)

    new_product = Product(
        Name=payload.Name,
        Price=payload.Price,
        SpecialPrice=payload.SpecialPrice,
        ShortDescription=payload.ShortDescription,
        Discount=payload.Discount,
        Description=payload.Description,
        Images=payload.Images,
        plan_type=PlanType(payload.plan_type.value),
        max_members=payload.max_members,
        category_id=category.id,
    )
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "status": "success",
        "message": "Product created successfully.",
        "data": new_product,
    }


@router.get("/viewProduct", response_model=ProductListResponse)
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()

    return {
        "status": "success",
        "message": "Product list fetched successfully.",
        "data": products,
    }


@router.get("/detail/{ProductId}", response_model=ProductSingleResponse)
def get_product_detail(ProductId: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.ProductId == ProductId).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "status": "success",
        "message": "Product fetched successfully.",
        "data": product,
    }