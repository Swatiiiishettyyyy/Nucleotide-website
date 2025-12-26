"""
Order CRUD operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any
import secrets
from Login_module.Utils.datetime_utils import now_ist, to_ist_isoformat
from .Order_model import (
    Order, OrderItem, OrderSnapshot, OrderStatusHistory,
    Payment, PaymentTransition, WebhookLog,
    OrderStatus, PaymentStatus, PaymentMethod
)
from Cart_module.Cart_model import CartItem
from Cart_module.coupon_service import get_applied_coupon, validate_and_calculate_discount
from Product_module.Product_model import Product
from Member_module.Member_model import Member
from Address_module.Address_model import Address
import logging

logger = logging.getLogger(__name__)


def sync_order_item_statuses_with_order_status(
    db: Session,
    order: Order,
    order_status: OrderStatus,
    update_timestamp: bool = True
) -> None:
    """
    Sync all order item statuses based on the order-level status.
    Logic:
    - If order status is CONFIRMED → item status = CONFIRMED
    - If order status is PAYMENT_FAILED → item status = PAYMENT_FAILED
    - For all other order statuses → item status = PENDING
    
    Args:
        db: Database session
        order: Order object with items relationship loaded
        order_status: The order-level status
        update_timestamp: Whether to update status_updated_at timestamp
    """
    # Determine item status based on order status
    if order_status == OrderStatus.CONFIRMED:
        item_status = OrderStatus.CONFIRMED
    elif order_status == OrderStatus.PAYMENT_FAILED:
        item_status = OrderStatus.PAYMENT_FAILED
    else:
        # For all other statuses (PENDING_PAYMENT, PROCESSING, SCHEDULED, etc.)
        item_status = OrderStatus.PENDING
    
    # Update all order items
    for item in order.items:
        item.order_status = item_status
        if update_timestamp:
            item.status_updated_at = now_ist()


def extract_payment_method_from_razorpay_payload(entity: Dict[str, Any]) -> Tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Extract payment method details from Razorpay webhook payload.
    
    Args:
        entity: The payment entity from Razorpay webhook payload
        
    Returns:
        tuple: (payment_method_details, payment_method_metadata)
        - payment_method_details: e.g., "upi", "netbanking", "wallet", "card", "emi", etc.
        - payment_method_metadata: Additional details like VPA, bank name, wallet name, card details, etc.
    """
    if not entity:
        return None, None
    
    # Extract payment method (e.g., "upi", "netbanking", "wallet", "card", "emi")
    payment_method = entity.get("method")
    
    # Build metadata dictionary with relevant payment method details
    metadata = {}
    
    if payment_method:
        # UPI payment details
        if payment_method == "upi":
            metadata["vpa"] = entity.get("vpa")  # Virtual Payment Address
            metadata["upi_provider"] = entity.get("acquirer_data", {}).get("upi", {}).get("payer_account_type") if entity.get("acquirer_data") else None
        
        # Netbanking payment details
        elif payment_method == "netbanking":
            metadata["bank"] = entity.get("bank")
            metadata["bank_transaction_id"] = entity.get("acquirer_data", {}).get("bank_transaction_id") if entity.get("acquirer_data") else None
        
        # Wallet payment details
        elif payment_method == "wallet":
            metadata["wallet"] = entity.get("wallet")
            metadata["wallet_provider"] = entity.get("wallet")  # e.g., "paytm", "mobikwik", "freecharge"
        
        # Card payment details
        elif payment_method == "card":
            card_data = entity.get("card", {})
            if card_data:
                metadata["card_id"] = card_data.get("id")
                metadata["card_network"] = card_data.get("network")  # e.g., "Visa", "MasterCard", "RuPay"
                metadata["card_type"] = card_data.get("type")  # e.g., "credit", "debit"
                metadata["card_last4"] = card_data.get("last4")
                metadata["card_issuer"] = card_data.get("issuer")
        
        # EMI payment details
        elif payment_method == "emi":
            metadata["emi"] = entity.get("emi", {})
            metadata["bank"] = entity.get("bank")
        
        # Add other common fields
        if entity.get("acquirer_data"):
            metadata["acquirer"] = entity.get("acquirer_data", {}).get("acquirer")
            metadata["auth_code"] = entity.get("acquirer_data", {}).get("auth_code")
    
    return payment_method, metadata if metadata else None


def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = now_ist().strftime("%Y%m%d%H%M%S")
    random_part = secrets.token_hex(4).upper()
    return f"ORD{timestamp}{random_part}"


def find_existing_order_for_retry(
    db: Session,
    user_id: int,
    cart_item_ids: List[int]
) -> Optional[Order]:
    """
    Find existing order for retry payment scenario.
    Looks for orders with PAYMENT_FAILED or PENDING_PAYMENT status
    that have the same cart items (same products, members, addresses).
    
    Returns the most recent matching order, or None if not found.
    """
    # Get cart items to match against
    cart_items = (
        db.query(CartItem)
        .filter(
            CartItem.id.in_(cart_item_ids),
            CartItem.user_id == user_id,
            CartItem.is_deleted == False
        )
        .all()
    )
    
    if not cart_items:
        return None
    
    # Build set of cart item signatures for matching
    # Signature: (product_id, member_id, address_id, quantity)
    cart_signatures = {
        (item.product_id, item.member_id, item.address_id, item.quantity)
        for item in cart_items
    }
    
    # Find orders for this user with retry-able statuses
    # Order by created_at DESC to get most recent first
    candidate_orders = (
        db.query(Order)
        .filter(
            Order.user_id == user_id,
            Order.order_status.in_([OrderStatus.PAYMENT_FAILED, OrderStatus.PENDING_PAYMENT])
        )
        .order_by(Order.created_at.desc())
        .all()
    )
    
    # Check each candidate order to see if it matches current cart items
    for order in candidate_orders:
        # Get order items for this order
        order_items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .all()
        )
        
        if len(order_items) != len(cart_items):
            # Different number of items, can't match
            continue
        
        # Build set of order item signatures
        order_signatures = {
            (item.product_id, item.member_id, item.address_id, item.quantity)
            for item in order_items
        }
        
        # Check if signatures match exactly
        if cart_signatures == order_signatures:
            # Found matching order - return it
            logger.info(f"Found existing order {order.order_number} for retry payment")
            return order
    
    # No matching order found
    return None


