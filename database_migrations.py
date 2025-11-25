import logging
from typing import Callable

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from database import SessionLocal
from Member_module.Member_model import Member
from Product_module.Product_model import Category, Product
from Product_module.category_service import get_or_create_default_category

logger = logging.getLogger(__name__)


def _ensure_table(engine: Engine, table_callable: Callable[[Engine], None], table_name: str) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        logger.info("Creating table %s", table_name)
        table_callable(engine)


def _ensure_column(engine: Engine, table: str, column: str, ddl: str) -> None:
    inspector = inspect(engine)
    columns = {col["name"] for col in inspector.get_columns(table)}
    if column in columns:
        return

    logger.info("Adding column %s.%s", table, column)
    try:
        with engine.connect() as conn:
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}"))
            conn.commit()
    except SQLAlchemyError as exc:
        logger.error("Failed to add column %s.%s: %s", table, column, exc)
        raise


def _backfill_product_categories(session: Session) -> None:
    default_category = get_or_create_default_category(session)
    products = session.query(Product).filter(Product.category_id.is_(None)).all()
    if not products:
        return

    for product in products:
        product.category_id = default_category.id
    session.commit()
    logger.info("Backfilled %s product(s) with default category", len(products))


def _backfill_member_categories(session: Session) -> None:
    members = session.query(Member).filter(Member.associated_category_id.is_(None)).all()
    if not members:
        return

    logger.info("Backfilling %s member(s) with category references", len(members))
    for member in members:
        target_name = member.associated_category or get_or_create_default_category(session).name
        category = (
            session.query(Category)
            .filter(Category.name == target_name)
            .first()
        )
        if not category:
            category = Category(name=target_name)
            session.add(category)
            session.flush()
        member.associated_category_id = category.id
        if not member.associated_category:
            member.associated_category = category.name
    session.commit()


