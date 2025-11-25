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
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def initialize_database():
    """Initialize database tables and run migrations. Handles connection errors gracefully."""
    try:
        logger.info("Initializing database tables...")
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables initialized successfully")
    except OperationalError as e:
        logger.error(f"Failed to connect to database during table creation: {e}")
        logger.warning("Application will continue, but database operations may fail until connection is restored")
    except Exception as e:
        logger.error(f"Unexpected error during table creation: {e}", exc_info=True)
    
    try:
        logger.info("Running database migrations...")
        run_startup_migrations(engine)
        logger.info("Database migrations completed successfully")
    except OperationalError as e:
        logger.error(f"Failed to connect to database during migrations: {e}")
        logger.warning("Migrations will be retried on next startup")
    except Exception as e:
        logger.error(f"Unexpected error during migrations: {e}", exc_info=True)
    
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)