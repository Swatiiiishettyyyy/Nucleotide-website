from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, func, Index
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
    product_id = Column(Integer, ForeignKey("consent_products.id", ondelete="CASCADE"), nullable=False, index=True)
    product = Column(String(100), nullable=True)  # Product name (denormalized for quick access)
    consent_given = Column(Integer, nullable=False, default=1)  # 1 for yes, only store yes consents
    consent_source = Column(String(20), nullable=False)  # "login" or "product"
    status = Column(String(10), nullable=False, default="yes")  # "yes" or "no"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)

    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    consent_product = relationship("ConsentProduct", foreign_keys=[product_id], back_populates="consents")

    # Composite index to prevent duplicates
    __table_args__ = (
        Index('idx_user_phone_product', 'user_phone', 'product_id', unique=True),
    )

