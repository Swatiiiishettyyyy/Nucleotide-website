from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, func
from sqlalchemy.orm import relationship
from database import Base

class DeviceSession(Base):
    __tablename__ = "device_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    session_key = Column(String(255), nullable=False, index=True)  # random session id
    device_id = Column(String(255), nullable=True)                # device id from client
    device_platform = Column(String(50), nullable=True)           # web / mobile / ios / android etc
    device_details = Column(String(500), nullable=True)           # raw device details string/json
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, default=True)

    # relationships - optional
    # user = relationship("User", backref="sessions")