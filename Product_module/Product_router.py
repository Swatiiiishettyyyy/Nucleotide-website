from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import logging

from .Product_model import Product, PlanType
from deps import get_db
from Login_module.Utils.rate_limiter import get_client_ip
from .Product_schema import (
    ProductCreate,
    ProductListResponse,
    ProductSingleResponse,
)
from .category_service import resolve_category

logger = logging.getLogger(__name__)

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
    products = db.query(Product).filter(Product.is_deleted == False).all()

    return {
        "status": "success",
        "message": "Product list fetched successfully.",
        "data": products,
    }


@router.get("/detail/{ProductId}", response_model=ProductSingleResponse)
def get_product_detail(ProductId: int, request: Request, db: Session = Depends(get_db)):
    client_ip = get_client_ip(request) if request else None
    product = db.query(Product).filter(Product.ProductId == ProductId, Product.is_deleted == False).first()

    if not product:
        logger.warning(
            f"Product detail failed - Product not found | "
            f"Product ID: {ProductId} | IP: {client_ip}"
        )
        raise HTTPException(status_code=404, detail="Product not found")

    return {
        "status": "success",
        "message": "Product fetched successfully.",
        "data": product,
    }