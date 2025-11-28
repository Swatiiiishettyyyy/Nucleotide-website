# app/models/address.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from database import Base

class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Removed: first_name, last_name, email, mobile (as per requirements)

    address_label = Column(String(50), nullable=False)
    street_address = Column(String(255), nullable=False)
    landmark = Column(String(255), nullable=False)
    locality = Column(String(150), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(100), nullable=False)
    postal_code = Column(String(20), nullable=False, index=True)  # Pincode - required
    country = Column(String(100), nullable=False, default="India")

    save_for_future = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())