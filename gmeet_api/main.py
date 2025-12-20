"""
Main FastAPI application for Google Meet API.
This file can be run standalone or integrated into a larger FastAPI application.
"""
import os
import logging
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load environment variables.
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
ENV_CANDIDATES = [
    BASE_DIR / ".env",
    PROJECT_ROOT / ".env",
    BASE_DIR.parent / ".env",
]

for env_path in ENV_CANDIDATES:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Google Meet API",
    description="Medical Counsellor Appointment Booking System with Google Meet Integration",
    version="1.0.0"
)

# CORS configuration - always allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Initialize database tables
try:
    from .database import Base, engine
    from .models import (
        CounsellorToken,
        CounsellorBooking,
        CounsellorActivityLog,
        CounsellorGmeetList
    )
except ImportError:
    # Fallback for when running directly (e.g., uvicorn main:app)
    from database import Base, engine
    from models import (
        CounsellorToken,
        CounsellorBooking,
        CounsellorActivityLog,
        CounsellorGmeetList
    )

# Create tables
try:
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize database tables: {e}")

# Include router
try:
    from .router import router
except ImportError:
    # Fallback for when running directly
    from router import router
app.include_router(router)

# Root endpoint
@app.get("/")
def root():
    """Root endpoint with API information."""
    return {
        "status": "success",
        "message": "Google Meet API for Medical Counsellor Appointments",
        "version": "1.0.0",
        "endpoints": {
            "universal_connect": "/gmeet/counsellor/connect",
            "oauth_connect": "/gmeet/auth/connect/{counsellor_id}",
            "oauth_callback": "/gmeet/auth/callback",
            "availability": "/gmeet/availability",
            "book": "/gmeet/book",
            "delete_appointment": "/gmeet/appointment/{counsellor_id}/{booking_id}"
        },
        "docs": "/docs",
        "redoc": "/redoc"
    }


# Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint for container orchestration."""
    return {
        "status": "healthy",
        "service": "google-meet-api"
    }


if __name__ == "__main__":
    import uvicorn
    # Port 8030 matches Nucleotide-website_v11 dockerfile
    port = int(os.getenv("PORT", 8030))
    uvicorn.run(app, host="0.0.0.0", port=port)