def create_order_from_cart(
    db: Session,
    user_id: int,
    address_id: Optional[int],
    cart_item_ids: List[int],
    razorpay_order_id: Optional[str] = None,
    placed_by_member_id: Optional[int] = None
) -> Order:
    """
    Create order from cart items.
    Creates snapshots of products, members, and addresses at time of order.
    """
    # Validate all cart items belong to user (exclude deleted items)
    cart_items = (
        db.query(CartItem)
        .filter(
            CartItem.id.in_(cart_item_ids),
            CartItem.user_id == user_id,
            CartItem.is_deleted == False  # Exclude deleted items
        )
        .all()
    )
    
    if len(cart_items) != len(cart_item_ids):
        raise ValueError("One or more cart items not found or do not belong to you")
    
    if not cart_items:
        raise ValueError("No cart items selected")
    
    # Get unique addresses from cart items
    unique_cart_address_ids = {item.address_id for item in cart_items if item.address_id}
    
    if not unique_cart_address_ids:
        raise ValueError("No addresses associated with selected cart items")
    
    # Determine primary address_id
    primary_address_id = None
    
    if address_id:
        # If address_id is provided, validate it
        if address_id not in unique_cart_address_ids:
            raise ValueError(
                f"Address ID {address_id} is not associated with any of the selected cart items. "
                f"Cart items use address IDs: {sorted(unique_cart_address_ids)}"
            )
        primary_address_id = address_id
    else:
        # If address_id is not provided, use the first address from cart items
        primary_address_id = next(iter(sorted(unique_cart_address_ids)))
        logger.info(
            f"Address ID not provided for order creation. Using first address from cart items: {primary_address_id}. "
            f"All addresses in cart: {sorted(unique_cart_address_ids)}"
        )
    
    # Verify the address belongs to the user and exists
    address = db.query(Address).filter(
        Address.id == primary_address_id,
        Address.user_id == user_id,
        Address.is_deleted == False
    ).first()
    
    if not address:
        raise ValueError(f"Address ID {primary_address_id} not found or does not belong to you")
    
    # Log if multiple addresses are involved (for tracking purposes)
    if len(unique_cart_address_ids) > 1:
        logger.info(
            "Order creation for user %s contains multiple addresses (%s); using %s as primary",
            user_id,
            sorted(unique_cart_address_ids),
            primary_address_id
        )
    else:
        logger.info(
            "Order creation for user %s uses single address %s for all items",
            user_id,
            primary_address_id
        )
    
    # Calculate totals
    subtotal = 0.0
    delivery_charge = 0.0  # Free delivery
    discount = 0.0
    coupon_discount = 0.0
    coupon_code = None
    
    # Group cart items by group_id to calculate totals correctly
    grouped_items = {}
    for item in cart_items:
        group_key = item.group_id or f"single_{item.id}"
        if group_key not in grouped_items:
            grouped_items[group_key] = []
        grouped_items[group_key].append(item)
    
    # Calculate subtotal and discount (price is per product, not per member)
    # For couple/family products, there are multiple cart item rows but discount applies once per product
    # This matches the cart calculation logic exactly
    for group_key, items in grouped_items.items():
        # Skip if group is empty (should not happen, but safety check)
        if not items:
            continue
            
        item = items[0]  # Use first item as representative
        product = item.product
        
        # Skip if product is deleted or missing
        if not product:
            continue
            
        # Only count once per product group
        subtotal += item.quantity * product.SpecialPrice
        
        # Calculate discount once per product group (same logic as cart view)
        discount_per_item = product.Price - product.SpecialPrice
        discount += discount_per_item * item.quantity
    
    # Get applied coupon from cart and re-validate to ensure accuracy
    # This matches the cart view logic - recalculate discount based on current subtotal
    applied_coupon = get_applied_coupon(db, user_id)
    if applied_coupon:
        # Re-validate and recalculate discount (cart total might have changed)
        coupon, calculated_discount, error_message = validate_and_calculate_discount(
            db, applied_coupon.coupon_code, user_id, subtotal
        )
        
        if coupon and not error_message:
            # Coupon is valid - use the recalculated discount
            coupon_discount = calculated_discount
            coupon_code = applied_coupon.coupon_code
            logger.info(f"Order will include coupon '{coupon_code}' with discount of ₹{coupon_discount} (recalculated from subtotal ₹{subtotal})")
        else:
            # Validation failed - log warning but use stored discount as fallback
            logger.warning(f"Coupon validation warning for '{applied_coupon.coupon_code}' during order creation: {error_message}. Using stored discount.")
            coupon_discount = applied_coupon.discount_amount
            coupon_code = applied_coupon.coupon_code
    
    # Calculate total amount
    # Note: subtotal already uses SpecialPrice (product discount is already applied)
    # So we only subtract coupon_discount, not discount
    # This matches the corrected cart calculation: grand_total = subtotal_amount + delivery_charge - coupon_amount
    total_amount = subtotal + delivery_charge - coupon_discount
    # Ensure total is not negative
    total_amount = max(0.0, total_amount)
    
    # Create order (without payment fields - payment is in separate table)
    order = Order(
        order_number=generate_order_number(),
        user_id=user_id,
        placed_by_member_id=placed_by_member_id,  # Member profile that was active when order was placed
        address_id=primary_address_id,
        subtotal=subtotal,
        delivery_charge=delivery_charge,
        discount=discount,
        coupon_code=coupon_code,
        coupon_discount=coupon_discount,
        total_amount=total_amount,
        payment_status=PaymentStatus.PENDING,  # Order created, payment not started (denormalized for quick queries)
        order_status=OrderStatus.PENDING_PAYMENT  # Order created, waiting for payment
    )
    db.add(order)
    db.flush()  # Get order.id
    
    # Create payment record (always create, even if razorpay_order_id is None initially)
    # This ensures every order has a payment record for consistency
    # Note: razorpay_order_id is NOT NULL in the database, so we use empty string as placeholder
    payment = Payment(
        order_id=order.id,
        payment_method=PaymentMethod.RAZORPAY,
        payment_status=PaymentStatus.PENDING,
        razorpay_order_id=razorpay_order_id or "",  # Use empty string if None (will be updated when Razorpay order is created)
        amount=total_amount,
        currency="INR",
        notes="Initial payment record created with order" + (f" (Razorpay order ID: {razorpay_order_id})" if razorpay_order_id else " (Razorpay order ID pending)")
    )
    db.add(payment)
    db.flush()  # Get payment.id
    
    # Create initial payment transition
    payment_transition = PaymentTransition(
        payment_id=payment.id,
        from_status=None,  # Initial status
        to_status=PaymentStatus.PENDING,
        transition_reason="Order created, payment not started",
        triggered_by="system"
    )
    db.add(payment_transition)
    
    # If razorpay_order_id was provided later, update the payment record
    if razorpay_order_id and payment.razorpay_order_id != razorpay_order_id:
        payment.razorpay_order_id = razorpay_order_id
        payment.notes = f"Initial payment record created with order (Razorpay order ID: {razorpay_order_id})"
        db.flush()
    
    # Create order items and snapshots
    for cart_item in cart_items:
        product = cart_item.product
        member = cart_item.member
        address_obj = cart_item.address
        
        # Validate required relationships exist
        if not product:
            raise ValueError(f"Product not found for cart item {cart_item.id}")
        if not member:
            raise ValueError(f"Member not found for cart item {cart_item.id}")
        if not address_obj:
            raise ValueError(f"Address not found for cart item {cart_item.id}")
        
        # Create snapshot
        snapshot = OrderSnapshot(
            order_id=order.id,
            user_id=user_id,
            product_data={
                "ProductId": product.ProductId,
                "Name": product.Name,
                "Price": product.Price,
                "SpecialPrice": product.SpecialPrice,
                "plan_type": product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type),
                "category": {
                    "id": product.category.id if product.category else None,
                    "name": product.category.name if product.category else None,
                },
                "ShortDescription": product.ShortDescription,
                "Images": product.Images
            },
            member_data={
                "id": member.id,
                "name": member.name,
                "relation": member.relation.value if hasattr(member.relation, 'value') else str(member.relation),
                "age": member.age,
                "gender": member.gender,
                "dob": to_ist_isoformat(member.dob) if member.dob else None,
                "mobile": member.mobile
            },
            address_data={
                "id": address_obj.id,
                "address_label": address_obj.address_label,
                "street_address": address_obj.street_address,
                "landmark": address_obj.landmark,
                "locality": address_obj.locality,
                "city": address_obj.city,
                "state": address_obj.state,
                "postal_code": address_obj.postal_code,
                "country": address_obj.country
            },
            cart_item_data={
                "group_id": cart_item.group_id  # Store group_id to distinguish different packs of same product
            }
        )
        db.add(snapshot)
        db.flush()
        
        # Create order item with initial status
        order_item = OrderItem(
            order_id=order.id,
            user_id=user_id,
            product_id=product.ProductId,
            member_id=member.id,
            address_id=cart_item.address_id,
            snapshot_id=snapshot.id,
            quantity=cart_item.quantity,
            unit_price=product.SpecialPrice,  # Store SpecialPrice as unit_price
            order_status=OrderStatus.PENDING_PAYMENT  # Initialize with pending payment status
        )
        db.add(order_item)
        db.flush()  # Get order_item.id for status history
        
        # Create initial status history for this order item
        item_status_history = OrderStatusHistory(
            order_id=order.id,
            order_item_id=order_item.id,
            status=OrderStatus.PENDING_PAYMENT,
            previous_status=None,
            notes=f"Order item created for member {member.name} at address {address_obj.address_label or address_obj.id}. Waiting for payment.",
            changed_by=str(user_id)
        )
        db.add(item_status_history)
    
        # Create initial status history
    status_history = OrderStatusHistory(
        order_id=order.id,
        status=OrderStatus.PENDING_PAYMENT,
        previous_status=None,
        notes="Order created from cart. Waiting for payment.",
        changed_by=str(user_id)
    )
    db.add(status_history)
    
    db.commit()
    db.refresh(order)
    
    return order


