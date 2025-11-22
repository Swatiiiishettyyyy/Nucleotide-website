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

Base.metadata.create_all(bind=engine)
app = FastAPI(title="Nucleotide API", version="1.0.0")

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
app.include_router(cart_router)
app.include_router(address_router)
app.include_router(member_router)

# Audit log query endpoints
from Login_module.Utils.audit_query import router as audit_router
app.include_router(audit_router)


@app.on_event("startup")
async def startup_event():
    """Start background scheduler on application startup"""
    start_scheduler()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop background scheduler on application shutdown"""
    shutdown_scheduler()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)