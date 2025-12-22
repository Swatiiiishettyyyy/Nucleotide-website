"""
Member transfer CRUD operations.
Handles initiation, verification, and execution of member transfers.
"""
import uuid
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
from fastapi import HTTPException, status
import logging

from .Member_transfer_model import MemberTransferLog
from .Member_model import Member
from Login_module.User.user_session_crud import get_user_by_mobile, get_user_by_id
from Login_module.Utils.datetime_utils import now_ist
# Orders are shared, not copied - no need to import Order models here
from Cart_module.Cart_model import CartItem
from Consent_module.Consent_model import UserConsent
from Consent_module.Consent_crud import get_consent_by_member_and_product

logger = logging.getLogger(__name__)


def create_transfer_log(
    db: Session,
    old_user_id: int,
    old_member_id: int,
    member_phone: str,
    initiated_by_user_id: int,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    otp_code: Optional[str] = None,
    otp_expires_at: Optional[datetime] = None
) -> MemberTransferLog:
    """
    Create a new member transfer log entry.
    """
    transfer_log = MemberTransferLog(
        old_user_id=old_user_id,
        old_member_id=old_member_id,
        member_phone=member_phone,
        transfer_status="PENDING_OTP",
        otp_code=otp_code,
        otp_expires_at=otp_expires_at,
        initiated_by_user_id=initiated_by_user_id,
        ip_address=ip_address,
        user_agent=user_agent,
        correlation_id=str(uuid.uuid4())
    )
    db.add(transfer_log)
    db.commit()
    db.refresh(transfer_log)
    return transfer_log


def get_transfer_log_by_id(db: Session, transfer_log_id: int) -> Optional[MemberTransferLog]:
    """Get transfer log by ID."""
    return db.query(MemberTransferLog).filter(MemberTransferLog.id == transfer_log_id).first()


def get_pending_transfer_by_phone(db: Session, phone: str) -> Optional[MemberTransferLog]:
    """
    Get pending transfer log for a phone number.
    Returns the most recent pending transfer.
    """
    return db.query(MemberTransferLog).filter(
        MemberTransferLog.member_phone == phone,
        MemberTransferLog.transfer_status.in_(["PENDING_OTP", "OTP_VERIFIED"])
    ).order_by(MemberTransferLog.created_at.desc()).first()


def mark_transfer_otp_verified(
    db: Session,
    phone: str
) -> Optional[MemberTransferLog]:
    """
    Mark transfer OTP as verified after normal OTP verification succeeds.
    This is called from the verify_otp endpoint after OTP is verified.
    """
    transfer_log = get_pending_transfer_by_phone(db, phone)
    
    if not transfer_log:
        return None
    
    # Check if OTP is expired
    if transfer_log.otp_expires_at and transfer_log.otp_expires_at < now_ist():
        transfer_log.transfer_status = "CANCELLED"
        transfer_log.error_message = "OTP expired"
        db.commit()
        return None
    
    # Mark as verified (OTP was already verified in normal flow)
    transfer_log.transfer_status = "OTP_VERIFIED"
    transfer_log.otp_verified_at = now_ist()
    db.commit()
    db.refresh(transfer_log)
    
    return transfer_log


def execute_member_transfer(
    db: Session,
    transfer_log_id: int,
    new_user_id: int
) -> MemberTransferLog:
    """
    Execute the member transfer after OTP verification.
    This function:
    1. Updates member ownership
    2. Copies orders and order items
    3. Moves cart items
    4. Copies consents
    5. Updates transfer log status
    """
    transfer_log = get_transfer_log_by_id(db, transfer_log_id)
    
    if not transfer_log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transfer log not found"
        )
    
    if transfer_log.transfer_status != "OTP_VERIFIED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transfer status is {transfer_log.transfer_status}, expected OTP_VERIFIED"
        )
    
    old_user_id = transfer_log.old_user_id
    old_member_id = transfer_log.old_member_id
    
    # Get member to transfer
    member = db.query(Member).filter(Member.id == old_member_id).first()
    if not member:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found"
        )
    
    # Verify member belongs to old user
    if member.user_id != old_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Member does not belong to the specified old user"
        )
    
    try:
        # Validate new user exists
        new_user = get_user_by_id(db, new_user_id)
        if not new_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="New user not found"
            )
        
        # Start transaction
        transfer_log.transfer_status = "TRANSFER_IN_PROGRESS"
        db.flush()  # Flush but don't commit yet
        
        # Step 1: Update member ownership
        # Before setting is_self_profile = True on transferred member,
        # check if new user already has a member with is_self_profile = True
        # If yes, unset it (the transferred member will become the new self profile)
        existing_self_profile = db.query(Member).filter(
            Member.user_id == new_user_id,
            Member.is_self_profile == True,
            Member.is_deleted == False
        ).first()
        
        if existing_self_profile:
            # Unset is_self_profile from existing member
            existing_self_profile.is_self_profile = False
            logger.info(
                f"Unsetting is_self_profile from member {existing_self_profile.id} "
                f"for user {new_user_id} before transferring member {old_member_id}"
            )
        
        member.user_id = new_user_id
        member.is_self_profile = True  # Transferred member becomes new user's self profile
        member.relation = "Self"  # Update relation to Self
        new_member_id = member.id  # Same member, just ownership changed
        
        # Update genetic test participant record if it exists
        # This is critical for data consistency - if it fails, the transfer should fail
        from GeneticTest_module.GeneticTest_crud import update_participant_on_member_transfer
        try:
            update_participant_on_member_transfer(db, new_member_id, new_user_id)
        except Exception as e:
            logger.error(f"Error updating genetic test participant on member transfer: {str(e)}", exc_info=True)
            # Re-raise to ensure transaction rollback and data consistency
            raise
        
        transfer_log.new_user_id = new_user_id
        transfer_log.new_member_id = new_member_id
        db.flush()
        
        # Step 2: Move cart items (orders are shared, not copied)
        cart_items_moved = _move_member_cart_items(
            db, old_user_id, new_user_id, old_member_id, new_member_id
        )
        transfer_log.cart_items_moved_count = cart_items_moved
        db.flush()
        
        # Step 3: Copy consents
        consents_copied = _copy_member_consents(
            db, old_user_id, new_user_id, old_member_id, new_member_id
        )
        transfer_log.consents_copied_count = consents_copied
        db.flush()
        
        # Step 4: Mark transfer as completed
        transfer_log.transfer_status = "COMPLETED"
        transfer_log.transfer_completed_at = now_ist()
        
        db.commit()
        db.refresh(transfer_log)
        
        logger.info(
            f"Member transfer completed: member_id={old_member_id}, "
            f"old_user_id={old_user_id}, new_user_id={new_user_id}, "
            f"cart_items={cart_items_moved}, consents={consents_copied}"
        )
        
        return transfer_log
        
    except Exception as e:
        db.rollback()
        logger.error(f"Error executing member transfer: {e}", exc_info=True)
        transfer_log.transfer_status = "FAILED"
        transfer_log.error_message = str(e)
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Transfer execution failed: {str(e)}"
        )
