"""
Main FastAPI application entry point.
"""
import os
import sys
import time
import logging
import warnings
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import ValidationError
from starlette import status
from starlette.middleware.base import BaseHTTPMiddleware
from sqlalchemy.exc import OperationalError

# Load environment variables
load_dotenv()

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    force=True
)

logger = logging.getLogger(__name__)

# Database and migrations
from database import Base, engine
from alembic_runner import run_migrations
from Category_module.bootstrap import seed_default_categories

# Import models to register with SQLAlchemy Base
from Banner_module.Banner_model import Banner
from Consent_module.Consent_model import UserConsent, ConsentProduct
from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
from Member_module.Member_transfer_model import MemberTransferLog
from GeneticTest_module.GeneticTest_model import GeneticTestParticipant

# Import Google Meet API models to register with SQLAlchemy Base
try:
    from gmeet_api.models import (
        CounsellorToken,
        CounsellorBooking,
        CounsellorActivityLog,
        CounsellorGmeetList
    )
except ImportError:
    logger.warning("Failed to import gmeet_api models. Google Meet tables may not be created.")

# Routers
from Address_module.Address_router import router as address_router
from Banner_module.Banner_router import router as banner_router
from Cart_module.Cart_router import router as cart_router
from Category_module.Category_router import router as category_router
from Consent_module.Consent_router import router as consent_router
from Login_module.OTP.OTP_router import router as otp_router
from Login_module.Device.Device_session_router import router as session_router
from Login_module.Utils.audit_query import router as audit_router
from Member_module.Member_router import router as member_router
from Orders_module.Order_router import router as order_router
from Product_module.Product_router import router as product_router
from Profile_module.Profile_router import router as profile_router

# Google Meet API router
try:
    from gmeet_api.router import router as gmeet_router
except ImportError:
    logger.warning("Failed to import gmeet_api router. Google Meet endpoints will not be available.")
    gmeet_router = None

# Scheduler
from Login_module.Device.scheduler import start_scheduler, shutdown_scheduler


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log HTTP requests and responses with status codes."""
    
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else "unknown"
        start_time = time.time()
        
        # Log incoming request
        logger.info(f"→ {request.method} {request.url.path} | IP: {client_ip}")
        
        try:
            response = await call_next(request)
            duration = time.time() - start_time
            
            # Get status code - ensure we can access it
            try:
                status_code = response.status_code
            except AttributeError:
                # Fallback if status_code is not directly accessible
                status_code = getattr(response, 'status_code', 200)
            
            # Determine status code category and emoji
            if 200 <= status_code < 300:
                status_emoji = "✅"
                status_category = "SUCCESS"
            elif 300 <= status_code < 400:
                status_emoji = "⚠️"
                status_category = "REDIRECT"
            elif 400 <= status_code < 500:
                status_emoji = "❌"
                status_category = "CLIENT_ERROR"
            else:
                status_emoji = "💥"
                status_category = "SERVER_ERROR"
            
            # Log response with detailed status code information - make it more visible
            log_message = (
                f"{status_emoji} {request.method} {request.url.path} | "
                f"Status: {status_code} ({status_category}) | "
                f"Duration: {duration:.3f}s | "
                f"IP: {client_ip}"
            )
            logger.info(log_message)
            
            # Also print to console for better visibility
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {log_message}")
            
            return response
        except Exception as e:
            duration = time.time() - start_time
            error_message = (
                f"💥 {request.method} {request.url.path} | "
                f"Status: 500 (SERVER_ERROR) | "
                f"Error: {str(e)} | "
                f"Duration: {duration:.3f}s | "
                f"IP: {client_ip}"
            )
            logger.error(error_message)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {error_message}")
            raise


def initialize_database():
    """
    Initialize database by running Alembic migrations and seeding default data.
    Handles connection errors gracefully.
    
    Note: For fresh databases, run `python create_all_tables.py` first to create all tables.
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
    """Lifespan event handler for startup and shutdown."""
    logger.info("Starting application...")
    initialize_database()
    start_scheduler()
    logger.info("Application started successfully")
    yield
    logger.info("Shutting down application...")
    shutdown_scheduler()
    logger.info("Application shutdown complete")


# Initialize FastAPI app
app = FastAPI(
    title="Nucleotide API",
    version="1.0.0",
    lifespan=lifespan
)


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
    """Handle FastAPI request validation errors."""
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
    """Handle Pydantic validation errors."""
    detail_list = _format_validation_errors(exc)
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "status": "error",
            "message": "Validation failed.",
            "details": detail_list
        }
    )


# CORS configuration
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")
if ALLOWED_ORIGINS == ["*"]:
    warnings.warn("CORS is set to allow all origins. This is not recommended for production.")

# Middleware
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
)

# Include routers
app.include_router(otp_router)
app.include_router(profile_router)
app.include_router(product_router)
app.include_router(category_router)
app.include_router(cart_router)
app.include_router(address_router)
app.include_router(banner_router)
app.include_router(consent_router)
app.include_router(member_router)
app.include_router(order_router)
app.include_router(audit_router)
app.include_router(session_router)

# Include Google Meet API router if available
if gmeet_router:
    app.include_router(gmeet_router)
# API Endpoints
@app.get("/")
def root():
    """Root endpoint with API information."""
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
            "banners": "/banners",
            "consent": "/consent",
            "member": "/member",
            "orders": "/orders",
            "audit": "/audit",
            "sessions": "/sessions",
            "gmeet": "/gmeet"
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }


@app.get("/health")
def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "Nucleoseq Unified API"
    }


# Run application
if __name__ == "__main__":
    import uvicorn
    
    # Configure uvicorn loggers
    uvicorn_access_logger = logging.getLogger("uvicorn.access")
    uvicorn_access_logger.setLevel(logging.INFO)
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)
    
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
        reload=False,
        log_level="info",
        access_log=True,
        use_colors=True
    )