def verify_payment_frontend(
    db: Session,
    order_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> Order:
    """
    Verify Razorpay payment from frontend (verify-payment endpoint).
    ONLY sets payment_status = SUCCESS (temporary).
    DOES NOT confirm order or clear cart.
    Webhook will finalize confirmation later.
    """
    # Load order with items
    from sqlalchemy.orm import joinedload
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise ValueError("Order not found")
    
    # Refresh to get latest state (prevent race conditions)
    db.refresh(order)
    
    # If webhook already confirmed, do nothing (idempotent)
    if order.order_status == OrderStatus.CONFIRMED:
        logger.info(f"Order {order.order_number} already confirmed by webhook. Frontend verification skipped.")
        return order
    
    # If already verified by frontend, return success (idempotent)
    if order.payment_status == PaymentStatus.PROCESSING:
        logger.info(f"Payment already verified for order {order.order_number}. Returning success.")
        return order
    
    # If payment already failed, raise error
    if order.payment_status == PaymentStatus.FAILED:
        raise ValueError("Payment for this order has already failed. Please create a new order to retry payment.")
    
    # Get the latest payment for this order
    # First try to find payment with matching razorpay_order_id
    payment = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.razorpay_order_id == razorpay_order_id
    ).order_by(Payment.created_at.desc()).first()
    
    # If not found, get the latest payment for this order (fallback)
    if not payment:
        payment = db.query(Payment).filter(
            Payment.order_id == order.id
        ).order_by(Payment.created_at.desc()).first()
        
        if not payment:
            # Create payment record if it doesn't exist (shouldn't happen, but handle gracefully)
            logger.warning(f"Payment record not found for order {order.order_number}. Creating new payment record.")
            payment = Payment(
                order_id=order.id,
                payment_method=PaymentMethod.RAZORPAY,
                payment_status=PaymentStatus.PENDING,
                razorpay_order_id=razorpay_order_id,
                amount=order.total_amount,
                currency="INR",
                notes=f"Payment record created during verification (Razorpay order ID: {razorpay_order_id})"
            )
            db.add(payment)
            db.flush()
        else:
            # Update existing payment with razorpay_order_id if it's missing
            if not payment.razorpay_order_id or payment.razorpay_order_id != razorpay_order_id:
                payment.razorpay_order_id = razorpay_order_id
                db.flush()
    
    # Validate razorpay_order_id matches
    if payment.razorpay_order_id != razorpay_order_id:
        raise ValueError(f"Razorpay order ID mismatch. Expected {payment.razorpay_order_id}, got {razorpay_order_id}")
    
    # Verify signature
    from .razorpay_service import verify_payment_signature
    is_valid = verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    
    if not is_valid:
        # Update payment status to failed
        previous_payment_status = payment.payment_status
        payment.payment_status = PaymentStatus.FAILED
        payment.razorpay_payment_id = razorpay_payment_id
        payment.razorpay_signature = razorpay_signature
        payment.updated_at = now_ist()
        
        # Create payment transition
        payment_transition = PaymentTransition(
            payment_id=payment.id,
            from_status=previous_payment_status,
            to_status=PaymentStatus.FAILED,
            transition_reason="Payment verification failed. Invalid payment signature.",
            triggered_by="system"
        )
        db.add(payment_transition)
        
        # Update order status
        order.payment_status = PaymentStatus.FAILED  # Denormalized
        previous_order_status = order.order_status
        order.order_status = OrderStatus.PAYMENT_FAILED
        order.status_updated_at = now_ist()
        
        # Update item statuses - sync with order status
        item_previous_statuses = {}
        for item in order.items:
            item_previous_statuses[item.id] = item.order_status
        
        # Sync all order item statuses with order status
        sync_order_item_statuses_with_order_status(db, order, OrderStatus.PAYMENT_FAILED, update_timestamp=True)
        
        # Create status history
        status_history = OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.PAYMENT_FAILED,
            previous_status=previous_order_status,
            notes="Payment verification failed. Invalid payment signature. Payment status set to FAILED. Order status set to PAYMENT_FAILED.",
            changed_by="system"
        )
        db.add(status_history)
        
        # Create status history for each order item
        for item in order.items:
            item_previous_status = item_previous_statuses.get(item.id, OrderStatus.PENDING_PAYMENT)
            item_status_history = OrderStatusHistory(
                order_id=order.id,
                order_item_id=item.id,
                status=OrderStatus.PAYMENT_FAILED,
                previous_status=item_previous_status,
                notes="Payment verification failed. Order item payment failed.",
                changed_by="system"
            )
            db.add(item_status_history)
        
        db.commit()
        logger.warning(f"Payment verification failed for order {order.order_number} (ID: {order.id}). Payment status set to FAILED.")
        raise ValueError("Payment verification failed. Please check your payment details and try again. If the problem persists, please contact support.")
    
    # Payment signature valid - update to PROCESSING (frontend verified, waiting for webhook)
    previous_payment_status = payment.payment_status
    payment.razorpay_payment_id = razorpay_payment_id
    payment.razorpay_signature = razorpay_signature
    payment.payment_status = PaymentStatus.PROCESSING
    payment.updated_at = now_ist()
    
    # Create payment transition
    payment_transition = PaymentTransition(
        payment_id=payment.id,
        from_status=previous_payment_status,
        to_status=PaymentStatus.PROCESSING,
        transition_reason="Frontend payment verification successful. Waiting for webhook confirmation.",
        triggered_by="system"
    )
    db.add(payment_transition)
    
    # Update order (denormalized payment_status)
    order.payment_status = PaymentStatus.PROCESSING
    order.order_status = OrderStatus.PROCESSING  # Frontend verified, waiting for webhook
    order.status_updated_at = now_ist()
    
    # Sync all order item statuses with order status
    sync_order_item_statuses_with_order_status(db, order, OrderStatus.PROCESSING, update_timestamp=True)
    
    # DO NOT clear cart - webhook will handle this
    
    db.commit()
    db.refresh(order)
    
    logger.info(f"Frontend payment verification successful for order {order.order_number}. Payment status: PROCESSING. Order status: PROCESSING. Waiting for webhook confirmation.")
    
    return order


