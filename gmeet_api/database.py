"""
Database connection and session management for Google Meet API.
"""
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Load environment variables
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent.parent
ENV_CANDIDATES = [
    BASE_DIR / ".env",
    PROJECT_ROOT / ".env",
    BASE_DIR.parent / ".env",
]

for env_path in ENV_CANDIDATES:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        logger.info(f"Loaded .env from: {env_path}")
        break
else:
    load_dotenv()
    logger.warning("No .env file found, using system environment variables")

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Strip prefix if accidentally included
PREFIX = "DATABASE_URL="
if DATABASE_URL.startswith(PREFIX):
    DATABASE_URL = DATABASE_URL[len(PREFIX):].strip()

if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL not found in environment variables. "
        "Please set it in your .env file."
    )

# Database connection pooling configuration
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 20))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 30))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 3600))

engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,
    "poolclass": QueuePool,
    "pool_size": POOL_SIZE,
    "max_overflow": MAX_OVERFLOW,
    "pool_timeout": POOL_TIMEOUT,
    "pool_recycle": POOL_RECYCLE,
}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()

logger.info(f"Database connection pool configured: size={POOL_SIZE}, max_overflow={MAX_OVERFLOW}")

