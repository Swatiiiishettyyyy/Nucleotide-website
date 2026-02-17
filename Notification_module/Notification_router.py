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
)
from .Notification_crud import (
    create_notification,
    list_notifications,
    get_device_tokens_for_user,
    delete_device_tokens_by_value,
    mark_notification_read,
    get_unread_count,
)
from .firebase_service import init_firebase, send_fcm_to_tokens, firebase_initialized

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
    init_firebase()
    if tokens and firebase_initialized:
        data = {"notification_id": str(notification.id), "type": body.type or ""}
        invalid_tokens = send_fcm_to_tokens(
            tokens=tokens,
            title=body.title,
            body=body.message,
            data=data,
        )
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
    """List notifications for the authenticated user. Optional limit and unread_only filter."""
    items = list_notifications(
        db,
        user_id=current_user.id,
        limit=limit,
        unread_only=unread_only,
    )
    return [NotificationItem.model_validate(n) for n in items]


@router.put("/notifications/{notification_id}/read", response_model=NotificationItem)
def put_notification_read(
    notification_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Mark a notification as read. Requires auth; only own notifications can be marked read."""
    updated = mark_notification_read(db, notification_id=notification_id, user_id=current_user.id)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found",
        )
    return NotificationItem.model_validate(updated)


@router.get("/notifications/unread-count", response_model=UnreadCountResponse)
def get_notifications_unread_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return count of unread notifications for the authenticated user."""
    count = get_unread_count(db, user_id=current_user.id)
    return UnreadCountResponse(unread_count=count)
