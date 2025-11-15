
from sqlalchemy import Column, Integer, String, DateTime, func
from database import Base

class AddressAudit(Base):
    __tablename__ = "address_audit"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    username = Column(String(255), nullable=True)
    phone_number = Column(String(20), nullable=True)
    address_id = Column(Integer, nullable=False)
    action = Column(String(50))  # created / updated

    created_at = Column(DateTime(timezone=True), server_default=func.now())