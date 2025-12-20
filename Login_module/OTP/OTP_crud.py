from sqlalchemy.orm import Session
from datetime import datetime
from typing import Optional
from .OTP_Log_Model import OTPAuditLog
from Login_module.Utils.datetime_utils import now_ist


def create_otp_audit_log(
    db: Session,
    event_type: str,  # GENERATED, VERIFIED, FAILED, BLOCKED
    user_id: Optional[int] = None,
    device_id: Optional[str] = None,
    phone_number: Optional[str] = None,
    reason: Optional[str] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    correlation_id: Optional[str] = None
) -> OTPAuditLog:
    """
    Create OTP audit log entry. No OTP values are stored, only events.
    """
    log = OTPAuditLog(
        user_id=user_id,
        device_id=device_id,
        event_type=event_type,
        phone_number=phone_number,
        reason=reason,
        timestamp=now_ist(),
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=correlation_id
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log