def _ensure_order_columns(engine: Engine) -> None:
    """Add order-related columns that support per-item status tracking"""
    try:
        inspector = inspect(engine)
        
        # Check if order_items table exists
        if "order_items" not in inspector.get_table_names():
            logger.warning("order_items table does not exist. Skipping order column migrations.")
            return
        
        # Check if order_status_history table exists
        if "order_status_history" not in inspector.get_table_names():
            logger.warning("order_status_history table does not exist. Skipping order column migrations.")
            return
        
        with engine.connect() as conn:
            # Get current columns for order_items
            order_items_columns = {col["name"] for col in inspector.get_columns("order_items")}
            
            # Add or fix order_status column in order_items
            dialect_name = engine.dialect.name
            if "order_status" not in order_items_columns:
                logger.info("Adding order_status column to order_items")
                try:
                    if dialect_name == "mysql":
                        # Check existing enum values from orders table to match them
                        # SQLAlchemy stores enum NAMES (uppercase), not values (lowercase)
                        try:
                            # Try to get enum values from orders.order_status column
                            result = conn.execute(text("""
                                SELECT COLUMN_TYPE 
                                FROM INFORMATION_SCHEMA.COLUMNS 
                                WHERE TABLE_SCHEMA = DATABASE() 
                                AND TABLE_NAME = 'orders' 
                                AND COLUMN_NAME = 'order_status'
                            """))
                            enum_row = result.fetchone()
                            if enum_row and enum_row[0]:
                                # Extract enum values from COLUMN_TYPE (e.g., "enum('ORDER_CONFIRMED','SCHEDULED',...)")
                                enum_def = enum_row[0]
                                logger.info(f"Found existing enum definition: {enum_def}")
                                # Use the existing enum definition
                                conn.execute(text(f"""
                                    ALTER TABLE order_items 
                                    ADD COLUMN order_status {enum_def} NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                                """))
                            else:
                                # Fallback to uppercase enum values (SQLAlchemy default)
                                conn.execute(text("""
                                    ALTER TABLE order_items 
                                    ADD COLUMN order_status ENUM(
                                        'ORDER_CONFIRMED',
                                        'SCHEDULED',
                                        'SCHEDULE_CONFIRMED_BY_LAB',
                                        'SAMPLE_COLLECTED',
                                        'SAMPLE_RECEIVED_BY_LAB',
                                        'TESTING_IN_PROGRESS',
                                        'REPORT_READY'
                                    ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                                """))
                        except Exception as e:
                            logger.warning(f"Could not detect existing enum, using default: {e}")
                            # Fallback to uppercase enum values
                            conn.execute(text("""
                                ALTER TABLE order_items 
                                ADD COLUMN order_status ENUM(
                                    'ORDER_CONFIRMED',
                                    'SCHEDULED',
                                    'SCHEDULE_CONFIRMED_BY_LAB',
                                    'SAMPLE_COLLECTED',
                                    'SAMPLE_RECEIVED_BY_LAB',
                                    'TESTING_IN_PROGRESS',
                                    'REPORT_READY'
                                ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                            """))
                    else:
                        # For other databases, use VARCHAR with CHECK constraint or TEXT
                        conn.execute(text("""
                            ALTER TABLE order_items 
                            ADD COLUMN order_status VARCHAR(50) NOT NULL DEFAULT 'order_confirmed'
                        """))
                    conn.commit()
                    logger.info("Successfully added order_status column to order_items")
                    
                    # Update any NULL values (though DEFAULT should have handled this)
                    try:
                        conn.execute(text("""
                            UPDATE order_items 
                            SET order_status = 'ORDER_CONFIRMED' 
                            WHERE order_status IS NULL
                        """))
                        conn.commit()
                    except Exception as e:
                        logger.warning(f"Could not update NULL order_status values: {e}")
                        conn.rollback()
                except SQLAlchemyError as e:
                    logger.error(f"Failed to add order_status column: {e}")
                    conn.rollback()
            else:
                # Column exists, but might have wrong enum values (lowercase)
                # Check if enum values are lowercase and need to be fixed
                logger.info("order_status column already exists, checking enum values")
                try:
                    if dialect_name == "mysql":
                        # Check current enum definition
                        result = conn.execute(text("""
                            SELECT COLUMN_TYPE 
                            FROM INFORMATION_SCHEMA.COLUMNS 
                            WHERE TABLE_SCHEMA = DATABASE() 
                            AND TABLE_NAME = 'order_items' 
                            AND COLUMN_NAME = 'order_status'
                        """))
                        enum_row = result.fetchone()
                        if enum_row and enum_row[0]:
                            enum_def = enum_row[0]
                            logger.info(f"Current order_items.order_status enum: {enum_def}")
                            # Check if it has lowercase values
                            if "'order_confirmed'" in enum_def.lower() and "'ORDER_CONFIRMED'" not in enum_def:
                                logger.error("order_items.order_status has lowercase enum values, but SQLAlchemy expects uppercase!")
                                logger.error("Fixing enum values by recreating the column...")
                                
                                # Create a temporary column with correct enum
                                try:
                                    # Step 1: Add temporary column with uppercase enum
                                    conn.execute(text("""
                                        ALTER TABLE order_items 
                                        ADD COLUMN order_status_new ENUM(
                                            'ORDER_CONFIRMED',
                                            'SCHEDULED',
                                            'SCHEDULE_CONFIRMED_BY_LAB',
                                            'SAMPLE_COLLECTED',
                                            'SAMPLE_RECEIVED_BY_LAB',
                                            'TESTING_IN_PROGRESS',
                                            'REPORT_READY'
                                        ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                                    """))
                                    
                                    # Step 2: Copy and convert data (convert lowercase to uppercase)
                                    conn.execute(text("""
                                        UPDATE order_items 
                                        SET order_status_new = CASE 
                                            WHEN UPPER(order_status) = 'ORDER_CONFIRMED' THEN 'ORDER_CONFIRMED'
                                            WHEN UPPER(order_status) = 'SCHEDULED' THEN 'SCHEDULED'
                                            WHEN UPPER(order_status) = 'SCHEDULE_CONFIRMED_BY_LAB' THEN 'SCHEDULE_CONFIRMED_BY_LAB'
                                            WHEN UPPER(order_status) = 'SAMPLE_COLLECTED' THEN 'SAMPLE_COLLECTED'
                                            WHEN UPPER(order_status) = 'SAMPLE_RECEIVED_BY_LAB' THEN 'SAMPLE_RECEIVED_BY_LAB'
                                            WHEN UPPER(order_status) = 'TESTING_IN_PROGRESS' THEN 'TESTING_IN_PROGRESS'
                                            WHEN UPPER(order_status) = 'REPORT_READY' THEN 'REPORT_READY'
                                            ELSE 'ORDER_CONFIRMED'
                                        END
                                    """))
                                    
                                    # Step 3: Drop old column
                                    conn.execute(text("ALTER TABLE order_items DROP COLUMN order_status"))
                                    
                                    # Step 4: Rename and position the column
                                    conn.execute(text("""
                                        ALTER TABLE order_items 
                                        CHANGE COLUMN order_status_new order_status ENUM(
                                            'ORDER_CONFIRMED',
                                            'SCHEDULED',
                                            'SCHEDULE_CONFIRMED_BY_LAB',
                                            'SAMPLE_COLLECTED',
                                            'SAMPLE_RECEIVED_BY_LAB',
                                            'TESTING_IN_PROGRESS',
                                            'REPORT_READY'
                                        ) NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price
                                    """))
                                    
                                    conn.commit()
                                    logger.info("Successfully fixed order_status enum values to uppercase")
                                except Exception as e:
                                    logger.error(f"Failed to fix order_status enum: {e}")
                                    conn.rollback()
                                    logger.error("You may need to manually fix the enum. Run this SQL:")
                                    logger.error("""
ALTER TABLE order_items 
ADD COLUMN order_status_new ENUM('ORDER_CONFIRMED','SCHEDULED','SCHEDULE_CONFIRMED_BY_LAB','SAMPLE_COLLECTED','SAMPLE_RECEIVED_BY_LAB','TESTING_IN_PROGRESS','REPORT_READY') 
NOT NULL DEFAULT 'ORDER_CONFIRMED' AFTER total_price;

UPDATE order_items SET order_status_new = UPPER(order_status);

ALTER TABLE order_items DROP COLUMN order_status;
ALTER TABLE order_items CHANGE COLUMN order_status_new order_status ENUM('ORDER_CONFIRMED','SCHEDULED','SCHEDULE_CONFIRMED_BY_LAB','SAMPLE_COLLECTED','SAMPLE_RECEIVED_BY_LAB','TESTING_IN_PROGRESS','REPORT_READY') NOT NULL DEFAULT 'ORDER_CONFIRMED';
                                    """)
                except Exception as e:
                    logger.warning(f"Could not check order_status enum definition: {e}")
            
            # Add status_updated_at to order_items if it doesn't exist
            if "status_updated_at" not in order_items_columns:
                logger.info("Adding status_updated_at column to order_items")
                try:
                    dialect_name = engine.dialect.name
                    if dialect_name == "mysql":
                        conn.execute(text("""
                            ALTER TABLE order_items 
                            ADD COLUMN status_updated_at DATETIME NULL AFTER order_status
                        """))
                    else:
                        conn.execute(text("""
                            ALTER TABLE order_items 
                            ADD COLUMN status_updated_at TIMESTAMP NULL
                        """))
                    conn.commit()
                    logger.info("Successfully added status_updated_at column to order_items")
                except SQLAlchemyError as e:
                    logger.error(f"Failed to add status_updated_at column: {e}")
                    conn.rollback()
            
            # Get current columns for order_status_history
            history_columns = {col["name"] for col in inspector.get_columns("order_status_history")}
            
            # Add order_item_id to order_status_history if it doesn't exist
            if "order_item_id" not in history_columns:
                logger.info("Adding order_item_id column to order_status_history")
                try:
                    dialect_name = engine.dialect.name
                    if dialect_name == "mysql":
                        conn.execute(text("""
                            ALTER TABLE order_status_history 
                            ADD COLUMN order_item_id INT NULL AFTER order_id
                        """))
                    else:
                        conn.execute(text("""
                            ALTER TABLE order_status_history 
                            ADD COLUMN order_item_id INTEGER NULL
                        """))
                    conn.commit()
                    logger.info("Successfully added order_item_id column to order_status_history")
                    
                    # Add index for order_item_id
                    try:
                        if dialect_name == "mysql":
                            conn.execute(text("""
                                CREATE INDEX idx_order_status_history_order_item_id 
                                ON order_status_history(order_item_id)
                            """))
                        else:
                            conn.execute(text("""
                                CREATE INDEX IF NOT EXISTS idx_order_status_history_order_item_id 
                                ON order_status_history(order_item_id)
                            """))
                        conn.commit()
                        logger.info("Successfully created index on order_item_id")
                    except SQLAlchemyError as e:
                        # Index might already exist, ignore
                        logger.warning(f"Could not create index on order_item_id (may already exist): {e}")
                        conn.rollback()
                    
                    # Add foreign key constraint if possible
                    try:
                        conn.execute(text("""
                            ALTER TABLE order_status_history 
                            ADD CONSTRAINT fk_order_status_history_order_item_id 
                            FOREIGN KEY (order_item_id) 
                            REFERENCES order_items(id) 
                            ON DELETE CASCADE
                        """))
                        conn.commit()
                        logger.info("Successfully added foreign key constraint on order_item_id")
                    except SQLAlchemyError as e:
                        # Foreign key might already exist or table might not support it
                        logger.warning(f"Could not add foreign key constraint (may already exist): {e}")
                        conn.rollback()
                        
                except SQLAlchemyError as e:
                    logger.error(f"Failed to add order_item_id column: {e}")
                    conn.rollback()
                    
    except Exception as exc:
        logger.error(f"Failed to add order columns: {exc}", exc_info=True)
        # Don't raise - allow app to continue if migrations fail


