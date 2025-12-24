"""Initial database schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

Tags: schema, initial
"""
from typing import Sequence, Union
import logging

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = ('schema',)
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Initial schema creation - creates all base tables.
    This migration creates all core tables if they don't exist.
    Uses Base.metadata to create all registered models.
    """
    # Import all models to ensure they're registered with Base
    import sys
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    if str(BASE_DIR) not in sys.path:
        sys.path.insert(0, str(BASE_DIR))
    
    # Import database and Base
    from database import Base
    from sqlalchemy import inspect
    
    connection = op.get_bind()
    inspector = inspect(connection)
    existing_tables_before = set(inspector.get_table_names())
    
    # Import all models so they're registered with Base.metadata
    # This ensures all tables are included
    try:
        from Login_module.User.user_model import User
        from Product_module.Product_model import Category, Product
        from Member_module.Member_model import Member
        from Address_module.Address_model import Address
        from Cart_module.Cart_model import CartItem
        from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
        from Login_module.Device.Device_session_model import DeviceSession
        from Member_module.Member_audit_model import MemberAuditLog
        from Address_module.Address_audit_model import AddressAudit
        from Cart_module.Cart_audit_model import AuditLog
        from Audit_module.Profile_audit_crud import ProfileAuditLog
        from Login_module.Device.Device_session_audit_model import SessionAuditLog
        from Login_module.OTP.OTP_Log_Model import OTPAuditLog
        from Cart_module.Coupon_model import Coupon, CartCoupon
    except ImportError as e:
        logging.getLogger(__name__).warning(f"Could not import some models: {e}")
    
    # Create all tables defined in models if they don't exist
    # This ensures base tables are created even if migrations haven't run
    Base.metadata.create_all(bind=connection, checkfirst=True)
    
    # Check what was created
    inspector = inspect(connection)
    existing_tables_after = set(inspector.get_table_names())
    created_tables = existing_tables_after - existing_tables_before
    
    logger = logging.getLogger(__name__)
    if created_tables:
        logger.info(f"Created {len(created_tables)} base tables: {', '.join(sorted(created_tables))}")
    else:
        logger.info(f"All base tables already exist ({len(existing_tables_before)} tables found).")


def downgrade() -> None:
    """Rollback initial schema"""
    pass

