import sys
import os
import logging
from dotenv import load_dotenv

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

load_dotenv()

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

from contextlib import asynccontextmanager
from fastapi import FastAPI
from database import Base, engine
from  Address_module.Address_router import router as address_router
from Cart_module.Cart_router import router as cart_router
from Login_module.OTP.OTP_router import router as otp_router
from Member_module.Member_router import router as member_router
from Product_module.Product_router import router as product_router
from Profile_module.Profile_router import router as profile_router
from fastapi.middleware.cors import CORSMiddleware
from Login_module.Device.scheduler import start_scheduler, shutdown_scheduler

# Import order models so they're registered with SQLAlchemy Base
from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
from database_migrations import run_startup_migrations
from Category_module.Category_router import router as category_router
from Category_module.bootstrap import seed_default_categories

Base.metadata.create_all(bind=engine)
run_startup_migrations(engine)
seed_default_categories()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()


app = FastAPI(title="Nucleotide API", version="1.0.0", lifespan=lifespan)

# CORS configuration - restrict origins in production
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if ALLOWED_ORIGINS == ["*"]:
    # In production, you should set specific origins
    import warnings
    warnings.warn("CORS is set to allow all origins. This is not recommended for production.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

app.include_router(otp_router)
app.include_router(profile_router)
app.include_router(product_router)
app.include_router(category_router)
app.include_router(cart_router)
app.include_router(address_router)
app.include_router(member_router)

# Orders module
from Orders_module.Order_router import router as order_router
app.include_router(order_router)

# Audit log query endpoints
from Login_module.Utils.audit_query import router as audit_router
app.include_router(audit_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)