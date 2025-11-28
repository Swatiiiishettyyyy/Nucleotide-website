from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Enum, Date, Integer as IntCol
from sqlalchemy.orm import relationship
from database import Base
from Product_module.Product_model import Category
import enum


class RelationType(str, enum.Enum):
    SELF = "self"
    SPOUSE = "spouse"
    CHILD = "child"
    PARENT = "parent"
    SIBLING = "sibling"
    OTHER = "other"


class Member(Base):
    __tablename__ = "members"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(100), nullable=False)
    relation = Column(Enum(RelationType), nullable=False, default=RelationType.SELF)
    
    # Required fields: age, gender, dob, mobile
    age = Column(IntCol, nullable=False)
    gender = Column(String(20), nullable=False)  # M, F, Other
    dob = Column(Date, nullable=False)
    mobile = Column(String(20), nullable=False)
    
    # Track which category/plan this member is associated with
    # This helps prevent duplicate entries in same category
    associated_category = Column(String(100), nullable=True, index=True)  # "genome_testing"
    associated_category_id = Column(Integer, ForeignKey("categories.id"), nullable=True, index=True)
    associated_plan_type = Column(String(50), nullable=True, index=True)  # "single", "couple", "family"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    category = relationship(Category, lazy="joined", foreign_keys=[associated_category_id])