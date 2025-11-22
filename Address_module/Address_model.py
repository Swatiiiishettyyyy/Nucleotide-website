# app/models/address.py
from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, DateTime, func
from database import Base

class Address(Base):
    __tablename__ = "addresses"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    # Removed: first_name, last_name, email, mobile (as per requirements)

    address_label = Column(String(50))
    street_address = Column(String(255))
    landmark = Column(String(255))
    city = Column(String(100))
    state = Column(String(100))
    postal_code = Column(String(20), nullable=False, index=True)  # Pincode - required for auto-generation
    country = Column(String(100), default="India")

    save_for_future = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())