def confirm_order_from_webhook(
    db: Session,
    order_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    webhook_log_id: Optional[int] = None,
    payment_method_details: Optional[str] = None,
    payment_method_metadata: Optional[dict] = None
) -> Order:
    """
    Confirm order from webhook (payment.captured event).
    This is the ONLY place where order confirmation happens.
    Idempotent - can be called multiple times safely.
    """
    # Load order with items using row-level locking to prevent race conditions
    from sqlalchemy import select
    from sqlalchemy.orm import joinedload
    from sqlalchemy import func as sql_func
    
    # Use SELECT FOR UPDATE to lock the row
    # Note: .unique() is required when using joinedload on collections to deduplicate parent rows
    order_stmt = select(Order).options(joinedload(Order.items)).where(Order.id == order_id).with_for_update()
    result = db.execute(order_stmt)
    order = result.scalars().unique().first()
    
    if not order:
        raise ValueError(f"Order {order_id} not found")
    
    # Get the payment record for this order
    # First try to find payment with matching razorpay_order_id
    payment = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.razorpay_order_id == razorpay_order_id
    ).order_by(Payment.created_at.desc()).first()
    
    # If not found, get the latest payment for this order (fallback)
    if not payment:
        payment = db.query(Payment).filter(
            Payment.order_id == order.id
        ).order_by(Payment.created_at.desc()).first()
        
        if not payment:
            # Create payment record if it doesn't exist (shouldn't happen, but handle gracefully)
            logger.warning(f"Payment record not found for order {order.order_number}. Creating new payment record.")
            payment = Payment(
                order_id=order.id,
                payment_method=PaymentMethod.RAZORPAY,
                payment_status=PaymentStatus.PENDING,
                razorpay_order_id=razorpay_order_id,
                amount=order.total_amount,
                currency="INR",
                notes=f"Payment record created during webhook confirmation (Razorpay order ID: {razorpay_order_id})"
            )
            db.add(payment)
            db.flush()
        else:
            # Update existing payment with razorpay_order_id if it's missing or different
            if not payment.razorpay_order_id or payment.razorpay_order_id != razorpay_order_id:
                payment.razorpay_order_id = razorpay_order_id
                db.flush()
    
    # Validate razorpay_order_id matches (after potential update)
    if payment.razorpay_order_id != razorpay_order_id:
        raise ValueError(f"Razorpay order ID mismatch. Expected {payment.razorpay_order_id}, got {razorpay_order_id}")
    
    # IDEMPOTENCY CHECK: If already confirmed, return early (idempotent)
    # This protects against late failure events and ensures idempotency
    if order.order_status == OrderStatus.CONFIRMED:
        logger.info(f"Order {order.order_number} already confirmed. Webhook event ignored (idempotent).")
        return order
    
    # Update payment status atomically
    previous_payment_status = payment.payment_status
    previous_order_status = order.order_status
    
    # Update payment record
    payment.razorpay_payment_id = razorpay_payment_id
    payment.payment_status = PaymentStatus.COMPLETED
    payment.payment_date = now_ist()
    payment.updated_at = now_ist()
    
    # Update payment method details if provided
    if payment_method_details:
        payment.payment_method_details = payment_method_details
    if payment_method_metadata:
        payment.payment_method_metadata = payment_method_metadata
    
    # Create payment transition
    payment_transition = PaymentTransition(
        payment_id=payment.id,
        from_status=previous_payment_status,
        to_status=PaymentStatus.COMPLETED,
        transition_reason="Payment confirmed by webhook (payment.captured event)",
        triggered_by="system",
        webhook_log_id=webhook_log_id
    )
    db.add(payment_transition)
    
    # Update order (denormalized payment_status)
    order.payment_status = PaymentStatus.COMPLETED
    order.order_status = OrderStatus.CONFIRMED
    order.status_updated_at = now_ist()
    
    # Update all order items - sync with order status
    item_previous_statuses = {}
    for item in order.items:
        item_previous_statuses[item.id] = item.order_status
    
    # Sync all order item statuses with order status
    sync_order_item_statuses_with_order_status(db, order, OrderStatus.CONFIRMED, update_timestamp=True)
    
    # Create status history for order confirmation
    status_history = OrderStatusHistory(
        order_id=order.id,
        status=OrderStatus.CONFIRMED,
        previous_status=previous_order_status,
        notes=f"Order confirmed by webhook (payment.captured). Payment verified. Previous status: {previous_order_status.value}",
        changed_by="system"
    )
    db.add(status_history)
    
    # Create status history for each order item
    for item in order.items:
        previous_item_status = item_previous_statuses.get(item.id, OrderStatus.PENDING_PAYMENT)
        item_status_history = OrderStatusHistory(
            order_id=order.id,
            order_item_id=item.id,
            status=OrderStatus.CONFIRMED,
            previous_status=previous_item_status,
            notes="Order item confirmed by webhook. Payment verified.",
            changed_by="system"
        )
        db.add(item_status_history)
    
    db.flush()
    
    # Clear cart items (idempotent - clear all cart items for user to ensure nothing is missed)
    try:
        from Cart_module.Cart_model import CartItem, Cart
        
        # Get user's active cart
        cart = db.query(Cart).filter(
            Cart.user_id == order.user_id,
            Cart.is_active == True
        ).first()
        
        # Get cart items first to check if user has any
        cart_items = db.query(CartItem).filter(
            CartItem.user_id == order.user_id,
            CartItem.is_deleted == False
        ).all()
        
        # If cart doesn't exist but user has items, create cart
        if not cart and cart_items:
            # Get all active carts for this user
            active_carts = db.query(Cart).filter(
                Cart.user_id == order.user_id,
                Cart.is_active == True
            ).all()
            
            if len(active_carts) > 1:
                # Multiple active carts - deactivate all except the first
                for c in active_carts[1:]:
                    c.is_active = False
                cart = active_carts[0]
            elif len(active_carts) == 1:
                cart = active_carts[0]
            else:
                # No active cart exists - create new one
                cart = Cart(
                    user_id=order.user_id,
                    is_active=True
                )
                db.add(cart)
                db.flush()
                db.refresh(cart)
            
            # Update items to use the new cart_id
            for item in cart_items:
                if not item.cart_id:
                    item.cart_id = cart.id
        
        # Soft delete all cart items for the user's cart to ensure nothing is missed
        # This is safer than matching specific items which might miss items added after order creation
        if cart and cart_items:
            # Re-query with cart_id to ensure we get all items
            cart_items = db.query(CartItem).filter(
                CartItem.cart_id == cart.id,
                CartItem.is_deleted == False
            ).all()
        
        deleted_count = len(cart_items)
        for item in cart_items:
            item.is_deleted = True
        
        # Update cart's last_activity_at
        if cart:
            cart.last_activity_at = now_ist()
        
        # Remove applied coupon after successful payment
        from Cart_module.coupon_service import remove_coupon_from_cart
        remove_coupon_from_cart(db, order.user_id)
        
        logger.info(f"Cart cleared for user {order.user_id} after order {order.order_number} confirmation. {deleted_count} item(s) removed.")
    except Exception as e:
        # Log error but don't fail order confirmation if cart clearing fails
        # However, this is a critical operation, so log as error for monitoring
        logger.error(
            f"CRITICAL: Error clearing cart for order {order.order_number} (user {order.user_id}): {str(e)}. "
            f"Order confirmed but cart may still contain items. Manual intervention may be required.",
            exc_info=True
        )
    
    # Track genetic test participants after order confirmation
    try:
        from GeneticTest_module.GeneticTest_crud import create_or_update_participant
        
        for order_item in order.items:
            if order_item.member_id and order_item.product_id:
                member = db.query(Member).filter(
                    Member.id == order_item.member_id,
                    Member.is_deleted == False
                ).first()
                if not member:
                    logger.warning(f"Member {order_item.member_id} not found or deleted for participant tracking")
                    continue
                
                product = db.query(Product).filter(
                    Product.ProductId == order_item.product_id,
                    Product.is_deleted == False
                ).first()
                if not product:
                    logger.warning(f"Product {order_item.product_id} not found or deleted for participant tracking")
                    continue
                
                plan_type = None
                if product.plan_type:
                    plan_type = product.plan_type.value if hasattr(product.plan_type, 'value') else str(product.plan_type)
                
                create_or_update_participant(
                    db=db,
                    user_id=order.user_id,
                    member_id=order_item.member_id,
                    mobile=member.mobile,
                    name=member.name,
                    plan_type=plan_type,
                    product_id=order_item.product_id,
                    category_id=product.category_id,
                    order_id=order.id,
                    has_taken_genetic_test=True
                )
                logger.info(f"Tracked genetic test participant: member {order_item.member_id}, plan_type: {plan_type}")
    except Exception as e:
        # Log error but don't fail order confirmation
        # However, this is a critical operation, so log as error for monitoring
        logger.error(
            f"CRITICAL: Error tracking genetic test participants for order {order.order_number} (ID: {order.id}): {str(e)}. "
            f"Order confirmed but genetic test flag may not be set. Manual intervention may be required.",
            exc_info=True
        )
    
    db.commit()
    db.refresh(order)
    
    logger.info(f"Order {order.order_number} confirmed by webhook. Payment status: COMPLETED, Order status: CONFIRMED")
    
    return order


