"""
Razorpay payment gateway integration service.

Switch test vs live via RAZORPAY_MODE in .env (test | live).
Uses RAZORPAY_TEST_* or RAZORPAY_LIVE_* credentials from config.settings.
"""
import hashlib
import hmac
import logging
from typing import Any, Dict, Optional

import razorpay

from config import settings

logger = logging.getLogger(__name__)

_razorpay_client: Optional[razorpay.Client] = None


def get_razorpay_mode() -> str:
    return (settings.RAZORPAY_MODE or "test").strip().lower()


def get_razorpay_key_id() -> str:
    return settings.RAZORPAY_KEY_ID or ""


def get_razorpay_key_secret() -> str:
    return settings.RAZORPAY_KEY_SECRET or ""


def get_razorpay_webhook_secret() -> str:
    return settings.RAZORPAY_WEBHOOK_SECRET or ""


def get_razorpay_public_config() -> Dict[str, str]:
    """Public values safe to return to the frontend (never include secrets)."""
    return {
        "razorpay_mode": get_razorpay_mode(),
        "razorpay_key_id": get_razorpay_key_id(),
    }


def _ensure_razorpay_configured() -> None:
    if not get_razorpay_key_id() or not get_razorpay_key_secret():
        raise ValueError(
            f"Razorpay credentials missing for mode '{get_razorpay_mode()}'. "
            "Set RAZORPAY_TEST_* or RAZORPAY_LIVE_* (or legacy RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET) in .env."
        )


def get_razorpay_client() -> razorpay.Client:
    """Return Razorpay client for the active mode (test or live)."""
    global _razorpay_client
    _ensure_razorpay_configured()
    if _razorpay_client is None:
        _razorpay_client = razorpay.Client(
            auth=(get_razorpay_key_id(), get_razorpay_key_secret())
        )
        logger.info("Razorpay client initialized (mode=%s)", get_razorpay_mode())
    return _razorpay_client


def reset_razorpay_client() -> None:
    """Clear cached client (e.g. after tests or config reload)."""
    global _razorpay_client
    _razorpay_client = None


def __getattr__(name: str):
    if name == "RAZORPAY_KEY_ID":
        return get_razorpay_key_id()
    if name == "RAZORPAY_KEY_SECRET":
        return get_razorpay_key_secret()
    if name == "RAZORPAY_WEBHOOK_SECRET":
        return get_razorpay_webhook_secret()
    if name == "razorpay_client":
        return get_razorpay_client()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def create_razorpay_order(
    amount: float,
    currency: str = "INR",
    receipt: Optional[str] = None,
    notes: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Create a Razorpay order.

    Args:
        amount: Amount in rupees (will be converted to paise)
        currency: Currency code (default: INR)
        receipt: Receipt ID for internal tracking
        notes: Additional notes/metadata

    Returns:
        Razorpay order object
    """
    try:
        amount_in_paise = int(amount * 100)

        order_data: Dict[str, Any] = {
            "amount": amount_in_paise,
            "currency": currency,
            "payment_capture": 1,
        }

        if receipt:
            order_data["receipt"] = receipt

        if notes:
            order_data["notes"] = notes

        order = get_razorpay_client().order.create(data=order_data)

        logger.info(
            "Razorpay order created (mode=%s): %s for amount %s",
            get_razorpay_mode(),
            order.get("id"),
            amount,
        )
        return order

    except razorpay.errors.BadRequestError as e:
        logger.error(f"Razorpay bad request error: {e}")
        raise ValueError(f"Invalid request to Razorpay: {str(e)}")
    except razorpay.errors.ServerError as e:
        logger.error(f"Razorpay server error: {e}")
        raise ValueError(f"Razorpay server error: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating Razorpay order: {e}")
        raise ValueError(f"Failed to create Razorpay order: {str(e)}")


def verify_payment_signature(
    razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str
) -> bool:
    """
    Verify Razorpay payment signature to ensure payment authenticity.
    """
    try:
        message = f"{razorpay_order_id}|{razorpay_payment_id}"

        key_secret = get_razorpay_key_secret()
        generated_signature = hmac.new(
            key_secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(generated_signature, razorpay_signature)

        if is_valid:
            logger.info(f"Payment signature verified for order: {razorpay_order_id}")
        else:
            logger.warning(f"Invalid payment signature for order: {razorpay_order_id}")

        return is_valid

    except Exception as e:
        logger.error(f"Error verifying payment signature: {e}")
        return False


def get_payment_details(payment_id: str) -> Optional[Dict[str, Any]]:
    """Get payment details from Razorpay."""
    try:
        payment = get_razorpay_client().payment.fetch(payment_id)
        return payment
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Payment not found: {payment_id}, error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching payment details: {e}")
        return None


def get_order_details(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    """Get Razorpay order details."""
    try:
        order = get_razorpay_client().order.fetch(razorpay_order_id)
        return order
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Order not found: {razorpay_order_id}, error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching order details: {e}")
        return None

def verify_webhook_signature(webhook_body: str, webhook_signature: str) -> bool:
    """Verify Razorpay webhook signature using the webhook secret for the active mode."""
    try:
        webhook_secret = get_razorpay_webhook_secret()
        if not webhook_secret:
            logger.error(
                "Razorpay webhook secret not configured for mode '%s'. "
                "Cannot verify webhook signature.",
                get_razorpay_mode(),
            )
            return False

        generated_signature = hmac.new(
            webhook_secret.encode("utf-8"),
            webhook_body.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        is_valid = hmac.compare_digest(generated_signature, webhook_signature)

        if is_valid:
            logger.info("Webhook signature verified successfully (mode=%s)", get_razorpay_mode())
        else:
            logger.warning("Invalid webhook signature (mode=%s)", get_razorpay_mode())

        return is_valid

    except Exception as e:
        logger.error(f"Error verifying webhook signature: {e}")
        return False
