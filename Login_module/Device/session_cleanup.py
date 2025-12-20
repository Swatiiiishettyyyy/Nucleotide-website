"""
Session cleanup cron job.
Deletes inactive or deleted sessions every 1-2 hours.
"""
import logging
from datetime import datetime
from sqlalchemy.orm import Session
from database import SessionLocal
from Login_module.Utils.datetime_utils import now_ist
from .Device_session_crud import cleanup_inactive_sessions

logger = logging.getLogger(__name__)


def cleanup_sessions_job():
    """
    Cron job function to cleanup inactive sessions.
    Runs every 1-2 hours to delete old inactive sessions.
    """
    db: Session = SessionLocal()
    try:
        # Cleanup sessions that have been inactive for 24 hours
        deleted_count = cleanup_inactive_sessions(db, hours_inactive=24)
        logger.info(f"Session cleanup completed at {now_ist()}. Deleted {deleted_count} inactive sessions.")
    except Exception as e:
        logger.error(f"Error during session cleanup: {str(e)}")
    finally:
        db.close()