# Legacy function - kept for backward compatibility, but deprecated
def verify_and_complete_payment(
    db: Session,
    order_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> Order:
    """
    DEPRECATED: Legacy function. Use verify_payment_frontend() instead.
    This function is kept for backward compatibility but should not be used for new code.
    """
    logger.warning("verify_and_complete_payment is deprecated. Use verify_payment_frontend() instead.")
    return verify_payment_frontend(db, order_id, razorpay_order_id, razorpay_payment_id, razorpay_signature)


def mark_payment_failed_or_cancelled(
    db: Session,
    order_id: int,
    payment_status: PaymentStatus,
    reason: str = None,
    payment_method_details: Optional[str] = None,
    payment_method_metadata: Optional[Dict[str, Any]] = None
) -> Order:
    """
    Mark payment as failed.
    Called from webhooks when payment fails.
    
    Args:
        db: Database session
        order_id: Order ID
        payment_status: PaymentStatus.FAILED
        reason: Optional reason for failure
    
    Returns:
        Updated order
    """
    if payment_status != PaymentStatus.FAILED:
        raise ValueError(f"Invalid payment status. Must be FAILED, got {payment_status}")
    
    # Load order with items to ensure all items are in session for updates
    from sqlalchemy.orm import joinedload
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise ValueError("Order not found")
    
    # Don't update if payment is already completed (protected state)
    if order.payment_status == PaymentStatus.COMPLETED:
        logger.warning(f"Cannot mark payment as {payment_status.value} for order {order.order_number} - payment already completed")
        return order
    
    # Get the latest payment for this order
    payment = db.query(Payment).filter(
        Payment.order_id == order.id
    ).order_by(Payment.created_at.desc()).first()
    
    if not payment:
        logger.warning(f"Payment record not found for order {order.order_number}. Creating new payment record.")
        # Create a payment record if it doesn't exist (shouldn't happen, but handle gracefully)
        payment = Payment(
            order_id=order.id,
            payment_method=PaymentMethod.RAZORPAY,
            payment_status=PaymentStatus.FAILED,
            razorpay_order_id="",  # Unknown
            amount=order.total_amount,
            currency="INR",
            notes=f"Payment record created during failure marking. Reason: {reason or 'Unknown'}"
        )
        db.add(payment)
        db.flush()
    
    # Update payment status
    previous_payment_status = payment.payment_status
    payment.payment_status = PaymentStatus.FAILED
    payment.updated_at = now_ist()
    
    # Update payment method details if provided
    if payment_method_details:
        payment.payment_method_details = payment_method_details
    if payment_method_metadata:
        payment.payment_method_metadata = payment_method_metadata
    
    if reason:
        payment.notes = (payment.notes or "") + f" | Failed: {reason}"
    
    # Create payment transition
    payment_transition = PaymentTransition(
        payment_id=payment.id,
        from_status=previous_payment_status,
        to_status=PaymentStatus.FAILED,
        transition_reason=reason or "Payment failed or cancelled",
        triggered_by="system"
    )
    db.add(payment_transition)
    
    # Update order (denormalized payment_status)
    order.payment_status = PaymentStatus.FAILED
    order.status_updated_at = now_ist()
    
    # Set order_status to PAYMENT_FAILED
    previous_order_status = order.order_status
    order.order_status = OrderStatus.PAYMENT_FAILED
    item_previous_statuses = {}
    
    # Update item statuses - sync with order status
    for item in order.items:
        item_previous_statuses[item.id] = item.order_status
    
    # Sync all order item statuses with order status
    sync_order_item_statuses_with_order_status(db, order, OrderStatus.PAYMENT_FAILED, update_timestamp=True)
    
    # Create status history entry
    status_notes = f"Payment marked as FAILED."
    if reason:
        status_notes += f" Reason: {reason}"
    else:
        status_notes += " Payment verification failed or payment was declined. Payment status set to FAILED. Order status set to PAYMENT_FAILED."
    
    status_history = OrderStatusHistory(
        order_id=order.id,
        status=OrderStatus.PAYMENT_FAILED,
        previous_status=previous_order_status,
        notes=status_notes,
        changed_by="system"
    )
    db.add(status_history)
    
    # Create status history for order items
    for item in order.items:
        item_previous_status = item_previous_statuses.get(item.id, OrderStatus.PENDING_PAYMENT)
        item_status_history = OrderStatusHistory(
            order_id=order.id,
            order_item_id=item.id,
            status=OrderStatus.PAYMENT_FAILED,
            previous_status=item_previous_status,
            notes="Payment FAILED. Order item payment failed.",
            changed_by="system"
        )
        db.add(item_status_history)
    
    db.flush()
    db.refresh(order)
    
    logger.info(f"Payment marked as {payment_status.value} for order {order.order_number} (ID: {order.id}). Previous status: {previous_payment_status.value}")
    
    return order


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus,
    changed_by: str,
    notes: Optional[str] = None,
    order_item_id: Optional[int] = None,
    address_id: Optional[int] = None,
    scheduled_date: Optional[datetime] = None,
    technician_name: Optional[str] = None,
    technician_contact: Optional[str] = None
) -> Order:
    """
    Update order status and create status history entry.
    If order_item_id or address_id is provided, updates only that specific item.
    Otherwise, updates the entire order and all items with matching addresses.
    
    Technician and scheduling fields are optional and only applied when provided.
    For statuses like 'report_ready', 'testing_in_progress', 'sample_received_by_lab',
    technician details are not needed and will be cleared if not provided.
    
    Statuses that typically need technician info:
    - scheduled: requires scheduled_date, technician_name, technician_contact
    - schedule_confirmed_by_lab: may need technician info
    - sample_collected: may need technician info
    
    Statuses that don't need technician info:
    - confirmed, sample_received_by_lab, testing_in_progress, report_ready
    """
    # Statuses where technician details are not relevant
    # For these statuses, if technician fields are not provided, they will be cleared
    # However, if explicitly provided, they will still be set (for flexibility)
    STATUSES_WITHOUT_TECHNICIAN = {
        OrderStatus.PENDING_PAYMENT,
        OrderStatus.PROCESSING,
        OrderStatus.PAYMENT_FAILED,
        OrderStatus.CONFIRMED,
        OrderStatus.SAMPLE_RECEIVED_BY_LAB,
        OrderStatus.TESTING_IN_PROGRESS,
        OrderStatus.REPORT_READY
    }
    
    # If status doesn't need technician info and fields are not provided, clear them
    # If fields ARE provided, use them regardless of status (for flexibility)
    should_clear_technician = new_status in STATUSES_WITHOUT_TECHNICIAN
    
    # Load order with items to ensure all items are in session for updates
    from sqlalchemy.orm import joinedload
    order = db.query(Order).options(joinedload(Order.items)).filter(Order.id == order_id).first()
    if not order:
        raise ValueError("Order not found")
    
    # Validate payment status for post-payment statuses
    # Post-payment statuses can only be set if payment is completed
    POST_PAYMENT_STATUSES = {
        OrderStatus.SCHEDULED,
        OrderStatus.SCHEDULE_CONFIRMED_BY_LAB,
        OrderStatus.SAMPLE_COLLECTED,
        OrderStatus.SAMPLE_RECEIVED_BY_LAB,
        OrderStatus.TESTING_IN_PROGRESS,
        OrderStatus.REPORT_READY
    }
    
    if new_status in POST_PAYMENT_STATUSES:
        if order.payment_status != PaymentStatus.COMPLETED:
            raise ValueError(
                f"Cannot set order status to {new_status.value} because payment status is {order.payment_status.value}. "
                f"Payment must be completed before setting post-payment statuses."
            )
    
    # Prevent setting order back to PENDING_PAYMENT if payment is already completed
    if new_status == OrderStatus.PENDING_PAYMENT and order.payment_status == PaymentStatus.COMPLETED:
        raise ValueError(
            "Cannot set order status to PENDING_PAYMENT because payment is already completed. "
            "Order status should remain CONFIRMED or progress to next stages."
        )
    
    
    # Prevent manually setting order to CONFIRMED - only webhook can confirm orders
    # This ensures cart clearing and genetic test flag setting happen correctly
    if new_status == OrderStatus.CONFIRMED:
        raise ValueError(
            "Cannot manually set order status to CONFIRMED. "
            "Order confirmation must happen via webhook (confirm_order_from_webhook) to ensure "
            "cart clearing and genetic test flag setting occur correctly."
        )
    
    # Prevent setting order to post-payment statuses if payment is not completed
    if new_status in POST_PAYMENT_STATUSES:
        if order.payment_status != PaymentStatus.COMPLETED:
            raise ValueError(
                f"Cannot set order status to {new_status.value} because payment status is {order.payment_status.value}. "
                f"Payment must be completed before setting post-payment statuses."
            )
    
    # If updating specific order item
    if order_item_id:
        order_item = db.query(OrderItem).filter(
            OrderItem.id == order_item_id,
            OrderItem.order_id == order_id
        ).first()
        if not order_item:
            raise ValueError("Order item not found")
        
        previous_status = order_item.order_status
        order_item.order_status = new_status
        order_item.status_updated_at = now_ist()
        
        # Update technician and scheduling fields only if provided
        # For statuses that don't need technician info, clear fields if not provided
        if scheduled_date is not None:
            order_item.scheduled_date = scheduled_date
        elif should_clear_technician:
            order_item.scheduled_date = None
            
        if technician_name is not None:
            order_item.technician_name = technician_name
        elif should_clear_technician:
            order_item.technician_name = None
            
        if technician_contact is not None:
            order_item.technician_contact = technician_contact
        elif should_clear_technician:
            order_item.technician_contact = None
        
        # Create status history entry for this item
        status_history = OrderStatusHistory(
            order_id=order_id,
            order_item_id=order_item_id,
            status=new_status,
            previous_status=previous_status,
            notes=notes or f"Status updated for order item {order_item_id}",
            changed_by=changed_by
        )
        db.add(status_history)
        
        # Also update order-level status if all items have the same status
        _sync_order_status(db, order)
    
    # If updating by address_id (all items with that address)
    elif address_id:
        order_items = db.query(OrderItem).filter(
            OrderItem.order_id == order_id,
            OrderItem.address_id == address_id
        ).all()
        
        if not order_items:
            raise ValueError(f"No order items found for address {address_id} in this order")
        
        for item in order_items:
            previous_status = item.order_status
            item.order_status = new_status
            item.status_updated_at = now_ist()
            
            # Update technician and scheduling fields only if provided
            # For statuses that don't need technician info, clear fields if not provided
            if scheduled_date is not None:
                item.scheduled_date = scheduled_date
            elif should_clear_technician:
                item.scheduled_date = None
                
            if technician_name is not None:
                item.technician_name = technician_name
            elif should_clear_technician:
                item.technician_name = None
                
            if technician_contact is not None:
                item.technician_contact = technician_contact
            elif should_clear_technician:
                item.technician_contact = None
            
            # Create status history entry for each item
            status_history = OrderStatusHistory(
                order_id=order_id,
                order_item_id=item.id,
                status=new_status,
                previous_status=previous_status,
                notes=notes or f"Status updated for address {address_id}",
                changed_by=changed_by
            )
            db.add(status_history)
        
        # Also update order-level status if all items have the same status
        _sync_order_status(db, order)
    
    # Update entire order (default behavior)
    else:
        previous_status = order.order_status
        order.order_status = new_status
        order.status_updated_at = now_ist()
        
        # Update all order items to match - sync with order status
        sync_order_item_statuses_with_order_status(db, order, new_status, update_timestamp=True)
        
        # Update technician and scheduling fields for all items only if provided
        # For statuses that don't need technician info, clear fields if not provided
        for item in order.items:
            if scheduled_date is not None:
                item.scheduled_date = scheduled_date
            elif should_clear_technician:
                item.scheduled_date = None
                
            if technician_name is not None:
                item.technician_name = technician_name
            elif should_clear_technician:
                item.technician_name = None
                
            if technician_contact is not None:
                item.technician_contact = technician_contact
            elif should_clear_technician:
                item.technician_contact = None
        
        # Create status history entry for order
        status_history = OrderStatusHistory(
            order_id=order_id,
            status=new_status,
            previous_status=previous_status,
            notes=notes,
            changed_by=changed_by
        )
        db.add(status_history)
    
    db.commit()
    db.refresh(order)
    
    return order


