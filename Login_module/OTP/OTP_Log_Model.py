from sqlalchemy import Column, Integer, String, DateTime, func, Text
from database import Base


class OTPLog(Base):
    __tablename__ = "otp_logs"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(30), nullable=False, index=True) 
    # includes country code
    hashed_otp = Column(String(255), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now())
    
    user_entered_otp = Column(String(255), nullable=True)  # filled only when verifying
    verified_at = Column(DateTime(timezone=True), nullable=True)

    # status: sent / verified / failed
    status = Column(String(20), nullable=False)
    
    