"""
Comprehensive script to create ALL database tables if they don't exist.
This script checks the database and creates only the missing tables.

Usage:
    python create_all_tables.py

This will:
1. Import all models from the codebase
2. Check which tables exist in the database
3. Create only the missing tables
4. Provide detailed output of what was created
"""
import sys
import os
from pathlib import Path
from dotenv import load_dotenv
import logging

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
from sqlalchemy import inspect
from sqlalchemy.exc import OperationalError

# Define all expected tables with their models
EXPECTED_TABLES = {
    # Core tables
    'users': 'Login_module.User.user_model.User',
    'categories': 'Product_module.Product_model.Category',
    'products': 'Product_module.Product_model.Product',
    'members': 'Member_module.Member_model.Member',
    'addresses': 'Address_module.Address_model.Address',
    'cart_items': 'Cart_module.Cart_model.CartItem',
    
    # Coupon tables
    'coupons': 'Cart_module.Coupon_model.Coupon',
    'cart_coupons': 'Cart_module.Coupon_model.CartCoupon',
    
    # Order tables
    'orders': 'Orders_module.Order_model.Order',
    'order_items': 'Orders_module.Order_model.OrderItem',
    'order_snapshots': 'Orders_module.Order_model.OrderSnapshot',
    'order_status_history': 'Orders_module.Order_model.OrderStatusHistory',
    
    # Device/Session tables
    'device_sessions': 'Login_module.Device.Device_session_model.DeviceSession',
    
    # Audit tables
    'audit_logs': 'Cart_module.Cart_audit_model.AuditLog',
    'member_audit_logs': 'Member_module.Member_audit_model.MemberAuditLog',
    'address_audits': 'Address_module.Address_audit_model.AddressAudit',
    'session_audit_logs': 'Login_module.Device.Device_session_audit_model.SessionAuditLog',
    'otp_audit_logs': 'Login_module.OTP.OTP_Log_Model.OTPAuditLog',
    'profile_audit_logs': 'Profile_module.Profile_audit_crud.ProfileAuditLog',
}


def import_all_models():
    """Import all models to register them with SQLAlchemy Base.metadata"""
    logger.info("Importing all models...")
    imported_count = 0
    
    try:
        # User models
        from Login_module.User.user_model import User
        imported_count += 1
        logger.debug("✓ Imported User model")
        
        # Product models
        from Product_module.Product_model import Category, Product
        imported_count += 2
        logger.debug("✓ Imported Category and Product models")
        
        # Member models
        from Member_module.Member_model import Member
        from Member_module.Member_audit_model import MemberAuditLog
        imported_count += 2
        logger.debug("✓ Imported Member and MemberAuditLog models")
        
        # Address models
        from Address_module.Address_model import Address
        from Address_module.Address_audit_model import AddressAudit
        imported_count += 2
        logger.debug("✓ Imported Address and AddressAudit models")
        
        # Cart models
        from Cart_module.Cart_model import CartItem
        from Cart_module.Cart_audit_model import AuditLog
        imported_count += 2
        logger.debug("✓ Imported CartItem and AuditLog models")
        
        # Coupon models
        from Cart_module.Coupon_model import Coupon, CartCoupon
        imported_count += 2
        logger.debug("✓ Imported Coupon and CartCoupon models")
        
        # Order models - IMPORTANT: These must be imported
        # Import order models early to ensure they're registered
        try:
            from Orders_module.Order_model import Order, OrderItem, OrderSnapshot, OrderStatusHistory
            imported_count += 4
            logger.info("✓ Imported Order, OrderItem, OrderSnapshot, OrderStatusHistory models")
            
            # Verify order tables are registered
            order_table_names = ['orders', 'order_items', 'order_snapshots', 'order_status_history']
            registered_order_tables = [t for t in order_table_names if t in Base.metadata.tables]
            logger.info(f"  Registered order tables: {len(registered_order_tables)}/{len(order_table_names)}")
            if len(registered_order_tables) < len(order_table_names):
                missing = set(order_table_names) - set(registered_order_tables)
                logger.warning(f"  ⚠ Missing order tables in Base.metadata: {', '.join(missing)}")
        except Exception as e:
            logger.error(f"❌ Failed to import Order models: {e}")
            import traceback
            traceback.print_exc()
            raise
        
        # Device/Session models
        from Login_module.Device.Device_session_model import DeviceSession
        from Login_module.Device.Device_session_audit_model import SessionAuditLog
        imported_count += 2
        logger.debug("✓ Imported DeviceSession and SessionAuditLog models")
        
        # OTP models
        from Login_module.OTP.OTP_Log_Model import OTPAuditLog
        imported_count += 1
        logger.debug("✓ Imported OTPAuditLog model")
        
        # Profile models
        try:
            from Profile_module.Profile_audit_crud import ProfileAuditLog
            imported_count += 1
            logger.debug("✓ Imported ProfileAuditLog model")
        except ImportError as e:
            logger.warning(f"⚠ Could not import ProfileAuditLog: {e}")
        
        # Verify models are registered
        registered_tables = len(Base.metadata.tables)
        logger.info(f"✅ Imported {imported_count} model(s), {registered_tables} table(s) registered in Base.metadata")
        
        if registered_tables == 0:
            logger.error("❌ No tables registered in Base.metadata! This is a critical error.")
            logger.error("Models may not be properly inheriting from Base.")
            logger.error("Checking Base instance...")
            
            # Verify Base instance
            from database import Base as DB_Base
            if Base is not DB_Base:
                logger.error("❌ Base instance mismatch! Using different Base instances.")
                logger.error("This will prevent tables from being created.")
            else:
                logger.info("✓ Base instance is correct")
            
            return False
        
        # Verify Base instance matches
        from database import Base as DB_Base
        if Base is not DB_Base:
            logger.warning("⚠ Base instance mismatch detected!")
            logger.warning("Models might be using a different Base instance.")
        else:
            logger.debug("✓ Base instance verification passed")
        
        return True
        
    except ImportError as e:
        logger.error(f"❌ Error importing models: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during model import: {e}", exc_info=True)
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
        logger.error(f"❌ Error inspecting database: {e}", exc_info=True)
        return None


