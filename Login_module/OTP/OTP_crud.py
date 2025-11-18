from sqlalchemy.orm import Session
from datetime import datetime
from .OTP_Log_Model import OTPLog
from ..Utils.security import hash_value  # Use central hashing function


def create_sent_log(db: Session, phone_number: str, otp_hash: str):
    """
    Create log when OTP is generated & sent.
    otp_hash must already be hashed before passed.
    """
    log = OTPLog(
        phone_number=phone_number,
        hashed_otp=otp_hash,
        status="sent"
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def mark_verified(db: Session, log_id: int, user_entered_otp_hash: str):
    """
    Mark the previously sent OTP as verified successfully.
    Store the hashed OTP provided by user for auditing.
    """
    log = db.query(OTPLog).filter(OTPLog.id == log_id).first()
    if log:
        log.user_entered_otp = user_entered_otp_hash
        log.verified_at = datetime.utcnow()
        log.status = "verified"
        db.commit()
        db.refresh(log)
    return log


def mark_failed(db: Session, phone_number: str, user_entered_otp_hash: str):
    """
    Log failed OTP attempts.
    hashed_otp is preserved as 'N/A' because we don't know which OTP was expected.
    """
    log = OTPLog(
        phone_number=phone_number,
        hashed_otp="N/A",
        user_entered_otp=user_entered_otp_hash,
        verified_at=datetime.utcnow(),
        status="failed"
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log