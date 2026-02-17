"""
Firebase Admin SDK initialization and FCM send.
Initializes once at startup (or on first use); sends push notifications via FCM.
"""
import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

firebase_initialized = False


def init_firebase() -> bool:
    """
    Initialize Firebase Admin from service account JSON.
    Uses FIREBASE_SERVICE_ACCOUNT_PATH from config, or fallback to project-root Notifications.json.
    Returns True if initialized, False otherwise (FCM send will be skipped).
    """
    global firebase_initialized
    if firebase_initialized:
        return True

    try:
        import firebase_admin
        from firebase_admin import credentials
    except ImportError:
        logger.warning("firebase-admin not installed; FCM push will be skipped.")
        return False

    if firebase_admin._apps:
        firebase_initialized = True
        return True

    from config import settings
    path = (settings.FIREBASE_SERVICE_ACCOUNT_PATH or "").strip()
    if not path:
        # Prefer Notification_module/Notifications.json, then project root
        this_dir = Path(__file__).resolve().parent
        root = this_dir.parent
        if os.path.isfile(this_dir / "Notifications.json"):
            path = str(this_dir / "Notifications.json")
        else:
            path = str(root / "Notifications.json")
    if not os.path.isfile(path):
        logger.warning("Firebase service account file not found at %s; FCM push will be skipped.", path)
        return False

    try:
        cred = credentials.Certificate(path)
        firebase_admin.initialize_app(cred)
        firebase_initialized = True
        logger.info("Firebase Admin initialized for FCM (push notifications enabled).")
        return True
    except Exception as e:
        logger.warning("Firebase Admin init failed: %s; FCM push will be skipped.", e)
        return False


def _is_invalid_or_unregistered_token(exc: Optional[Exception]) -> bool:
    """Return True if the FCM exception indicates token should be removed (unregistered/invalid)."""
    if exc is None:
        return False
    name = type(exc).__name__
    msg = (getattr(exc, "message", None) or str(exc)).lower()
    if "UnregisteredError" in name or "unregistered" in msg:
        return True
    if "invalid" in msg or "not a valid fcm registration" in msg or "requested entity was not found" in msg:
        return True
    return False


def send_fcm_to_tokens(
    tokens: list[str],
    title: str,
    body: str,
    data: Optional[dict] = None,
) -> list[str]:
    """
    Send FCM notification to the given device tokens.
    Does not raise; logs errors so API responses are not tied to FCM failures.
    Returns list of token strings that are invalid/unregistered and should be removed from DB.
    """
    invalid_tokens: list[str] = []
    if not tokens:
        return invalid_tokens
    init_firebase()
    if not firebase_initialized:
        return invalid_tokens

    try:
        import firebase_admin
        from firebase_admin import messaging
    except ImportError:
        logger.warning("firebase-admin not available; skipping FCM send.")
        return invalid_tokens

    if not firebase_admin._apps:
        logger.warning("Firebase not initialized; skipping FCM send.")
        return invalid_tokens

    # data must be string key -> string value for FCM
    data_dict: Optional[dict[str, str]] = None
    if data:
        data_dict = {k: str(v) for k, v in data.items()}

    message = messaging.MulticastMessage(
        notification=messaging.Notification(title=title, body=body),
        data=data_dict,
        tokens=tokens,
    )
    try:
        batch = messaging.send_each_for_multicast(message)
        if batch.failure_count > 0:
            for i, send_response in enumerate(batch.responses):
                if not send_response.success:
                    exc = getattr(send_response, "exception", None)
                    logger.warning(
                        "FCM send failed for token index %s: %s",
                        i,
                        getattr(exc, "message", exc),
                    )
                    if i < len(tokens) and _is_invalid_or_unregistered_token(exc):
                        invalid_tokens.append(tokens[i])
        logger.info("FCM sent to %s/%s tokens.", batch.success_count, len(tokens))
    except Exception as e:
        logger.warning("FCM send failed: %s", e)
    return invalid_tokens
