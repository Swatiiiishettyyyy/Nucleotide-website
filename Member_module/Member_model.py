from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, func, Enum, Integer as IntCol
from database import Base
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
    
    # New fields: age, gender, mobile
    age = Column(IntCol, nullable=True)
    gender = Column(String(20), nullable=True)  # M, F, Other
    mobile = Column(String(20), nullable=True)
    
    # Track which category/plan this member is associated with
    # This helps prevent duplicate entries in same category
    associated_category = Column(String(100), nullable=True, index=True)  # "genome_testing"
    associated_plan_type = Column(String(50), nullable=True, index=True)  # "single", "couple", "family"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())