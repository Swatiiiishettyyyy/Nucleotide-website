"""
Database table creation utility.
Checks if tables exist and creates them if they don't.

Usage:
    python tables.py

This script:
1. Imports all models to register them with SQLAlchemy Base
2. Checks which tables exist in the database
3. Creates only the missing tables
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import logging
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

# Add project root to path
ROOT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT_DIR))

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Import database components
from database import Base, engine


def import_all_models():
    """Import all models to register them with SQLAlchemy Base.metadata"""
    logger.info("Importing all models...")
    
    try:
        # User models
        from Login_module.User.user_model import User
        logger.debug("✓ Imported User model")
        
        # Product models
        from Product_module.Product_model import Category, Product
        logger.debug("✓ Imported Category and Product models")
        
        # Member models
        from Member_module.Member_model import Member
        from Member_module.Member_audit_model import MemberAuditLog
        logger.debug("✓ Imported Member and MemberAuditLog models")
        
        # Address models
        from Address_module.Address_model import Address
        from Address_module.Address_audit_model import AddressAudit
        logger.debug("✓ Imported Address and AddressAudit models")
        
        # Cart models
        from Cart_module.Cart_model import CartItem
        from Cart_module.Cart_audit_model import AuditLog
        logger.debug("✓ Imported CartItem and AuditLog models")
        
        # Coupon models
        from Cart_module.Coupon_model import Coupon, CartCoupon
        logger.debug("✓ Imported Coupon and CartCoupon models")
        
        # Order models
        from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
        logger.debug("✓ Imported Order models")
        
        # Device/Session models
        from Login_module.Device.Device_session_model import DeviceSession
        from Login_module.Device.Device_session_audit_model import SessionAuditLog
        logger.debug("✓ Imported DeviceSession and SessionAuditLog models")
        
        # OTP models
        from Login_module.OTP.OTP_Log_Model import OTPAuditLog
        logger.debug("✓ Imported OTPAuditLog model")
        
        # Profile models
        try:
            from Audit_module.Profile_audit_crud import ProfileAuditLog
            logger.debug("✓ Imported ProfileAuditLog model")
        except ImportError:
            logger.warning("⚠ Could not import ProfileAuditLog (optional)")
        
        # Verify models are registered
        registered_tables = len(Base.metadata.tables)
        logger.info(f"✅ Imported models, {registered_tables} table(s) registered in Base.metadata")
        
        if registered_tables == 0:
            logger.error("❌ No tables registered in Base.metadata!")
            return False
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Error importing models: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during model import: {e}")
        return False


def get_existing_tables():
    """Get list of existing tables in the database"""
    try:
        inspector = inspect(engine)
        existing_tables = inspector.get_table_names()
        return existing_tables
    except OperationalError as e:
        logger.error(f"❌ Cannot connect to database: {e}")
        logger.error("Please check your DATABASE_URL environment variable")
        return None
    except Exception as e:
        logger.error(f"❌ Error inspecting database: {e}")
        return None


def create_missing_tables(existing_tables):
    """Create missing tables using Base.metadata.create_all()"""
    try:
        # Get all tables that should exist from Base.metadata
        all_expected_tables = set(Base.metadata.tables.keys())
        
        # Find missing tables
        missing_tables = all_expected_tables - set(existing_tables)
        
        if not missing_tables:
            logger.info("✅ All tables already exist in the database!")
            return True, []
        
        logger.info(f"Found {len(missing_tables)} missing table(s): {', '.join(sorted(missing_tables))}")
        
        # Create missing tables (checkfirst=True will skip existing ones)
        logger.info("Creating missing tables...")
        Base.metadata.create_all(bind=engine, checkfirst=True)
        
        # Verify tables were created
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        newly_created = set(created_tables) - set(existing_tables)
        
        if newly_created:
            logger.info(f"✅ Successfully created {len(newly_created)} table(s): {', '.join(sorted(newly_created))}")
            return True, sorted(newly_created)
        else:
            logger.warning("⚠ No new tables were created")
            return False, []
            
    except OperationalError as e:
        logger.error(f"❌ Database operation error: {e}")
        logger.error("Please check:")
        logger.error("  1. Database is running")
        logger.error("  2. DATABASE_URL is correct")
        logger.error("  3. Database user has CREATE TABLE permissions")
        return False, []
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}")
        return False, []


def print_summary(existing_tables, newly_created):
    """Print a summary of tables"""
    print("\n" + "="*70)
    print("DATABASE TABLES SUMMARY")
    print("="*70)
    
    all_tables = sorted(existing_tables)
    print(f"\n📊 Total tables in database: {len(all_tables)}")
    
    if newly_created:
        print(f"\n✨ Newly created tables ({len(newly_created)}):")
        for table in newly_created:
            print(f"   ✓ {table}")
    
    print("\n📋 All Tables:")
    for table in all_tables:
        marker = "✨" if table in newly_created else "✓"
        print(f"   {marker} {table}")
    
    print("\n" + "="*70)


def main():
    """Main function to create all missing tables"""
    print("="*70)
    print("DATABASE TABLE CREATION")
    print("="*70)
    print()
    
    # Step 1: Import all models
    logger.info("Step 1: Importing all models...")
    if not import_all_models():
        logger.error("Failed to import models. Exiting.")
        return False
    
    print()
    
    # Step 2: Check existing tables
    logger.info("Step 2: Checking existing tables in database...")
    existing_tables = get_existing_tables()
    
    if existing_tables is None:
        logger.error("Cannot proceed without database connection. Exiting.")
        return False
    
    logger.info(f"Found {len(existing_tables)} existing table(s) in database")
    if existing_tables:
        logger.debug(f"Existing tables: {', '.join(sorted(existing_tables))}")
    print()
    
    # Step 3: Create missing tables
    logger.info("Step 3: Creating missing tables...")
    success, newly_created = create_missing_tables(existing_tables)
    
    if not success:
        logger.error("Failed to create tables. Please check the error messages above.")
        return False
    
    print()
    
    # Step 4: Get final table list and print summary
    final_tables = get_existing_tables()
    if final_tables:
        print_summary(final_tables, newly_created)
    
    print()
    if newly_created:
        logger.info(f"✅ Successfully created {len(newly_created)} missing table(s)")
    else:
        logger.info("✅ All tables already exist. No action needed.")
    
    print()
    print("="*70)
    print("SCRIPT COMPLETED SUCCESSFULLY")
    print("="*70)
    
    return True


if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.info("\n⚠ Script interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}", exc_info=True)
        sys.exit(1)