def create_missing_tables(existing_tables):
    """Create missing tables using Base.metadata.create_all()"""
    import time
    
    try:
        logger.info("Creating missing tables...")
        
        # Get all tables that should exist from Base.metadata
        all_expected_tables = set(Base.metadata.tables.keys())
        
        # ALWAYS print registered tables for debugging
        logger.info(f"Registered tables in Base.metadata: {len(all_expected_tables)}")
        logger.info("Registered table names:")
        for table_name in sorted(all_expected_tables):
            logger.info(f"  - {table_name}")
        
        # Specifically check order tables
        order_table_names = ['orders', 'order_items', 'order_snapshots', 'order_status_history']
        registered_order_tables = [t for t in order_table_names if t in all_expected_tables]
        logger.info("")
        logger.info(f"Order tables check: {len(registered_order_tables)}/{len(order_table_names)} registered")
        for table_name in order_table_names:
            if table_name in all_expected_tables:
                logger.info(f"  ✓ {table_name} is registered")
            else:
                logger.error(f"  ✗ {table_name} is NOT registered in Base.metadata!")
                logger.error(f"     This means the model was not properly imported or registered.")
        
        if len(all_expected_tables) == 0:
            logger.error("❌ CRITICAL: No tables registered in Base.metadata!")
            logger.error("Models were imported but not registered. Check model imports.")
            return False, []
        
        # Find missing tables
        missing_tables = all_expected_tables - set(existing_tables)
        
        if not missing_tables:
            logger.info("✅ All tables already exist in the database!")
            return True, []
        
        logger.info(f"Found {len(missing_tables)} missing table(s): {', '.join(sorted(missing_tables))}")
        
        # PRIMARY METHOD: Create all tables (checkfirst will skip existing ones)
        logger.info("Creating tables using Base.metadata.create_all()...")
        try:
            # Use explicit connection and transaction
            with engine.begin() as conn:
                Base.metadata.create_all(bind=conn, checkfirst=True)
            logger.info("✓ Table creation command executed")
        except Exception as e:
            logger.warning(f"⚠ Error with explicit transaction, trying direct method: {e}")
            # Fallback: direct creation
            Base.metadata.create_all(bind=engine, checkfirst=True)
        
        # Wait for database to process
        time.sleep(1.0)  # Increased wait time
        
        # Verify tables were created
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        newly_created = set(created_tables) - set(existing_tables)
        
        # Check if all missing tables were actually created
        still_missing = missing_tables - newly_created
        
        if newly_created:
            logger.info(f"✅ Successfully created {len(newly_created)} table(s): {', '.join(sorted(newly_created))}")
            
            if still_missing:
                logger.warning(f"⚠ {len(still_missing)} table(s) were not created: {', '.join(sorted(still_missing))}")
                
                # Check if missing tables are order tables
                order_table_names = ['orders', 'order_items', 'order_snapshots', 'order_status_history']
                missing_order_tables = [t for t in still_missing if t in order_table_names]
                
                if missing_order_tables:
                    logger.warning("")
                    logger.warning("⚠⚠⚠ ORDER TABLES ARE MISSING! ⚠⚠⚠")
                    logger.warning(f"Missing order tables: {', '.join(missing_order_tables)}")
                    logger.warning("This is critical - attempting special handling...")
                    logger.warning("")
                
                logger.info("Attempting to create remaining tables individually...")
                
                # Try individual creation with explicit transactions
                for table_name in still_missing:
                    try:
                        if table_name not in Base.metadata.tables:
                            logger.error(f"  ✗ {table_name} is NOT in Base.metadata.tables!")
                            logger.error(f"     Cannot create table - model not registered!")
                            continue
                        
                        table = Base.metadata.tables[table_name]
                        logger.info(f"  Creating {table_name} individually...")
                        logger.info(f"     Table object: {table}")
                        logger.info(f"     Table columns: {len(table.columns)}")
                        
                        # Try with explicit transaction
                        try:
                            with engine.begin() as conn:
                                table.create(bind=conn, checkfirst=True)
                            logger.info(f"  ✓ Created {table_name} (transaction method)")
                            newly_created.add(table_name)
                        except Exception as e1:
                            logger.warning(f"  ⚠ Transaction method failed for {table_name}: {e1}")
                            # Fallback to direct method
                            try:
                                table.create(bind=engine, checkfirst=True)
                                logger.info(f"  ✓ Created {table_name} (direct method)")
                                newly_created.add(table_name)
                            except Exception as e2:
                                logger.error(f"  ✗ Direct method also failed for {table_name}: {e2}")
                                # Last resort: try without checkfirst
                                try:
                                    table.create(bind=engine, checkfirst=False)
                                    logger.info(f"  ✓ Created {table_name} (force method)")
                                    newly_created.add(table_name)
                                except Exception as e3:
                                    logger.error(f"  ✗ All methods failed for {table_name}: {e3}")
                                    import traceback
                                    traceback.print_exc()
                    except Exception as e:
                        logger.error(f"  ✗ Failed to create {table_name}: {e}")
                        logger.error(f"     Error details: {type(e).__name__}: {str(e)}")
                        import traceback
                        traceback.print_exc()
            
            # Final verification
            time.sleep(0.5)
            inspector = inspect(engine)
            final_tables = inspector.get_table_names()
            final_newly_created = set(final_tables) - set(existing_tables)
            
            if final_newly_created:
                logger.info(f"✅ Final count: {len(final_newly_created)} table(s) created")
                return True, sorted(final_newly_created)
            else:
                return True, sorted(newly_created)
        else:
            logger.warning("⚠ No new tables were created on first attempt.")
            logger.info("Attempting alternative creation methods...")
            
            # METHOD 2: Create without checkfirst (will error if exists, but that's OK)
            logger.info("Method 2: Creating all tables without checkfirst...")
            try:
                with engine.begin() as conn:
                    Base.metadata.create_all(bind=conn, checkfirst=False)
                time.sleep(1.0)
                inspector = inspect(engine)
                final_tables = inspector.get_table_names()
                newly_created = set(final_tables) - set(existing_tables)
                if newly_created:
                    logger.info(f"✅ Created {len(newly_created)} table(s) with method 2")
                    return True, sorted(newly_created)
            except Exception as e2:
                logger.warning(f"⚠ Method 2 failed (this is OK if tables already exist): {e2}")
            
            # METHOD 3: Create tables one by one
            logger.info("Method 3: Creating tables individually...")
            individual_created = []
            for table_name in missing_tables:
                try:
                    if table_name in Base.metadata.tables:
                        table = Base.metadata.tables[table_name]
                        logger.info(f"  Creating {table_name}...")
                        with engine.begin() as conn:
                            table.create(bind=conn, checkfirst=True)
                        individual_created.append(table_name)
                        logger.info(f"  ✓ Created {table_name}")
                except Exception as e3:
                    logger.error(f"  ✗ Failed to create {table_name}: {e3}")
            
            if individual_created:
                logger.info(f"✅ Created {len(individual_created)} table(s) individually")
                return True, sorted(individual_created)
            
            logger.error("❌ All creation methods failed!")
            logger.error("Please check:")
            logger.error("  1. Database connection is working")
            logger.error("  2. Database user has CREATE TABLE permissions")
            logger.error("  3. No conflicting table names or schema issues")
            return False, []
            
    except OperationalError as e:
        logger.error(f"❌ Database operation error: {e}")
        logger.error("Please check:")
        logger.error("  1. Database is running")
        logger.error("  2. DATABASE_URL is correct")
        logger.error("  3. Database user has CREATE TABLE permissions")
        return False, []
    except Exception as e:
        logger.error(f"❌ Error creating tables: {e}", exc_info=True)
        return False, []