def _sync_order_status(db: Session, order: Order):
    """
    Sync order-level status based on order items.
    If all items have the same status, update order status to match.
    Otherwise, keep order status as the most common status or leave as is.
    
    Validates that status changes are consistent with payment status.
    """
    if not order.items:
        return
    
    # Get all item statuses
    item_statuses = [item.order_status for item in order.items]
    
    # Determine target status
    if len(set(item_statuses)) == 1:
        target_status = item_statuses[0]
    else:
        from collections import Counter
        target_status = Counter(item_statuses).most_common(1)[0][0]
    
    # Validate status change is consistent with payment status
    # Don't set to PENDING_PAYMENT if payment is completed
    if target_status == OrderStatus.PENDING_PAYMENT and order.payment_status == PaymentStatus.COMPLETED:
        # If payment is completed, don't sync to PENDING_PAYMENT
        # Keep current order status or use CONFIRMED as minimum
        if order.order_status != OrderStatus.PENDING_PAYMENT:
            return  # Keep current status
        target_status = OrderStatus.CONFIRMED
    
    # Don't set to CONFIRMED or post-payment statuses if payment is not completed
    POST_PAYMENT_STATUSES = {
        OrderStatus.CONFIRMED,
        OrderStatus.SCHEDULED,
        OrderStatus.SCHEDULE_CONFIRMED_BY_LAB,
        OrderStatus.SAMPLE_COLLECTED,
        OrderStatus.SAMPLE_RECEIVED_BY_LAB,
        OrderStatus.TESTING_IN_PROGRESS,
        OrderStatus.REPORT_READY
    }
    
    if target_status in POST_PAYMENT_STATUSES and order.payment_status != PaymentStatus.COMPLETED:
        # If payment is not completed, don't sync to post-payment statuses
        # Keep current status or use appropriate status based on payment
        if order.order_status not in POST_PAYMENT_STATUSES:
            return  # Keep current status
        # If payment failed, keep as PENDING_PAYMENT (user can retry), otherwise keep current status
        if order.payment_status == PaymentStatus.FAILED:
            target_status = OrderStatus.PENDING_PAYMENT
        else:
            # Keep current status or use PENDING_PAYMENT
            target_status = order.order_status if order.order_status else OrderStatus.PENDING_PAYMENT
    
    # Update order status
    order.order_status = target_status
    order.status_updated_at = now_ist()


