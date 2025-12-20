"""
Script to create database tables.
Run this script to initialize the database schema.

Usage:
    python create_tables.py
    OR
    python -m gmeet_api.create_tables
"""
import sys
import os
from pathlib import Path
import importlib.util
import types

# Add parent directory to path to import shared database
BASE_DIR = Path(__file__).resolve().parent
PARENT_DIR = BASE_DIR.parent
sys.path.insert(0, str(PARENT_DIR))
sys.path.insert(0, str(BASE_DIR))

# Import shared database from parent
import database

# Create mock package structure BEFORE importing models
gmeet_api_module = types.ModuleType('gmeet_api')
gmeet_api_module.database = database
sys.modules['gmeet_api'] = gmeet_api_module
sys.modules['gmeet_api.database'] = database

# Now load models.py using importlib to handle relative imports
models_path = BASE_DIR / "models.py"
spec = importlib.util.spec_from_file_location("gmeet_api.models", models_path)
models_module = importlib.util.module_from_spec(spec)
# Set the parent package so relative imports work
models_module.__package__ = 'gmeet_api'
models_module.__name__ = 'gmeet_api.models'
sys.modules['gmeet_api.models'] = models_module
spec.loader.exec_module(models_module)

# Also add to sys.modules as 'models' for convenience
sys.modules['models'] = models_module

import logging
from database import Base, engine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_tables():
    """Create all database tables."""
    try:
        logger.info("Creating database tables...")
        # Import models to register them with Base
        from models import (
            CounsellorToken,
            CounsellorBooking,
            CounsellorActivityLog,
            CounsellorGmeetList
        )
        Base.metadata.create_all(bind=engine)
        logger.info("✅ Database tables created successfully!")
        logger.info("Created tables:")
        logger.info("  - counsellor_gmeet_tokens")
        logger.info("  - counsellor_gmeet_bookings")
        logger.info("  - counsellor_gmeet_activity_logs")
        logger.info("  - counsellor_gmeet_list")
    except Exception as e:
        logger.error(f"❌ Failed to create tables: {e}")
        raise

if __name__ == "__main__":
    create_tables()

