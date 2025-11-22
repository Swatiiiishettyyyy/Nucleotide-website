"""
Scheduler setup for background tasks.
Uses APScheduler to run periodic cleanup jobs.
"""
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .session_cleanup import cleanup_sessions_job

logger = logging.getLogger(__name__)

# Global scheduler instance
scheduler = None


def start_scheduler():
    """
    Start the background scheduler for periodic tasks.
    - Session cleanup: runs every 90 minutes (1.5 hours)
    """
    global scheduler
    
    if scheduler is not None:
        logger.warning("Scheduler is already running")
        return scheduler
    
    scheduler = BackgroundScheduler()
    
    # Schedule session cleanup every 90 minutes (1.5 hours, between 1-2 hours as specified)
    scheduler.add_job(
        cleanup_sessions_job,
        trigger=IntervalTrigger(minutes=90),
        id='session_cleanup',
        name='Cleanup inactive sessions',
        replace_existing=True
    )
    
    scheduler.start()
    logger.info("Background scheduler started. Session cleanup scheduled every 90 minutes.")
    
    return scheduler


def shutdown_scheduler():
    """
    Shutdown the background scheduler.
    """
    global scheduler
    
    if scheduler is not None:
        scheduler.shutdown()
        scheduler = None
        logger.info("Background scheduler stopped.")




