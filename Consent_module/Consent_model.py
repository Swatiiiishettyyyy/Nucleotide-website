from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Index, Text
from sqlalchemy.orm import relationship
from database import Base


class ConsentProduct(Base):
    __tablename__ = "consent_products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Relationship
    consents = relationship("UserConsent", back_populates="consent_product")


class UserConsent(Base):
    __tablename__ = "user_consents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_phone = Column(String(20), nullable=False, index=True)
    member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    product_id = Column(Integer, ForeignKey("consent_products.id", ondelete="CASCADE"), nullable=False, index=True)
    product = Column(String(100), nullable=True)  # Product name (denormalized for quick access)
    consent_given = Column(Integer, nullable=False, default=1)  # 1 for yes, only store yes consents
    consent_source = Column(String(20), nullable=False)  # "login" or "product"
    status = Column(String(10), nullable=False, default="yes")  # "yes" or "no"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Transfer tracking fields
    linked_from_consent_id = Column(Integer, ForeignKey("user_consents.id", ondelete="SET NULL"), nullable=True)  # Original consent if this is a transferred copy
    transfer_log_id = Column(Integer, ForeignKey("member_transfer_logs.id", ondelete="SET NULL"), nullable=True, index=True)  # Link to transfer log
    transferred_at = Column(DateTime(timezone=True), nullable=True)  # When transfer occurred

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    member = relationship("Member", foreign_keys=[member_id])
    consent_product = relationship("ConsentProduct", foreign_keys=[product_id], back_populates="consents")

    # Composite index to prevent duplicates (member-scoped)
    __table_args__ = (
        Index('idx_member_product', 'member_id', 'product_id', unique=True),
    )


class PartnerConsent(Base):
    """
    Partner consent table for Product 11 (Child simulator).
    Stores dual consent records where both user and partner must consent.
    """
    __tablename__ = "partner_consents"

    id = Column(Integer, primary_key=True, index=True)
    
    # Product info (should always be product_id = 11)
    product_id = Column(Integer, ForeignKey("consent_products.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # User (requester) info - who initiated the consent
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    user_member_id = Column(Integer, ForeignKey("members.id", ondelete="RESTRICT"), nullable=False, index=True)
    user_name = Column(String(100), nullable=False)
    user_mobile = Column(String(20), nullable=False, index=True)
    user_consent = Column(String(10), nullable=False, default="no")  # "yes" or "no"
    
    # Partner info - the spouse/partner who needs to consent
    partner_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)  # Partner's user_id if they have account
    partner_member_id = Column(Integer, ForeignKey("members.id", ondelete="SET NULL"), nullable=True, index=True)  # Partner's member_id if exists
    partner_name = Column(String(100), nullable=True)  # Partner's name
    partner_mobile = Column(String(20), nullable=False, index=True)  # Partner's mobile (required for OTP)
    partner_consent = Column(String(10), nullable=False, default="no")  # "yes" or "no"
    
    # Final consent status (only "yes" if both user and partner consented)
    final_status = Column(String(10), nullable=False, default="no")  # "yes" only if both said yes
    
    # Metadata
    consent_source = Column(String(20), nullable=False, default="product")  # "product" or "partner_otp"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    user_member = relationship("Member", foreign_keys=[user_member_id])
    partner_user = relationship("User", foreign_keys=[partner_user_id])
    partner_member = relationship("Member", foreign_keys=[partner_member_id])
    consent_product = relationship("ConsentProduct", foreign_keys=[product_id])
    
    # Composite index to prevent duplicates (one consent record per user_member_id for product 11)
    __table_args__ = (
        Index('idx_user_member_product', 'user_member_id', 'product_id', unique=True),
    )

