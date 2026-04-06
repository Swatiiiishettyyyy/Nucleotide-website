import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone, timedelta

# Import models
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../..'))

from database import Base
from Cart_module.Coupon_model import Coupon, CouponAllowedUser, CouponType, CouponStatus
from Cart_module.coupon_service import is_user_allowed_for_coupon


# Fixture: in-memory SQLite session
@pytest.fixture
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()
    Base.metadata.drop_all(engine)


def make_coupon(db, code="TEST10"):
    """Helper to create a minimal valid coupon."""
    now = datetime.now(timezone.utc)
    coupon = Coupon(
        coupon_code=code,
        discount_type=CouponType.PERCENTAGE,
        discount_value=10.0,
        min_order_amount=0.0,
        valid_from=now - timedelta(days=1),
        valid_until=now + timedelta(days=30),
        status=CouponStatus.ACTIVE,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


# Unit tests

def test_allowlist_row_requires_user_id_or_mobile(db):
    """Property 1: row with both null must raise IntegrityError."""
    coupon = make_coupon(db)
    entry = CouponAllowedUser(coupon_id=coupon.id, user_id=None, mobile=None)
    db.add(entry)
    with pytest.raises(IntegrityError):
        db.flush()
    db.rollback()


def test_cascade_delete(db):
    """Property 2: deleting coupon removes allowlist rows."""
    coupon = make_coupon(db)
    entry = CouponAllowedUser(coupon_id=coupon.id, user_id=42, mobile=None)
    db.add(entry)
    db.commit()
    db.delete(coupon)
    db.commit()
    count = db.query(CouponAllowedUser).filter(CouponAllowedUser.coupon_id == coupon.id).count()
    assert count == 0


def test_unrestricted_coupon_allows_any_user(db):
    """Property 4/6: coupon with no allowlist entries is unrestricted."""
    coupon = make_coupon(db)
    assert is_user_allowed_for_coupon(db, coupon, user_id=99, mobile="9999999999") is True


def test_restricted_coupon_blocks_non_allowlisted_user(db):
    """Property 3/5: restricted coupon blocks user not on allowlist."""
    coupon = make_coupon(db)
    entry = CouponAllowedUser(coupon_id=coupon.id, user_id=1, mobile=None)
    db.add(entry)
    db.commit()
    assert is_user_allowed_for_coupon(db, coupon, user_id=99, mobile="9999999999") is False


def test_restricted_coupon_allows_user_by_id(db):
    """Property 3: user on allowlist by user_id is allowed."""
    coupon = make_coupon(db)
    entry = CouponAllowedUser(coupon_id=coupon.id, user_id=42, mobile=None)
    db.add(entry)
    db.commit()
    assert is_user_allowed_for_coupon(db, coupon, user_id=42, mobile="0000000000") is True


def test_restricted_coupon_allows_user_by_mobile(db):
    """Property 3: user on allowlist by mobile is allowed."""
    coupon = make_coupon(db)
    entry = CouponAllowedUser(coupon_id=coupon.id, user_id=None, mobile="9876543210")
    db.add(entry)
    db.commit()
    assert is_user_allowed_for_coupon(db, coupon, user_id=99, mobile="9876543210") is True
