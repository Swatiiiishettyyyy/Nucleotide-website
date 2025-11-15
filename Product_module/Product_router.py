from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from Product_model import Product
from database import SessionLocal
from deps import get_db
from Product_schema import (
    ProductCreate,
    ProductResponse,
    ProductListResponse,
    ProductSingleResponse
)

router = APIRouter(prefix="/products", tags=["Products"])

@router.post("/addProduct", response_model=ProductSingleResponse)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    new_product = Product(**payload.dict())
    db.add(new_product)
    db.commit()
    db.refresh(new_product)

    return {
        "status": "success",
        "message": "Product created successfully.",
        "data": new_product
    }


@router.get("/viewProduct", response_model=ProductListResponse)
def get_products(db: Session = Depends(get_db)):
    products = db.query(Product).all()

    return {
        "status": "success",
        "message": "Product list fetched successfully.",
        "data": products
    }

from fastapi import HTTPException


@router.get("/detail/{ProductId}", response_model=ProductSingleResponse)
def get_product_detail(ProductId: int, db: Session = Depends(get_db)):
    # Use ProductId as in the model
    product = db.query(Product).filter(Product.ProductId == ProductId).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "status": "success",
        "message": "Product fetched successfully.",
        "data": product
    }