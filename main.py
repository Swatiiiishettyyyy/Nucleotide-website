import sys
import os
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

from fastapi import FastAPI
from database import Base, engine
from  Address_module.Address_router import router as address_router
from Cart_module.Cart_router import router as cart_router
from Login_module.OTP.OTP_router import router as otp_router
from Member_module.Member_router import router as member_router
from Product_module.Product_router import router as product_router
from Profile_module.Profile_router import router as profile_router
from fastapi.middleware.cors import CORSMiddleware
Base.metadata.create_all(bind=engine)
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # allow all domains (React, Postman, mobile)
    allow_credentials=True,
    allow_methods=["*"],        # GET, POST, PUT, DELETE...
    allow_headers=["*"],        # Authorization, Content-Type...
)
app.include_router(otp_router)
app.include_router(profile_router)
app.include_router(product_router)
app.include_router(cart_router)
app.include_router(address_router)
app.include_router(member_router)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)