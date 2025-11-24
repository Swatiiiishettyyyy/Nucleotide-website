"""
Razorpay payment gateway integration service.
"""
import razorpay
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

# Razorpay configuration
RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    raise ValueError("RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in .env file")

# Initialize Razorpay client
razorpay_client = razorpay.Client(auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET))

# Set API version (optional)
# razorpay_client.set_app_details({"title": "Nucleotide", "version": "1.0.0"})


def create_razorpay_order(amount: float, currency: str = "INR", receipt: Optional[str] = None, notes: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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
        # Convert rupees to paise (multiply by 100)
        amount_in_paise = int(amount * 100)
        
        order_data = {
            "amount": amount_in_paise,
            "currency": currency,
            "payment_capture": 1,  # Auto-capture payment
        }
        
        if receipt:
            order_data["receipt"] = receipt
        
        if notes:
            order_data["notes"] = notes
        
        order = razorpay_client.order.create(data=order_data)
        
        logger.info(f"Razorpay order created: {order.get('id')} for amount {amount}")
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


def verify_payment_signature(razorpay_order_id: str, razorpay_payment_id: str, razorpay_signature: str) -> bool:
    """
    Verify Razorpay payment signature to ensure payment authenticity.
    
    Args:
        razorpay_order_id: Razorpay order ID
        razorpay_payment_id: Razorpay payment ID
        razorpay_signature: Signature received from Razorpay
    
    Returns:
        True if signature is valid, False otherwise
    """
    try:
        # Create message to verify
        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        
        # Generate expected signature
        generated_signature = hmac.new(
            RAZORPAY_KEY_SECRET.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Compare signatures (use constant-time comparison to prevent timing attacks)
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
    """
    Get payment details from Razorpay.
    
    Args:
        payment_id: Razorpay payment ID
    
    Returns:
        Payment details or None if not found
    """
    try:
        payment = razorpay_client.payment.fetch(payment_id)
        return payment
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Payment not found: {payment_id}, error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching payment details: {e}")
        return None


def get_order_details(razorpay_order_id: str) -> Optional[Dict[str, Any]]:
    """
    Get Razorpay order details.
    
    Args:
        razorpay_order_id: Razorpay order ID
    
    Returns:
        Order details or None if not found
    """
    try:
        order = razorpay_client.order.fetch(razorpay_order_id)
        return order
    except razorpay.errors.BadRequestError as e:
        logger.error(f"Order not found: {razorpay_order_id}, error: {e}")
        return None
    except Exception as e:
        logger.error(f"Error fetching order details: {e}")
        return None

