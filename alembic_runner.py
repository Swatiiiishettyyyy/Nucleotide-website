"""
Alembic migration runner for application startup.
This module provides functions to run Alembic migrations programmatically.
"""
import logging
import os
import signal
import threading
from contextlib import contextmanager
from sqlalchemy.exc import OperationalError, TimeoutError as SQLTimeoutError
from alembic import command
from alembic.config import Config
from database import DATABASE_URL, engine

logger = logging.getLogger(__name__)

# Allow skipping migrations via environment variable (useful for debugging)
SKIP_MIGRATIONS = os.getenv("SKIP_MIGRATIONS", "false").lower() in ("true", "1", "yes")


@contextmanager
def timeout_handler(timeout_seconds=30):
    """Context manager to handle timeouts during migrations."""
    def timeout_signal_handler(signum, frame):
        raise TimeoutError(f"Migration operation timed out after {timeout_seconds} seconds")
    
    # Set up signal handler for timeout (Unix only)
    if hasattr(signal, 'SIGALRM'):
        old_handler = signal.signal(signal.SIGALRM, timeout_signal_handler)
        signal.alarm(timeout_seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows doesn't support SIGALRM, so we'll just proceed without timeout
        # The database connection timeout should handle this
        yield


def test_database_connection() -> bool:
    """Test if database connection is available before running migrations."""
    try:
        logger.info("Testing database connection...")
        from sqlalchemy import text
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False


def run_migrations_with_timeout(alembic_cfg, timeout_seconds=30):
    """Run migrations in a thread with timeout support (works on Windows)."""
    result = {"success": False, "error": None, "completed": False}
    exception_occurred = threading.Event()
    
    def run_migration():
        try:
            logger.info("Migration thread started - executing migrations...")
            command.upgrade(alembic_cfg, "head")
            result["success"] = True
            result["completed"] = True
            logger.info("Migration thread completed successfully")
        except Exception as e:
            result["error"] = e
            result["completed"] = True
            exception_occurred.set()
            logger.error(f"Migration thread encountered error: {e}", exc_info=True)
    
    thread = threading.Thread(target=run_migration, daemon=True, name="MigrationThread")
    thread.start()
    
    # Wait for the thread with timeout
    thread.join(timeout=timeout_seconds)
    
    if thread.is_alive():
        # Thread is still running - migration timed out
        logger.warning(f"Migration operation timed out after {timeout_seconds} seconds")
        logger.warning("Migration will continue in background. Application will start anyway.")
        logger.warning("Migrations will be retried on next startup if not completed")
        return False
    
    if result["error"]:
        raise result["error"]
    
    return result["success"]


def check_migrations_needed(alembic_cfg) -> bool:
    """Check if migrations are needed by comparing current revision with head."""
    try:
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        
        script = ScriptDirectory.from_config(alembic_cfg)
        head_revision = script.get_current_head()
        
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
        
        if current_rev is None:
            logger.info("No migrations have been applied - migrations are needed")
            return True
        
        if current_rev != head_revision:
            logger.info(f"Migrations needed: current={current_rev}, head={head_revision}")
            return True
        
        logger.info(f"Database is up to date: current={current_rev}, head={head_revision}")
        return False
    except Exception as e:
        logger.warning(f"Could not check migration status: {e}. Will attempt to run migrations anyway.")
        return True


def run_migrations() -> None:
    """
    Run Alembic migrations programmatically.
    This function is called during application startup to ensure database is up to date.
    """
    # Check if migrations should be skipped
    if SKIP_MIGRATIONS:
        logger.warning("Migrations skipped due to SKIP_MIGRATIONS environment variable")
        return
    
    # First, test database connection
    if not test_database_connection():
        logger.warning("Skipping migrations due to database connection failure")
        return
    
    try:
        # Create Alembic configuration
        logger.info("Configuring Alembic...")
        alembic_cfg = Config("alembic.ini")
        
        # Set the database URL
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        
        # Check if migrations are actually needed
        if not check_migrations_needed(alembic_cfg):
            logger.info("No migrations needed - database is up to date")
            return
        
        logger.info("Running Alembic migrations to head...")
        # Log database info (without credentials)
        if '@' in DATABASE_URL:
            db_info = DATABASE_URL.split('@')[-1]
            logger.info(f"Database: {db_info}")
        else:
            logger.info("Database: configured")
        
        # Run migrations to head (latest version)
        # Use threading timeout for Windows compatibility
        # Use shorter timeout (30 seconds) to prevent long startup delays
        try:
            if hasattr(signal, 'SIGALRM'):
                # Unix/Linux - use signal-based timeout
                logger.info("Using signal-based timeout (30 seconds)...")
                with timeout_handler(timeout_seconds=30):
                    command.upgrade(alembic_cfg, "head")
                logger.info("Alembic migrations completed successfully")
            else:
                # Windows - use threading timeout
                logger.info("Using thread-based timeout (30 seconds)...")
                success = run_migrations_with_timeout(alembic_cfg, timeout_seconds=30)
                if success:
                    logger.info("Alembic migrations completed successfully")
                else:
                    # Timeout occurred - app will continue to start
                    logger.warning("Migration timeout - application will start anyway")
                    logger.warning("Migrations will be retried on next startup")
                    return
            
        except TimeoutError as e:
            logger.error(f"Migration timed out: {e}")
            logger.warning("Migrations will be retried on next startup")
        except KeyboardInterrupt:
            logger.warning("Migration interrupted by user")
            raise
        
    except OperationalError as e:
        logger.error(f"Failed to connect to database during migrations: {e}")
        logger.warning("Migrations will be retried on next startup")
        # Don't raise - allow app to continue even if database is temporarily unavailable
    except SQLTimeoutError as e:
        logger.error(f"Database operation timed out during migrations: {e}")
        logger.warning("Migrations will be retried on next startup")
    except Exception as e:
        logger.error(f"Unexpected error during Alembic migrations: {e}", exc_info=True)
        logger.warning("Migrations will be retried on next startup")
        # Don't raise - allow app to continue if migrations fail
        # In production, you might want to raise here


def get_current_revision() -> str:
    """
    Get the current database revision.
    Returns the revision string or 'None' if no migrations have been applied.
    """
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        
        from alembic.script import ScriptDirectory
        from alembic.runtime.migration import MigrationContext
        from database import engine
        
        script = ScriptDirectory.from_config(alembic_cfg)
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            return current_rev if current_rev else 'None'
    except Exception as e:
        logger.error(f"Failed to get current revision: {e}")
        return 'Unknown'