def print_table_summary(existing_tables, newly_created):
    """Print a summary of all tables"""
    print("\n" + "="*70)
    print("DATABASE TABLES SUMMARY")
    print("="*70)
    
    # Categorize tables
    core_tables = ['users', 'categories', 'products', 'members', 'addresses', 'cart_items']
    coupon_tables = ['coupons', 'cart_coupons']
    order_tables = ['orders', 'order_items', 'order_snapshots', 'order_status_history']
    device_tables = ['device_sessions']
    audit_tables = ['audit_logs', 'member_audit_logs', 'address_audits', 
                   'session_audit_logs', 'otp_audit_logs', 'profile_audit_logs']
    
    all_tables = sorted(existing_tables)
    
    print(f"\nTotal tables in database: {len(all_tables)}")
    
    if newly_created:
        print(f"\nNewly created tables ({len(newly_created)}):")
        for table in newly_created:
            print(f"   [OK] {table}")
    
    print(f"\nCore Tables:")
    for table in core_tables:
        status = "[OK]" if table in all_tables else "[MISSING]"
        print(f"   {status} {table}")
    
    print(f"\nCoupon Tables:")
    for table in coupon_tables:
        status = "[OK]" if table in all_tables else "[MISSING]"
        print(f"   {status} {table}")
    
    print(f"\nOrder Tables:")
    for table in order_tables:
        status = "[OK]" if table in all_tables else "[MISSING]"
        print(f"   {status} {table}")
    
    print(f"\nDevice/Session Tables:")
    for table in device_tables:
        status = "[OK]" if table in all_tables else "[MISSING]"
        print(f"   {status} {table}")
    
    print(f"\nAudit Tables:")
    for table in audit_tables:
        status = "[OK]" if table in all_tables else "[MISSING]"
        print(f"   {status} {table}")
    
    # Check for any other tables
    other_tables = set(all_tables) - set(core_tables) - set(coupon_tables) - set(order_tables) - set(device_tables) - set(audit_tables)
    if other_tables:
        print(f"\nOther Tables:")
        for table in sorted(other_tables):
            print(f"   [OK] {table}")
    
    print("\n" + "="*70)


