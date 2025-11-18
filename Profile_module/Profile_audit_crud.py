from sqlalchemy import Column, Integer, String, DateTime, JSON, func
from sqlalchemy.orm import Session
from database import Base
import json


class ProfileAuditLog(Base):
    __tablename__ = "profile_audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False, index=True)
    action = Column(String(50), nullable=False)  # EDIT / VIEW / etc.
    old_data = Column(JSON, nullable=True)
    new_data = Column(JSON, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now())


def log_profile_update(db: Session, user_id: int, old_data: dict, new_data: dict):
    """
    Store profile update audit log.
    """
    log_entry = ProfileAuditLog(
        user_id=user_id,
        action="PROFILE_UPDATE",
        old_data=old_data,
        new_data=new_data
    )
    
    db.add(log_entry)
    db.commit()
    db.refresh(log_entry)

    return log_entry
