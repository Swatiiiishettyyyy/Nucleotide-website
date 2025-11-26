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
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from starlette import status
from database import engine
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
from alembic_runner import run_migrations
from Category_module.Category_router import router as category_router
from Category_module.bootstrap import seed_default_categories
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def initialize_database():
    """
    Initialize database by running Alembic migrations and seeding default data.
    Handles connection errors gracefully.
    """
    # Run Alembic migrations (handles all schema creation and updates)
    try:
        logger.info("Running database migrations...")
        run_migrations()
        logger.info("Database migrations completed successfully")
    except OperationalError as e:
        logger.error(f"Failed to connect to database during migrations: {e}")
        logger.warning("Migrations will be retried on next startup")
    except Exception as e:
        logger.error(f"Unexpected error during migrations: {e}", exc_info=True)
    
    # Seed default categories
    try:
        logger.info("Seeding default categories...")
        seed_default_categories()
        logger.info("Default categories seeded successfully")
    except OperationalError as e:
        logger.error(f"Failed to connect to database during category seeding: {e}")
        logger.warning("Category seeding will be retried on next startup")
    except Exception as e:
        logger.error(f"Unexpected error during category seeding: {e}", exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("Starting application...")
    initialize_database()
    start_scheduler()
    logger.info("Application started successfully")
    yield
    # Shutdown
    logger.info("Shutting down application...")
    shutdown_scheduler()
    logger.info("Application shutdown complete")


app = FastAPI(title="Nucleotide API", version="1.0.0", lifespan=lifespan)


def _format_validation_errors(exc):
    """Return consistent error structure for 422 responses."""
    detail_list = []
    errors = exc.errors() if hasattr(exc, "errors") else []

    for err in errors:
        loc = err.get("loc", [])
        source = loc[0] if loc else "body"
        field = loc[-1] if len(loc) > 1 else loc[0] if loc else None
        detail_list.append({
            "source": source,
            "field": field,
            "message": err.get("msg"),
            "type": err.get("type")
        })
    return detail_list


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError):
    detail_list = _format_validation_errors(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Request validation failed.",
            "details": detail_list
        }
    )


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request: Request, exc: ValidationError):
    detail_list = _format_validation_errors(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation failed.",
            "details": detail_list
        }
    )

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

# Session management endpoints
from Login_module.Device.Device_session_router import router as session_router
app.include_router(session_router)



# ============================================================
# 6. ROOT ENDPOINT
# ============================================================
@app.get("/")
def root():
    """Root endpoint with API information"""
    return {
        "status": "success",
        "message": "Nucleoseq Unified API",
        "version": "3.0.0",
        "endpoints": {
            "auth": "/auth",
            "profile": "/profile",
            "products": "/products",
            "categories": "/categories",
            "cart": "/cart",
            "address": "/address",
            "member": "/member",
            "orders": "/orders",
            "audit": "/audit",
            "sessions": "/sessions"
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }



# ============================================================
# 7. HEALTH CHECK ENDPOINT
# ============================================================
@app.get("/health")
def health_check():
    """Health check endpoint for container orchestration"""
    return {
        "status": "healthy",
        "service": "Nucleoseq Unified API"
    }



# ============================================================
# 8. RUN APPLICATION
# ============================================================
if __name__ == "__main__":
    import uvicorn
    
    print("\n" + "="*60)
    print("Starting Nucleoseq Unified API Server")
    print("="*60)
    print("Server will be available at: http://0.0.0.0:8030")
    print("API Documentation: http://0.0.0.0:8030/docs")
    print("ReDoc Documentation: http://0.0.0.0:8030/redoc")
    print("="*60 + "\n")
    
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8030,
        reload=False
    )

