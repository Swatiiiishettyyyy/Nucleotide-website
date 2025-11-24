import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

# Attempt to load environment variables from multiple common locations
BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
ENV_CANDIDATES = [
    BASE_DIR / ".env",         # database module specific
    PROJECT_ROOT / ".env",     # project root
]

for env_path in ENV_CANDIDATES:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    # Fall back to default load (will pick up system env vars if already set)
    load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Some hosting environments accidentally prepend "DATABASE_URL=" to the value
# (e.g. when copying `export DATABASE_URL=...`). Strip that prefix if present
PREFIX = "DATABASE_URL="
if DATABASE_URL.startswith(PREFIX):
    DATABASE_URL = DATABASE_URL[len(PREFIX):].strip()

# Provide a sensible default for local development if DATABASE_URL is missing
if not DATABASE_URL:
    default_sqlite_path = PROJECT_ROOT / "nucleotide.db"
    DATABASE_URL = f"sqlite:///{default_sqlite_path.as_posix()}"
    logger.warning(
        "DATABASE_URL not found in environment. Falling back to SQLite at %s",
        default_sqlite_path
    )

# Database connection pooling configuration (used for non-SQLite databases)
POOL_SIZE = int(os.getenv("DB_POOL_SIZE", 10))
MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", 20))
POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", 30))
POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", 3600))  # Recycle connections after 1 hour

engine_kwargs = {
    "echo": False,
    "future": True,
    "pool_pre_ping": True,
}

# SQLite has different pooling requirements
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs.update(
        {
            "poolclass": QueuePool,
            "pool_size": POOL_SIZE,
            "max_overflow": MAX_OVERFLOW,
            "pool_timeout": POOL_TIMEOUT,
            "pool_recycle": POOL_RECYCLE,
        }
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)

Base = declarative_base()

# Log connection pool status for observability
if DATABASE_URL.startswith("sqlite"):
    logger.info("Database configured with SQLite at %s", DATABASE_URL)
else:
    logger.info("Database connection pool configured: size=%s, max_overflow=%s", POOL_SIZE, MAX_OVERFLOW)
