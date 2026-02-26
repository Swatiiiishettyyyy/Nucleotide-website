import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User

from .Notification_schema import (
    SendNotificationRequest,
    NotificationItem,
    UnreadCountResponse,
    NotificationSettingsResponse,
    NotificationSettingsUpdate,
)
from .Notification_crud import (
    create_notification,
    list_notifications,
    get_device_tokens_for_user,
    delete_device_tokens_by_value,
    mark_notification_read,
    get_unread_count,
)
from . import firebase_service
from Login_module.Utils.datetime_utils import to_ist_isoformat

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Notifications"])


@router.post("/notifications/send")
def post_notifications_send(
    body: SendNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a notification in DB and send push via FCM to the user's devices. Requires auth."""
    if body.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id must match the authenticated user",
        )
    notification = create_notification(
        db,
        user_id=body.user_id,
        title=body.title,
        message=body.message,
        type=body.type,
    )
    tokens = get_device_tokens_for_user(db, body.user_id)
    firebase_service.init_firebase()
    if not tokens:
        logger.error("Skipping FCM: no device tokens for user_id=%s", body.user_id)
    elif not firebase_service.firebase_initialized:
        logger.error("Skipping FCM: Firebase not initialized")
    else:
        data = {"notification_id": str(notification.id), "type": body.type or ""}
        invalid_tokens, success_count = firebase_service.send_fcm_to_tokens(
            tokens=tokens,
            title=body.title,
            body=body.message,
            data=data,
        )
        if success_count is not None:
            if success_count > 0:
                logger.info("FCM send attempted for user_id=%s, delivered to %s device(s)", body.user_id, success_count)
            else:
                logger.warning("FCM send attempted for user_id=%s, delivered to 0 device(s)", body.user_id)
        if invalid_tokens:
            from config import settings
            if settings.REMOVE_INVALID_FCM_TOKENS:
                removed = delete_device_tokens_by_value(db, invalid_tokens)
                logger.info("Removed %s invalid FCM token(s) for user_id=%s", removed, body.user_id)
            else:
                logger.debug("Invalid FCM token(s) for user_id=%s not removed (REMOVE_INVALID_FCM_TOKENS=false)", body.user_id)
    return {"status": "success", "message": "Notification created and sent"}


@router.get("/notifications", response_model=list[NotificationItem])
def get_notifications(
    limit: Optional[int] = None,
    unread_only: bool = False,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List notifications for the authenticated user. Optional limit and unread_only filter. Timestamps in IST."""
    items = list_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        unread_only=unread_only,
    )
    return [
        NotificationItem(
            id=n.id,
            title=n.title,
            message=n.message,
            type=n.type,
            is_read=n.is_read,
            created_at=to_ist_isoformat(n.created_at),
        )
        for n in items
    ]


@router.put("/notifications/{notification_id}/read", response_model=NotificationItem)
def put_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read. Requires auth; only own notifications can be marked read. Returns notification with created_at in IST."""
    updated = mark_notification_read(db, notification_id=notification_id, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationItem(
        id=updated.id,
        title=updated.title,
        message=updated.message,
        type=updated.type,
        is_read=updated.is_read,
        created_at=to_ist_isoformat(updated.created_at),
    )


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_notifications_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return count of unread notifications for the authenticated user."""
    count = get_unread_count(db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)


@router.get("/notifications/settings", response_model=NotificationSettingsResponse)
def get_notification_settings(
    current_user: User = Depends(get_current_user),
):
    """Get notification preference for the authenticated user (e.g. for Settings screen toggle)."""
    enabled = getattr(current_user, "notifications_enabled", True)
    return NotificationSettingsResponse(notifications_enabled=enabled)


@router.patch("/notifications/settings", response_model=NotificationSettingsResponse)
def patch_notification_settings(
    body: NotificationSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Update notification preference (enable/disable push). Used when user toggles in Settings."""
    current_user.notifications_enabled = body.enabled
    db.commit()
    db.refresh(current_user)
    return NotificationSettingsResponse(notifications_enabled=current_user.notifications_enabled)