def get_order_by_id(db: Session, order_id: int, user_id: Optional[int] = None, include_all_payment_statuses: bool = False) -> Optional[Order]:
    """
    Get order by ID, optionally filtered by user access.
    By default, only returns orders with verified payment for security.
    Set include_all_payment_statuses=True to allow viewing pending/failed orders (for order owner only).
    
    User can access order if:
    1. Order belongs to user (Order.user_id = user_id), OR
    2. User has transferred members that appear in the order (via order_items)
    
    Args:
        db: Database session
        order_id: Order ID
        user_id: Optional user ID for access control
        include_all_payment_statuses: If True, allows viewing orders with any payment status (for order owner)
    """
    from Member_module.Member_model import Member
    
    # Build query - allow all payment statuses if flag is set
    query = db.query(Order).filter(Order.id == order_id)
    
    # If not including all statuses, filter to completed only
    if not include_all_payment_statuses:
        query = query.filter(Order.payment_status == PaymentStatus.COMPLETED)
    
    if user_id:
        # Check if user owns the order OR has transferred members in the order
        order = query.first()
        if not order:
            return None
        
        # Check if user owns the order
        if order.user_id == user_id:
            return order
        
        # User doesn't have access (removed transferred member check)
        
        # User doesn't have access
        return None
    
    return query.first()


