
from sqlalchemy import Column, Integer, String, DateTime, func, JSON, Text
from database import Base

class AddressAudit(Base):
    __tablename__ = "address_audit"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    address_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # created / updated
    old_data = Column(JSON, nullable=True)  # Previous address data before update
    new_data = Column(JSON, nullable=True)  # New address data after update
    ip_address = Column(String(50), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)  # For request tracing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)