"""
Order CRUD operations.
"""
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import datetime
from typing import Optional, List
import secrets
from .Order_model import (
    Order, OrderItem, OrderSnapshot, OrderStatusHistory,
    OrderStatus, PaymentStatus, PaymentMethod
)
from Cart_module.Cart_model import CartItem
from Product_module.Product_model import Product
from Member_module.Member_model import Member
from Address_module.Address_model import Address
import logging

logger = logging.getLogger(__name__)


def generate_order_number() -> str:
    """Generate unique order number"""
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    random_part = secrets.token_hex(4).upper()
    return f"ORD{timestamp}{random_part}"


def create_order_from_cart(
    db: Session,
    user_id: int,
    address_id: Optional[int],
    cart_item_ids: List[int],
    razorpay_order_id: Optional[str] = None
) -> Order:
    """
    Create order from cart items.
    Creates snapshots of products, members, and addresses at time of order.
    """
    # Validate all cart items belong to user
    cart_items = (
        db.query(CartItem)
        .filter(
            CartItem.id.in_(cart_item_ids),
            CartItem.user_id == user_id
        )
        .all()
    )
    
    if len(cart_items) != len(cart_item_ids):
        raise ValueError("One or more cart items not found or do not belong to you")
    
    if not cart_items:
        raise ValueError("No cart items selected")
    
    # Determine primary address for order header
    unique_cart_address_ids = {item.address_id for item in cart_items}
    primary_address_id = address_id
    address = None

    if primary_address_id:
        address = db.query(Address).filter(
            Address.id == primary_address_id,
            Address.user_id == user_id
        ).first()
        if not address:
            raise ValueError("Address not found or does not belong to you")
    else:
        if not unique_cart_address_ids:
            raise ValueError("No addresses associated with selected cart items")
        primary_address_id = next(iter(unique_cart_address_ids))
        address = db.query(Address).filter(
            Address.id == primary_address_id,
            Address.user_id == user_id
        ).first()
        if not address:
            raise ValueError("Primary address derived from cart items not found")
        if len(unique_cart_address_ids) > 1:
            logger.info(
                "Order creation for user %s contains multiple addresses; using %s as primary",
                user_id,
                primary_address_id
            )
    
    # Calculate totals
    subtotal = 0.0
    delivery_charge = 50.0  # Fixed delivery charge
    discount = 0.0
    
    # Group cart items by group_id to calculate totals correctly
    grouped_items = {}
    for item in cart_items:
        group_key = item.group_id or f"single_{item.id}"
        if group_key not in grouped_items:
            grouped_items[group_key] = []
        grouped_items[group_key].append(item)
    
    # Calculate subtotal (price is per product, not per member)
    for group_key, items in grouped_items.items():
        item = items[0]  # Use first item as representative
        product = item.product
        # Only count once per product group
        subtotal += item.quantity * product.SpecialPrice
    
    total_amount = subtotal + delivery_charge - discount
    
    # Create order
    order = Order(
        order_number=generate_order_number(),
        user_id=user_id,
        address_id=primary_address_id,
        subtotal=subtotal,
        delivery_charge=delivery_charge,
        discount=discount,
        total_amount=total_amount,
        payment_method=PaymentMethod.RAZORPAY,
        payment_status=PaymentStatus.PENDING,
        razorpay_order_id=razorpay_order_id,
        order_status=OrderStatus.ORDER_CONFIRMED
    )
    db.add(order)
    db.flush()  # Get order.id
    
    # Create order items and snapshots
    for cart_item in cart_items:
        product = cart_item.product
        member = cart_item.member
        address_obj = cart_item.address
        
        # Create snapshot
        snapshot = OrderSnapshot(
            order_id=order.id,
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
                "dob": member.dob.isoformat() if member.dob else None,
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
            }
        )
        db.add(snapshot)
        db.flush()
        
        # Create order item
        order_item = OrderItem(
            order_id=order.id,
            product_id=product.ProductId,
            member_id=member.id,
            address_id=cart_item.address_id,
            snapshot_id=snapshot.id,
            quantity=cart_item.quantity,
            unit_price=product.SpecialPrice,
            total_price=cart_item.quantity * product.SpecialPrice
        )
        db.add(order_item)
    
    # Create initial status history
    status_history = OrderStatusHistory(
        order_id=order.id,
        status=OrderStatus.ORDER_CONFIRMED,
        previous_status=None,
        notes="Order created from cart",
        changed_by=str(user_id)
    )
    db.add(status_history)
    
    db.commit()
    db.refresh(order)
    
    return order


def verify_and_complete_payment(
    db: Session,
    order_id: int,
    razorpay_order_id: str,
    razorpay_payment_id: str,
    razorpay_signature: str
) -> Order:
    """
    Verify Razorpay payment and update order payment status.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise ValueError("Order not found")
    
    if order.payment_status == PaymentStatus.COMPLETED:
        raise ValueError("Payment already completed for this order")
    
    # Verify signature
    from .razorpay_service import verify_payment_signature
    is_valid = verify_payment_signature(razorpay_order_id, razorpay_payment_id, razorpay_signature)
    
    if not is_valid:
        # Update payment status to failed
        order.payment_status = PaymentStatus.FAILED
        db.commit()
        raise ValueError("Invalid payment signature. Payment verification failed.")
    
    # Update order with payment details
    order.razorpay_payment_id = razorpay_payment_id
    order.razorpay_signature = razorpay_signature
    order.payment_status = PaymentStatus.COMPLETED
    order.payment_date = datetime.utcnow()
    
    db.commit()
    db.refresh(order)
    
    return order


def update_order_status(
    db: Session,
    order_id: int,
    new_status: OrderStatus,
    changed_by: str,
    notes: Optional[str] = None,
    scheduled_date: Optional[datetime] = None,
    technician_name: Optional[str] = None,
    technician_contact: Optional[str] = None,
    lab_name: Optional[str] = None
) -> Order:
    """
    Update order status and create status history entry.
    """
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise ValueError("Order not found")
    
    previous_status = order.order_status
    
    # Update order status
    order.order_status = new_status
    order.status_updated_at = datetime.utcnow()
    
    # Update additional fields if provided
    if scheduled_date:
        order.scheduled_date = scheduled_date
    if technician_name:
        order.technician_name = technician_name
    if technician_contact:
        order.technician_contact = technician_contact
    if lab_name:
        order.lab_name = lab_name
    
    # Create status history entry
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


def get_order_by_id(db: Session, order_id: int, user_id: Optional[int] = None) -> Optional[Order]:
    """Get order by ID, optionally filtered by user_id"""
    query = db.query(Order).filter(Order.id == order_id)
    if user_id:
        query = query.filter(Order.user_id == user_id)
    return query.first()


def get_user_orders(db: Session, user_id: int, limit: int = 50) -> List[Order]:
    """Get all orders for a user"""
    return (
        db.query(Order)
        .filter(Order.user_id == user_id)
        .order_by(Order.created_at.desc())
        .limit(limit)
        .all()
    )

