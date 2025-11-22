from sqlalchemy import Column, Integer, String, Float, JSON, Enum
from database import Base
import enum


class PlanType(str, enum.Enum):
    SINGLE = "single"
    COUPLE = "couple"
    FAMILY = "family"


class Product(Base):
    __tablename__ = "products"

    ProductId = Column(Integer, primary_key=True, index=True)
    Name = Column(String(200), nullable=False)

    Price = Column(Float, nullable=False)             # Earlier mrp_price
    SpecialPrice = Column(Float, nullable=False)      # Earlier sale_price

    ShortDescription = Column(String(500), nullable=False)
    Discount = Column(String(50), nullable=True)

    Description = Column(String(2000), nullable=True)
    Images = Column(JSON, nullable=True)   # List of image URLs
    
    # New fields for plan type and category
    plan_type = Column(Enum(PlanType), nullable=False, default=PlanType.SINGLE, index=True)
    category = Column(String(100), nullable=False, default="genome_testing", index=True)
    max_members = Column(Integer, nullable=False, default=1)  # 1 for single, 2 for couple, 4 for family