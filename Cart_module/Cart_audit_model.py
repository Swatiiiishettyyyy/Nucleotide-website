from sqlalchemy import Column, Integer, String, DateTime, JSON, func, Text
from database import Base

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=True, index=True)
    username = Column(String(255), nullable=True)
    cart_id = Column(Integer, nullable=True)
    action = Column(String(100), nullable=False)  # ADD, UPDATE, DELETE, VIEW, CLEAR
    entity_type = Column(String(50), nullable=False)  # CART_ITEM, CART
    entity_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)  # Store additional details as JSON
    ip_address = Column(String(50), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)  # For request tracing
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)