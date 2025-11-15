from sqlalchemy import Column, Integer, String, Float, JSON
from database import Base


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