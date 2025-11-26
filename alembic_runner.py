"""
Alembic migration runner for application startup.
This module provides functions to run Alembic migrations programmatically.
"""
import logging
from sqlalchemy.exc import OperationalError
from alembic import command
from alembic.config import Config
from database import DATABASE_URL

logger = logging.getLogger(__name__)


def run_migrations() -> None:
    """
    Run Alembic migrations programmatically.
    This function is called during application startup to ensure database is up to date.
    """
    try:
        # Create Alembic configuration
        alembic_cfg = Config("alembic.ini")
        
        # Set the database URL
        alembic_cfg.set_main_option("sqlalchemy.url", DATABASE_URL)
        
        logger.info("Running Alembic migrations...")
        
        # Run migrations to head (latest version)
        command.upgrade(alembic_cfg, "head")
        
        logger.info("Alembic migrations completed successfully")
        
    except OperationalError as e:
        logger.error(f"Failed to connect to database during migrations: {e}")
        logger.warning("Migrations will be retried on next startup")
        raise
    except Exception as e:
        logger.error(f"Unexpected error during Alembic migrations: {e}", exc_info=True)
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