def force_create_all_tables():
    """Force create all tables without checking if they exist"""
    import time
    try:
        logger.info("Force creating all tables (this will skip existing tables)...")
        
        # Show what we're about to create
        logger.info(f"Tables to create: {len(Base.metadata.tables)}")
        for table_name in sorted(Base.metadata.tables.keys()):
            logger.info(f"  - {table_name}")
        
        # Use explicit transaction
        with engine.begin() as conn:
            Base.metadata.create_all(bind=conn, checkfirst=True)
        
        time.sleep(1.0)
        
        inspector = inspect(engine)
        created_tables = inspector.get_table_names()
        logger.info(f"✅ Tables in database after force create: {len(created_tables)}")
        logger.info(f"Tables: {', '.join(sorted(created_tables))}")
        return created_tables
    except Exception as e:
        logger.error(f"❌ Error in force create: {e}", exc_info=True)
        return None


def main():
    """Main function to create all missing tables"""
    print("="*70)
    print("DATABASE TABLE CREATION SCRIPT")
    print("="*70)
    print()
    
    # Step 1: Import all models
    logger.info("Step 1: Importing all models...")
    if not import_all_models():
        logger.error("Failed to import models. Exiting.")
        return False
    
    # Verify models are registered
    if len(Base.metadata.tables) == 0:
        logger.error("❌ CRITICAL: No tables registered in Base.metadata!")
        logger.error("This means models are not properly imported or not inheriting from Base.")
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
        logger.info(f"Existing tables: {', '.join(sorted(existing_tables))}")
    print()
    
    # Step 3: Create missing tables
    logger.info("Step 3: Creating missing tables...")
    success, newly_created = create_missing_tables(existing_tables)
    
    if not success or not newly_created:
        logger.warning("⚠ Initial creation attempt did not create all tables.")
        logger.info("Attempting force create as fallback...")
        force_created = force_create_all_tables()
        if force_created:
            newly_created = set(force_created) - set(existing_tables)
            if newly_created:
                logger.info(f"✅ Force create created {len(newly_created)} additional table(s)")
                success = True
    
    if not success:
        logger.error("Failed to create tables. Please check the error messages above.")
        logger.error("\nTroubleshooting tips:")
        logger.error("1. Check database connection (DATABASE_URL)")
        logger.error("2. Verify database user has CREATE TABLE permissions")
        logger.error("3. Check database logs for errors")
        logger.error("4. Try running: python create_all_tables.py")
        return False
    
    print()
    
    # Step 4: Get final table list
    final_tables = get_existing_tables()
    if final_tables:
        print_table_summary(final_tables, newly_created)
    
    print()
    if newly_created:
        logger.info(f"✅ Successfully created {len(newly_created)} missing table(s)")
        logger.info(f"Created tables: {', '.join(sorted(newly_created))}")
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

