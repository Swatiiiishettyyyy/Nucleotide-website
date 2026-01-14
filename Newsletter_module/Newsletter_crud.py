from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import Optional
import logging
from .Newsletter_model import NewsletterSubscription
from Login_module.Utils.datetime_utils import now_ist

logger = logging.getLogger(__name__)


def create_newsletter_subscription(
    db: Session,
    email: str,
    user_id: Optional[int] = None
) -> NewsletterSubscription:
    """
    Create a new newsletter subscription.
    If email already exists and is active, returns existing subscription.
    If email exists but is inactive, reactivates it.
    """
    # Normalize email (lowercase, strip whitespace)
    email = email.lower().strip()
    
    # Check if subscription already exists
    existing = db.query(NewsletterSubscription).filter(
        NewsletterSubscription.email == email
    ).first()
    
    if existing:
        # If already active, return existing
        if existing.is_active:
            logger.info(f"Newsletter subscription already exists for email: {email}")
            return existing
        
        # If inactive, reactivate it
        existing.is_active = True
        existing.unsubscribed_at = None
        existing.user_id = user_id  # Update user_id if provided
        db.commit()
        db.refresh(existing)
        logger.info(f"Reactivated newsletter subscription for email: {email}")
        return existing
    
    # Create new subscription
    subscription = NewsletterSubscription(
        email=email,
        user_id=user_id,
        is_active=True
    )
    
    try:
        db.add(subscription)
        db.commit()
        db.refresh(subscription)
        logger.info(f"Created new newsletter subscription for email: {email}, user_id: {user_id}")
        return subscription
    except IntegrityError as e:
        db.rollback()
        # Handle race condition - another request might have created it
        existing = db.query(NewsletterSubscription).filter(
            NewsletterSubscription.email == email
        ).first()
        if existing:
            if not existing.is_active:
                existing.is_active = True
                existing.unsubscribed_at = None
                existing.user_id = user_id
                db.commit()
                db.refresh(existing)
                return existing
            return existing
        raise


def get_subscription_by_email(
    db: Session,
    email: str
) -> Optional[NewsletterSubscription]:
    """Get newsletter subscription by email"""
    email = email.lower().strip()
    return db.query(NewsletterSubscription).filter(
        NewsletterSubscription.email == email
    ).first()