def get_order_by_number(db: Session, order_number: str, user_id: Optional[int] = None, include_all_payment_statuses: bool = False) -> Optional[Order]:
    """
    Get order by order number, optionally filtered by user access.
    By default, only returns orders with verified payment for security.
    Set include_all_payment_statuses=True to allow viewing pending/failed orders (for order owner only).
    
    User can access order if:
    1. Order belongs to user (Order.user_id = user_id), OR
    2. User has transferred members that appear in the order (via order_items)
    
    Args:
        db: Database session
        order_number: Order number (e.g., "ORD2024012012345678")
        user_id: Optional user ID for access control
        include_all_payment_statuses: If True, allows viewing orders with any payment status (for order owner)
    """
    from Member_module.Member_model import Member
    
    # Build query - allow all payment statuses if flag is set
    query = db.query(Order).filter(Order.order_number == order_number)
    
    # If not including all statuses, filter to completed only
    if not include_all_payment_statuses:
        query = query.filter(Order.payment_status == PaymentStatus.COMPLETED)
    
    if user_id:
        # Check if user owns the order OR has transferred members in the order
        order = query.first()
        if not order:
            return None
        
        # Check if user owns the order
        if order.user_id == user_id:
            return order
        
        # User doesn't have access (removed transferred member check)
        
        # User doesn't have access
        return None
    
    return query.first()


def get_user_orders(db: Session, user_id: int, limit: int = 50, payment_status_filter: Optional[PaymentStatus] = None) -> List[Order]:
    """
    Get all orders for a user.
    By default, returns all orders regardless of payment status so users can see pending/failed orders.
    Can optionally filter by payment_status if needed.
    
    Returns orders owned by the user (Order.user_id = user_id)
    
    Args:
        db: Database session
        user_id: User ID
        limit: Maximum number of orders to return
        payment_status_filter: Optional payment status filter (None = show all statuses)
    """
    from Member_module.Member_model import Member
    
    # Build filter for user's own orders
    own_orders_filter = [Order.user_id == user_id]
    if payment_status_filter:
        own_orders_filter.append(Order.payment_status == payment_status_filter)
    
    # Get user's own orders - show all payment statuses by default
    own_orders = db.query(Order).filter(*own_orders_filter).all()
    
    # Sort by created_at descending and limit
    all_orders = sorted(
        own_orders,
        key=lambda x: x.created_at,
        reverse=True
    )[:limit]
    
    return all_orders