def _fix_order_foreign_keys(engine: Engine) -> None:
    """
    Modify foreign key constraints on order_items and orders tables
    to allow deletion of addresses, members, and products.
    Since we use OrderSnapshot, these can be safely deleted.
    """
    try:
        inspector = inspect(engine)
        dialect_name = engine.dialect.name
        
        # Check if tables exist
        if "order_items" not in inspector.get_table_names():
            logger.warning("order_items table does not exist. Skipping FK constraint migration.")
            return
        
        if "orders" not in inspector.get_table_names():
            logger.warning("orders table does not exist. Skipping FK constraint migration.")
            return
        
        with engine.connect() as conn:
            if dialect_name == "mysql":
                try:
                    # Step 1: Make columns nullable in order_items
                    logger.info("Making order_items foreign key columns nullable to allow deletion...")
                    
                    # Check current nullability
                    order_items_columns = {col["name"]: col for col in inspector.get_columns("order_items")}
                    
                    # Make address_id nullable if not already
                    if not order_items_columns.get("address_id", {}).get("nullable", False):
                        logger.info("Making order_items.address_id nullable")
                        conn.execute(text("ALTER TABLE order_items MODIFY COLUMN address_id INT NULL"))
                        conn.commit()
                    
                    # Make member_id nullable if not already
                    if not order_items_columns.get("member_id", {}).get("nullable", False):
                        logger.info("Making order_items.member_id nullable")
                        conn.execute(text("ALTER TABLE order_items MODIFY COLUMN member_id INT NULL"))
                        conn.commit()
                    
                    # Make product_id nullable if not already
                    if not order_items_columns.get("product_id", {}).get("nullable", False):
                        logger.info("Making order_items.product_id nullable")
                        conn.execute(text("ALTER TABLE order_items MODIFY COLUMN product_id INT NULL"))
                        conn.commit()
                    
                    # Step 2: Drop existing foreign key constraints
                    logger.info("Dropping existing foreign key constraints...")
                    
                    # Get existing foreign keys
                    fk_constraints = inspector.get_foreign_keys("order_items")
                    dropped_constraints = set()
                    
                    for fk in fk_constraints:
                        constraint_name = fk.get("name")
                        constrained_columns = fk.get("constrained_columns", [])
                        
                        if constraint_name and constraint_name not in dropped_constraints:
                            # Check if this FK is for address_id, member_id, or product_id
                            if "address_id" in constrained_columns or "member_id" in constrained_columns or "product_id" in constrained_columns:
                                try:
                                    logger.info(f"Dropping FK constraint: {constraint_name} on {constrained_columns}")
                                    conn.execute(text(f"ALTER TABLE order_items DROP FOREIGN KEY `{constraint_name}`"))
                                    conn.commit()
                                    dropped_constraints.add(constraint_name)
                                except Exception as e:
                                    # Constraint might not exist or already dropped
                                    logger.warning(f"Could not drop FK {constraint_name}: {e}")
                                    conn.rollback()
                    
                    # Step 3: Add new foreign key constraints with ON DELETE SET NULL
                    logger.info("Adding new foreign key constraints with ON DELETE SET NULL...")
                    
                    # Check if constraints already exist before adding
                    existing_fks = inspector.get_foreign_keys("order_items")
                    existing_fk_columns = set()
                    for fk in existing_fks:
                        existing_fk_columns.update(fk.get("constrained_columns", []))
                    
                    if "address_id" not in existing_fk_columns:
                        try:
                            conn.execute(text("""
                                ALTER TABLE order_items 
                                ADD CONSTRAINT fk_order_items_address_id 
                                FOREIGN KEY (address_id) 
                                REFERENCES addresses(id) 
                                ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("Added FK constraint for address_id with ON DELETE SET NULL")
                        except Exception as e:
                            logger.warning(f"Could not add FK for address_id: {e}")
                            conn.rollback()
                    
                    if "member_id" not in existing_fk_columns:
                        try:
                            conn.execute(text("""
                                ALTER TABLE order_items 
                                ADD CONSTRAINT fk_order_items_member_id 
                                FOREIGN KEY (member_id) 
                                REFERENCES members(id) 
                                ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("Added FK constraint for member_id with ON DELETE SET NULL")
                        except Exception as e:
                            logger.warning(f"Could not add FK for member_id: {e}")
                            conn.rollback()
                    
                    if "product_id" not in existing_fk_columns:
                        try:
                            conn.execute(text("""
                                ALTER TABLE order_items 
                                ADD CONSTRAINT fk_order_items_product_id 
                                FOREIGN KEY (product_id) 
                                REFERENCES products(ProductId) 
                                ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("Added FK constraint for product_id with ON DELETE SET NULL")
                        except Exception as e:
                            logger.warning(f"Could not add FK for product_id: {e}")
                            conn.rollback()
                    
                    # Step 4: Fix orders.address_id FK
                    orders_fk_constraints = inspector.get_foreign_keys("orders")
                    orders_columns = {col["name"]: col for col in inspector.get_columns("orders")}
                    
                    for fk in orders_fk_constraints:
                        constraint_name = fk.get("name")
                        if constraint_name and "address_id" in fk.get("constrained_columns", []):
                            try:
                                logger.info(f"Dropping FK constraint on orders.address_id: {constraint_name}")
                                conn.execute(text(f"ALTER TABLE orders DROP FOREIGN KEY `{constraint_name}`"))
                                conn.commit()
                                
                                # Make address_id nullable if not already
                                if not orders_columns.get("address_id", {}).get("nullable", False):
                                    logger.info("Making orders.address_id nullable")
                                    conn.execute(text("ALTER TABLE orders MODIFY COLUMN address_id INT NULL"))
                                    conn.commit()
                                
                                break
                            except Exception as e:
                                logger.warning(f"Could not drop orders.address_id FK: {e}")
                                conn.rollback()
                    
                    # Add new FK with SET NULL (check if it doesn't already exist)
                    orders_fk_constraints_after = inspector.get_foreign_keys("orders")
                    has_address_fk = any("address_id" in fk.get("constrained_columns", []) for fk in orders_fk_constraints_after)
                    
                    if not has_address_fk:
                        try:
                            conn.execute(text("""
                                ALTER TABLE orders 
                                ADD CONSTRAINT fk_orders_address_id 
                                FOREIGN KEY (address_id) 
                                REFERENCES addresses(id) 
                                ON DELETE SET NULL
                            """))
                            conn.commit()
                            logger.info("Added FK constraint for orders.address_id with ON DELETE SET NULL")
                        except Exception as e:
                            logger.warning(f"Could not add FK for orders.address_id: {e}")
                            conn.rollback()
                    else:
                        # Make sure address_id is nullable even if FK exists
                        if not orders_columns.get("address_id", {}).get("nullable", False):
                            try:
                                logger.info("Making orders.address_id nullable")
                                conn.execute(text("ALTER TABLE orders MODIFY COLUMN address_id INT NULL"))
                                conn.commit()
                            except Exception as e:
                                logger.warning(f"Could not make orders.address_id nullable: {e}")
                                conn.rollback()
                                
                except Exception as e:
                    logger.error(f"Error fixing order foreign keys: {e}")
                    conn.rollback()
            else:
                logger.warning(f"Foreign key constraint modification not implemented for {dialect_name}")
                
    except Exception as exc:
        logger.error(f"Failed to fix order foreign keys: {exc}", exc_info=True)
        # Don't raise - allow app to continue if migrations fail


def _ensure_audit_log_columns(engine: Engine) -> None:
    """Add identifying columns to audit log tables for clear member/address identification"""
    try:
        inspector = inspect(engine)
        
        # Check if member_audit_logs table exists
        if "member_audit_logs" in inspector.get_table_names():
            member_audit_columns = {col["name"] for col in inspector.get_columns("member_audit_logs")}
            
            # Add member_name column if it doesn't exist
            if "member_name" not in member_audit_columns:
                logger.info("Adding member_name column to member_audit_logs")
                _ensure_column(engine, "member_audit_logs", "member_name", "VARCHAR(255) NULL")
            
            # Add member_identifier column if it doesn't exist
            if "member_identifier" not in member_audit_columns:
                logger.info("Adding member_identifier column to member_audit_logs")
                _ensure_column(engine, "member_audit_logs", "member_identifier", "VARCHAR(100) NULL")
            
            # Add index on member_name if not exists
            try:
                with engine.connect() as conn:
                    indexes = inspector.get_indexes("member_audit_logs")
                    index_names = {idx["name"] for idx in indexes}
                    if "idx_member_audit_logs_member_name" not in index_names and "member_name" in member_audit_columns:
                        conn.execute(text("CREATE INDEX idx_member_audit_logs_member_name ON member_audit_logs(member_name)"))
                        conn.commit()
                        logger.info("Successfully added index on member_name")
            except SQLAlchemyError as e:
                logger.warning(f"Could not create index on member_name (may already exist): {e}")
        
        # Check if address_audit table exists
        if "address_audit" in inspector.get_table_names():
            address_audit_columns = {col["name"] for col in inspector.get_columns("address_audit")}
            
            # Add address_label column if it doesn't exist
            if "address_label" not in address_audit_columns:
                logger.info("Adding address_label column to address_audit")
                _ensure_column(engine, "address_audit", "address_label", "VARCHAR(255) NULL")
            
            # Add address_identifier column if it doesn't exist
            if "address_identifier" not in address_audit_columns:
                logger.info("Adding address_identifier column to address_audit")
                _ensure_column(engine, "address_audit", "address_identifier", "VARCHAR(200) NULL")
            
            # Make address_id nullable (for deletion logs) - try to alter if column exists
            try:
                with engine.connect() as conn:
                    conn.execute(text("ALTER TABLE address_audit MODIFY COLUMN address_id INT NULL"))
                    conn.commit()
                    logger.info("Made address_id nullable in address_audit")
            except SQLAlchemyError as e:
                logger.warning(f"Could not make address_id nullable (may already be nullable or column doesn't exist): {e}")
            
            # Add index on address_label if not exists
            try:
                with engine.connect() as conn:
                    indexes = inspector.get_indexes("address_audit")
                    index_names = {idx["name"] for idx in indexes}
                    if "idx_address_audit_address_label" not in index_names and "address_label" in address_audit_columns:
                        conn.execute(text("CREATE INDEX idx_address_audit_address_label ON address_audit(address_label)"))
                        conn.commit()
                        logger.info("Successfully added index on address_label")
            except SQLAlchemyError as e:
                logger.warning(f"Could not create index on address_label (may already exist): {e}")
        
    except SQLAlchemyError as e:
        logger.error(f"Failed to ensure audit log columns: {e}")
        # Don't raise - allow app to continue if migrations fail


def run_startup_migrations(engine: Engine) -> None:
    """
    Lightweight, idempotent migrations for environments without Alembic.
    Ensures new tables/columns exist and backfills required data.
    """
    # Ensure categories table exists
    Category.__table__.create(bind=engine, checkfirst=True)

    # Ensure new columns exist
    _ensure_column(engine, "products", "category_id", "INT NULL")
    _ensure_column(engine, "members", "dob", "DATE NULL")
    _ensure_column(engine, "members", "associated_category_id", "INT NULL")
    
    # Ensure order-related columns exist (per-item status tracking)
    _ensure_order_columns(engine)
    
    # Fix foreign key constraints to allow deletion (we use OrderSnapshot for data integrity)
    _fix_order_foreign_keys(engine)
    
    # Ensure audit log identifying columns exist
    _ensure_audit_log_columns(engine)

    # Backfill data using ORM sessions
    with SessionLocal() as session:
        _backfill_product_categories(session)
        _backfill_member_categories(session)

