"""
Genetic Test Participant CRUD operations.
Handles tracking of genetic test participants.
"""
from sqlalchemy.orm import Session
from typing import Optional, List
import logging

from .GeneticTest_model import GeneticTestParticipant

logger = logging.getLogger(__name__)


def get_participant_by_member_id(
    db: Session,
    member_id: int
) -> Optional[GeneticTestParticipant]:
    """Get participant record by member ID."""
    return db.query(GeneticTestParticipant).filter(
        GeneticTestParticipant.member_id == member_id
    ).first()


def get_participant_by_mobile(
    db: Session,
    mobile: str
) -> Optional[GeneticTestParticipant]:
    """Get participant record by mobile number."""
    return db.query(GeneticTestParticipant).filter(
        GeneticTestParticipant.mobile == mobile
    ).first()


def get_all_participants(
    db: Session,
    has_taken_test: Optional[bool] = None,
    plan_type: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[GeneticTestParticipant]:
    """Get all participants with optional filters."""
    query = db.query(GeneticTestParticipant)
    
    if has_taken_test is not None:
        query = query.filter(GeneticTestParticipant.has_taken_genetic_test == has_taken_test)
    
    if plan_type:
        query = query.filter(GeneticTestParticipant.plan_type == plan_type)
    
    return query.order_by(GeneticTestParticipant.created_at.desc()).offset(offset).limit(limit).all()


def create_or_update_participant(
    db: Session,
    user_id: int,
    member_id: int,
    mobile: str,
    name: str,
    plan_type: Optional[str] = None,
    product_id: Optional[int] = None,
    category_id: Optional[int] = None,
    order_id: Optional[int] = None,
    has_taken_genetic_test: bool = True
) -> GeneticTestParticipant:
    """
    Create or update participant record.
    If participant exists, updates the record. Otherwise creates new one.
    """
    # Check if participant already exists for this member
    participant = get_participant_by_member_id(db, member_id)
    
    if participant:
        # Update existing record
        participant.user_id = user_id
        participant.mobile = mobile  # Update mobile (denormalized)
        participant.name = name  # Update name (denormalized)
        participant.has_taken_genetic_test = has_taken_genetic_test
        participant.plan_type = plan_type  # Update to latest plan type
        participant.product_id = product_id
        participant.category_id = category_id
        participant.order_id = order_id  # Update to latest order
        logger.info(f"Updated genetic test participant record for member {member_id}")
    else:
        # Create new record
        participant = GeneticTestParticipant(
            user_id=user_id,
            member_id=member_id,
            mobile=mobile,
            name=name,
            has_taken_genetic_test=has_taken_genetic_test,
            plan_type=plan_type,
            product_id=product_id,
            category_id=category_id,
            order_id=order_id
        )
        db.add(participant)
        logger.info(f"Created new genetic test participant record for member {member_id}")
    
    db.flush()
    return participant


def update_participant_on_member_transfer(
    db: Session,
    member_id: int,
    new_user_id: int
) -> Optional[GeneticTestParticipant]:
    """
    Update participant record when member is transferred to new user.
    Updates user_id but keeps member_id, mobile, name, and test data.
    """
    participant = get_participant_by_member_id(db, member_id)
    
    if participant:
        participant.user_id = new_user_id
        db.flush()
        logger.info(f"Updated participant user_id to {new_user_id} for member {member_id}")
    
    return participant


def check_if_member_has_taken_test(
    db: Session,
    member_id: Optional[int] = None,
    mobile: Optional[str] = None
) -> bool:
    """
    Check if a member has taken genetic test.
    Can query by member_id or mobile.
    """
    if member_id:
        participant = get_participant_by_member_id(db, member_id)
        return participant.has_taken_genetic_test if participant else False
    
    if mobile:
        participant = get_participant_by_mobile(db, mobile)
        return participant.has_taken_genetic_test if participant else False
    
    return False


def get_participant_info(
    db: Session,
    member_id: Optional[int] = None,
    mobile: Optional[str] = None
) -> Optional[dict]:
    """
    Get participant information including test status and plan type.
    Returns dict with has_taken_test and plan_type.
    """
    participant = None
    
    if member_id:
        participant = get_participant_by_member_id(db, member_id)
    elif mobile:
        participant = get_participant_by_mobile(db, mobile)
    
    if participant:
        return {
            "member_id": participant.member_id,
            "mobile": participant.mobile,
            "name": participant.name,
            "has_taken_genetic_test": participant.has_taken_genetic_test,
            "plan_type": participant.plan_type,
            "product_id": participant.product_id,
            "order_id": participant.order_id
        }
    
    return None