# Order copying removed - orders are now shared via query logic (see Order_crud.get_user_orders)

def _move_member_cart_items(
    db: Session,
    old_user_id: int,
    new_user_id: int,
    old_member_id: int,
    new_member_id: int
) -> int:
    """
    Move cart items from old user to new user.
    Only moves items if all items in a group belong to this member.
    If a group has items for other members, those items are NOT moved.
    Returns count of items moved.
    """
    cart_items = db.query(CartItem).filter(
        CartItem.user_id == old_user_id,
        CartItem.member_id == old_member_id
    ).all()
    
    if not cart_items:
        return 0
    
    # Check for group_id conflicts
    group_ids = {item.group_id for item in cart_items if item.group_id}
    processed_groups = set()  # Track processed group_ids to avoid duplicates
    
    # For each group, check if all items in group are for this member
    items_to_move = []
    for item in cart_items:
        if item.group_id and item.group_id not in processed_groups:
            processed_groups.add(item.group_id)
            # Check if other items in this group belong to other members
            group_items = db.query(CartItem).filter(
                CartItem.group_id == item.group_id,
                CartItem.user_id == old_user_id
            ).all()
            
            # Only move if ALL items in group are for this member
            if all(gi.member_id == old_member_id for gi in group_items):
                items_to_move.extend(group_items)
            # If group has items for other members, do NOT move any items from this group
        elif not item.group_id:
            # Single items (no group) can always be moved
            items_to_move.append(item)
    
    # Move items
    moved_count = 0
    for item in items_to_move:
        item.user_id = new_user_id
        item.member_id = new_member_id
        moved_count += 1
    
    return moved_count


def _copy_member_consents(
    db: Session,
    old_user_id: int,
    new_user_id: int,
    old_member_id: int,
    new_member_id: int
) -> int:
    """
    Copy consent records for the member.
    Returns count of consents copied.
    """
    consents = db.query(UserConsent).filter(
        UserConsent.member_id == old_member_id,
        UserConsent.user_id == old_user_id
    ).all()
    
    if not consents:
        return 0
    
    # Get new user's phone number once (performance optimization)
    new_user = get_user_by_id(db, new_user_id)
    new_user_phone = new_user.mobile if new_user else None
    
    consents_copied = 0
    for original_consent in consents:
        # Check if consent already exists for new user/member/product
        existing = get_consent_by_member_and_product(db, new_member_id, original_consent.product_id)
        
        if existing:
            # Update existing consent with transfer info
            existing.transferred_at = now_ist()
            existing.linked_from_consent_id = original_consent.id
        else:
            # Use new user's phone, fallback to original if not available
            user_phone = new_user_phone if new_user_phone else original_consent.user_phone
            
            # Create new consent
            new_consent = UserConsent(
                user_id=new_user_id,
                user_phone=user_phone,  # Use new user's phone number
                member_id=new_member_id,
                product_id=original_consent.product_id,
                product=original_consent.product,
                consent_given=original_consent.consent_given,
                consent_source=original_consent.consent_source,
                status=original_consent.status,
                created_at=original_consent.created_at,  # Preserve original consent date
                linked_from_consent_id=original_consent.id,
                transferred_at=now_ist()
            )
            db.add(new_consent)
            consents_copied += 1
    
    return consents_copied

