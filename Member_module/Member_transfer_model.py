"""
Member transfer model for tracking member transfers between users.
"""
from sqlalchemy import Column, Integer, String, DateTime, func, ForeignKey, Text, JSON
from database import Base


class MemberTransferLog(Base):
    """
    Tracks member transfer requests and executions.
    Records the transfer of a member from one user account to another.
    """
    __tablename__ = "member_transfer_logs"

    id = Column(Integer, primary_key=True, index=True)
    
    # Transfer participants
    old_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    new_user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)  # Set when transfer completes
    old_member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    new_member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=True, index=True)  # Same as old_member_id after transfer
    
    # Member phone number (for OTP verification)
    member_phone = Column(String(20), nullable=False, index=True)
    
    # Transfer status
    transfer_status = Column(String(20), nullable=False, default="PENDING_OTP", index=True)  # PENDING_OTP, OTP_VERIFIED, COMPLETED, FAILED, CANCELLED
    
    # OTP fields
    otp_code = Column(String(10), nullable=True)  # Temporary storage (hashed in production)
    otp_expires_at = Column(DateTime(timezone=True), nullable=True)
    otp_verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Transfer metadata
    transfer_initiated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    transfer_completed_at = Column(DateTime(timezone=True), nullable=True)
    initiated_by_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)  # Who clicked transfer
    
    # Transfer statistics (counts of what was transferred)
    # Note: Orders are shared (not copied), so no order copying counts needed
    cart_items_moved_count = Column(Integer, nullable=False, default=0)
    consents_copied_count = Column(Integer, nullable=False, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    # Audit fields
    ip_address = Column(String(50), nullable=True, index=True)
    user_agent = Column(String(500), nullable=True)
    correlation_id = Column(String(100), nullable=True, index=True)
    transfer_metadata = Column(JSON, nullable=True)  # Flexible storage for additional data (renamed from 'metadata' to avoid SQLAlchemy reserved word)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

