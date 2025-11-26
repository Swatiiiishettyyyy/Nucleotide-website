"""
Order router - handles order creation, payment, and tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List
from collections import defaultdict
import uuid
import logging

from deps import get_db
from Login_module.Utils.auth_user import get_current_user
from Login_module.User.user_model import User
from .Order_schema import (
    CreateOrderRequest,
    OrderResponse,
    RazorpayOrderResponse,
    VerifyPaymentRequest,
    PaymentVerificationResponse,
    UpdateOrderStatusRequest,
    OrderTrackingResponse
)
from .Order_crud import (
    create_order_from_cart,
    verify_and_complete_payment,
    update_order_status,
    get_order_by_id,
    get_user_orders
)
from .razorpay_service import create_razorpay_order
from .Order_model import OrderStatus, PaymentStatus
from Cart_module.Cart_model import CartItem

router = APIRouter(prefix="/orders", tags=["Orders"])

logger = logging.getLogger(__name__)


def get_client_info(request: Request):
    """Extract client IP and user agent from request"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


@router.post("/create", response_model=RazorpayOrderResponse)
def create_order(
    request_data: CreateOrderRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create order from cart items.
    Creates Razorpay order for payment.
    No COD option - payment must be completed online.
    """
    try:
        # Validate cart items
        cart_items = (
            db.query(CartItem)
            .filter(
                CartItem.id.in_(request_data.cart_item_ids),
                CartItem.user_id == current_user.id
            )
            .all()
        )
        
        if len(cart_items) != len(request_data.cart_item_ids):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="One or more cart items not found"
            )
        
        # Calculate total amount (will be recalculated in create_order_from_cart with coupon)
        # This is just for Razorpay order creation - actual order will have correct totals
        subtotal = 0.0
        delivery_charge = 50.0
        grouped_items = {}
        
        for item in cart_items:
            group_key = item.group_id or f"single_{item.id}"
            if group_key not in grouped_items:
                grouped_items[group_key] = []
            grouped_items[group_key].append(item)
        
        for group_key, items in grouped_items.items():
            item = items[0]
            product = item.product
            subtotal += item.quantity * product.SpecialPrice
        
        # Get coupon discount for Razorpay order amount
        from Cart_module.coupon_service import get_applied_coupon
        applied_coupon = get_applied_coupon(db, current_user.id)
        coupon_discount = applied_coupon.discount_amount if applied_coupon else 0.0
        
        total_amount = subtotal + delivery_charge - coupon_discount
        total_amount = max(0.0, total_amount)  # Ensure not negative
        
        # Derive primary address id (requested or from first cart item)
        primary_address_id = request_data.address_id or (cart_items[0].address_id if cart_items else None)

        # Create Razorpay order first
        razorpay_order = create_razorpay_order(
            amount=total_amount,
            currency="INR",
            receipt=f"order_{current_user.id}_{uuid.uuid4().hex[:8]}",
            notes={
                "user_id": str(current_user.id),
                "address_id": str(primary_address_id) if primary_address_id else "None"
            }
        )
        
        # Create order in database
        order = create_order_from_cart(
            db=db,
            user_id=current_user.id,
            address_id=primary_address_id,
            cart_item_ids=request_data.cart_item_ids,
            razorpay_order_id=razorpay_order.get("id")
        )
        
        logger.info(f"Order {order.order_number} created for user {current_user.id}")
        
        return RazorpayOrderResponse(
            razorpay_order_id=razorpay_order.get("id"),
            amount=total_amount,
            currency="INR",
            order_id=order.id,
            order_number=order.order_number
        )
    
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating order: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating order: {str(e)}"
        )


@router.post("/verify-payment", response_model=PaymentVerificationResponse)
def verify_payment(
    payment_data: VerifyPaymentRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Verify Razorpay payment and complete order.
    Removes cart items after successful payment.
    """
    try:
        # Verify and complete payment
        order = verify_and_complete_payment(
            db=db,
            order_id=payment_data.order_id,
            razorpay_order_id=payment_data.razorpay_order_id,
            razorpay_payment_id=payment_data.razorpay_payment_id,
            razorpay_signature=payment_data.razorpay_signature
        )
        
        # Verify order belongs to user
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Order does not belong to you"
            )
        
        # Delete cart items after successful payment
        # Get order item details (product_id, member_id pairs)
        order_item_pairs = [(item.product_id, item.member_id) for item in order.items]
        
        # Find and delete matching cart items by product_id and member_id
        deleted_group_ids = set()
        
        for product_id, member_id in order_item_pairs:
            cart_item = (
                db.query(CartItem)
                .filter(
                    CartItem.user_id == current_user.id,
                    CartItem.product_id == product_id,
                    CartItem.member_id == member_id
                )
                .first()
            )
            
            if cart_item:
                # If cart item has group_id, delete all items in the group (for couple/family products)
                if cart_item.group_id and cart_item.group_id not in deleted_group_ids:
                    group_items = (
                        db.query(CartItem)
                        .filter(
                            CartItem.group_id == cart_item.group_id,
                            CartItem.user_id == current_user.id
                        )
                        .all()
                    )
                    for item in group_items:
                        db.delete(item)
                    deleted_group_ids.add(cart_item.group_id)
                elif not cart_item.group_id:
                    # Single item, delete it
                    db.delete(cart_item)
        
        # Remove applied coupon after successful payment
        from Cart_module.coupon_service import remove_coupon_from_cart
        remove_coupon_from_cart(db, current_user.id)
        
        db.commit()
        
        logger.info(f"Payment verified and order {order.order_number} completed for user {current_user.id}")
        
        return PaymentVerificationResponse(
            status="success",
            message="Payment verified successfully. Order confirmed.",
            order_id=order.id,
            order_number=order.order_number,
            payment_status=order.payment_status.value
        )
    
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except Exception as e:
        db.rollback()
        logger.error(f"Error verifying payment: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error verifying payment: {str(e)}"
        )


@router.get("/list", response_model=List[OrderResponse])
def get_orders(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all orders for current user"""
    orders = get_user_orders(db, current_user.id)
    
    result = []
    for order in orders:
        order_items = []
        for item in order.items:
            # Use snapshot data if available, fallback to original tables
            snapshot = item.snapshot if item.snapshot else None
            
            if snapshot:
                # Use snapshot data (from time of order confirmation)
                product_data = snapshot.product_data or {}
                member_data = snapshot.member_data or {}
                address_data = snapshot.address_data or {}
                
                address_details = {
                    "address_label": address_data.get("address_label"),
                    "street_address": address_data.get("street_address"),
                    "landmark": address_data.get("landmark"),
                    "locality": address_data.get("locality"),
                    "city": address_data.get("city"),
                    "state": address_data.get("state"),
                    "postal_code": address_data.get("postal_code"),
                    "country": address_data.get("country")
                }
                
                order_items.append({
                    "order_item_id": item.id,
                    "product_id": product_data.get("ProductId", item.product_id),
                    "product_name": product_data.get("Name", "Unknown"),
                    "member_id": member_data.get("id", item.member_id),
                    "member_name": member_data.get("name", "Unknown"),
                    "address_id": address_data.get("id", item.address_id),
                    "address_label": address_data.get("address_label"),
                    "address_details": address_details,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                    "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None
                })
            else:
                # Fallback to original tables (for backwards compatibility)
                address_details = None
                if item.address:
                    address_details = {
                        "address_label": item.address.address_label,
                        "street_address": item.address.street_address,
                        "landmark": item.address.landmark,
                        "locality": item.address.locality,
                        "city": item.address.city,
                        "state": item.address.state,
                        "postal_code": item.address.postal_code,
                        "country": item.address.country
                    }
                
                order_items.append({
                    "order_item_id": item.id,
                    "product_id": item.product_id,
                    "product_name": item.product.Name if item.product else "Unknown",
                    "member_id": item.member_id,
                    "member_name": item.member.name if item.member else "Unknown",
                    "address_id": item.address_id,
                    "address_label": item.address.address_label if item.address else None,
                    "address_details": address_details,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "total_price": item.total_price,
                    "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                    "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None
                })
        
        result.append({
            "order_id": order.id,
            "order_number": order.order_number,
            "user_id": order.user_id,
            "address_id": order.address_id,
            "subtotal": order.subtotal,
            "discount": order.discount,
            "coupon_code": order.coupon_code,
            "coupon_discount": order.coupon_discount,
            "delivery_charge": order.delivery_charge,
            "total_amount": order.total_amount,
            "payment_status": order.payment_status.value,
            "order_status": order.order_status.value,
            "razorpay_order_id": order.razorpay_order_id,
            "created_at": order.created_at,
            "items": order_items
        })
    
    return result


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get order details by ID"""
    order = get_order_by_id(db, order_id, user_id=current_user.id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    order_items = []
    for item in order.items:
        # Use snapshot data if available, fallback to original tables
        snapshot = item.snapshot if item.snapshot else None
        
        if snapshot:
            # Use snapshot data (from time of order confirmation)
            product_data = snapshot.product_data or {}
            member_data = snapshot.member_data or {}
            address_data = snapshot.address_data or {}
            
            address_details = {
                "address_label": address_data.get("address_label"),
                "street_address": address_data.get("street_address"),
                "landmark": address_data.get("landmark"),
                "locality": address_data.get("locality"),
                "city": address_data.get("city"),
                "state": address_data.get("state"),
                "postal_code": address_data.get("postal_code"),
                "country": address_data.get("country")
            }
            
            order_items.append({
                "order_item_id": item.id,
                "product_id": product_data.get("ProductId", item.product_id),
                "product_name": product_data.get("Name", "Unknown"),
                "member_id": member_data.get("id", item.member_id),
                "member_name": member_data.get("name", "Unknown"),
                "address_id": address_data.get("id", item.address_id),
                "address_label": address_data.get("address_label"),
                "address_details": address_details,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None
            })
        else:
            # Fallback to original tables (for backwards compatibility)
            address_details = None
            if item.address:
                address_details = {
                    "address_label": item.address.address_label,
                    "street_address": item.address.street_address,
                    "landmark": item.address.landmark,
                    "locality": item.address.locality,
                    "city": item.address.city,
                    "state": item.address.state,
                    "postal_code": item.address.postal_code,
                    "country": item.address.country
                }
            
            order_items.append({
                "order_item_id": item.id,
                "product_id": item.product_id,
                "product_name": item.product.Name if item.product else "Unknown",
                "member_id": item.member_id,
                "member_name": item.member.name if item.member else "Unknown",
                "address_id": item.address_id,
                "address_label": item.address.address_label if item.address else None,
                "address_details": address_details,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None
            })
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "user_id": order.user_id,
        "address_id": order.address_id,
        "subtotal": order.subtotal,
        "discount": order.discount,
        "coupon_code": order.coupon_code,
        "coupon_discount": order.coupon_discount,
        "delivery_charge": order.delivery_charge,
        "total_amount": order.total_amount,
        "payment_status": order.payment_status.value,
        "order_status": order.order_status.value,
        "razorpay_order_id": order.razorpay_order_id,
        "created_at": order.created_at,
        "items": order_items
    }


@router.get("/{order_id}/tracking", response_model=OrderTrackingResponse)
def get_order_tracking(
    order_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get order tracking information with status history.
    Returns per-address tracking for orders with multiple addresses (couple/family packs).
    """
    order = get_order_by_id(db, order_id, user_id=current_user.id)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Get order-level status history (where order_item_id is None)
    # Safely access order_item_id - it may not exist in older database schemas
    order_status_history = [
        {
            "status": hist.status.value,
            "previous_status": hist.previous_status.value if hist.previous_status else None,
            "notes": hist.notes,
            "changed_by": hist.changed_by,
            "created_at": hist.created_at.isoformat() if hist.created_at else None,
            "order_item_id": getattr(hist, 'order_item_id', None)
        }
        for hist in order.status_history if getattr(hist, 'order_item_id', None) is None
    ]
    
    # Group order items by address for per-address tracking
    address_groups = defaultdict(lambda: {"items": [], "address_data": None, "address_id": None})
    
    for item in order.items:
        # Use snapshot data if available
        snapshot = item.snapshot if item.snapshot else None
        # Get address_id from snapshot or item (handle NULL case)
        if snapshot and snapshot.address_data:
            address_id = snapshot.address_data.get("id") or item.address_id
        else:
            address_id = item.address_id
        
        # Group by address_id (can be None if address was deleted)
        address_groups[address_id]["items"].append((item, snapshot))
        if not address_groups[address_id]["address_data"]:
            if snapshot and snapshot.address_data:
                address_groups[address_id]["address_data"] = snapshot.address_data
                address_groups[address_id]["address_id"] = address_id
            elif item.address:
                # Fallback to original address
                address_groups[address_id]["address_data"] = {
                    "id": item.address.id,
                    "address_label": item.address.address_label,
                    "street_address": item.address.street_address,
                    "landmark": item.address.landmark,
                    "locality": item.address.locality,
                    "city": item.address.city,
                    "state": item.address.state,
                    "postal_code": item.address.postal_code,
                    "country": item.address.country
                }
                address_groups[address_id]["address_id"] = address_id
    
    # Build per-address tracking data
    address_tracking_list = []
    for address_id, group_data in address_groups.items():
        address_data = group_data["address_data"]
        items_with_snapshots = group_data["items"]
        
        # Get status history for items at this address
        item_ids = [item.id for item, _ in items_with_snapshots]
        item_status_history = []
        
        # Build member name lookup from snapshots
        member_name_map = {}
        for item, snapshot in items_with_snapshots:
            if snapshot and snapshot.member_data:
                member_name_map[item.id] = snapshot.member_data.get("name", "Unknown")
            elif item.member:
                member_name_map[item.id] = item.member.name
        
        for hist in order.status_history:
            hist_item_id = getattr(hist, 'order_item_id', None)
            if hist_item_id in item_ids:
                item_status_history.append({
                    "status": hist.status.value,
                    "previous_status": hist.previous_status.value if hist.previous_status else None,
                    "notes": hist.notes,
                    "changed_by": hist.changed_by,
                    "created_at": hist.created_at.isoformat() if hist.created_at else None,
                    "order_item_id": hist_item_id,
                    "member_name": member_name_map.get(hist_item_id)
                })
        
        # Get current status (should be same for all items at this address, but take the first)
        current_item_status = items_with_snapshots[0][0].order_status.value if items_with_snapshots else order.order_status.value
        
        # Build members list for this address using snapshot data
        members_list = []
        for item, snapshot in items_with_snapshots:
            if snapshot and snapshot.member_data:
                members_list.append({
                    "member_id": snapshot.member_data.get("id", item.member_id),
                    "member_name": snapshot.member_data.get("name", "Unknown"),
                    "order_item_id": item.id,
                    "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status)
                })
            else:
                # Fallback to original member
                members_list.append({
                    "member_id": item.member_id,
                    "member_name": item.member.name if item.member else "Unknown",
                    "order_item_id": item.id,
                    "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status)
                })
        
        # Build address details from snapshot
        address_details = None
        if address_data:
            address_details = {
                "address_label": address_data.get("address_label"),
                "street_address": address_data.get("street_address"),
                "landmark": address_data.get("landmark"),
                "locality": address_data.get("locality"),
                "city": address_data.get("city"),
                "state": address_data.get("state"),
                "postal_code": address_data.get("postal_code"),
                "country": address_data.get("country")
            }
        
        address_tracking_list.append({
            "address_id": address_id,
            "address_label": address_data.get("address_label") if address_data else None,
            "address_details": address_details,
            "members": members_list,
            "current_status": current_item_status,
            "status_history": item_status_history,
            "estimated_completion": order.scheduled_date.isoformat() if order.scheduled_date else None
        })
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "current_status": order.order_status.value,
        "status_history": order_status_history,
        "estimated_completion": order.scheduled_date if order.scheduled_date else None,
        "address_tracking": address_tracking_list
    }


@router.put("/{order_id}/status")
def update_order_status_api(
    order_id: int,
    status_data: UpdateOrderStatusRequest,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update order status (typically used by admin/lab technicians).
    Valid statuses: order_confirmed, scheduled, schedule_confirmed_by_lab,
    sample_collected, sample_received_by_lab, testing_in_progress, report_ready
    """
    try:
        # Validate status
        try:
            new_status = OrderStatus(status_data.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_data.status}"
            )
        
        # Verify order exists
        order = get_order_by_id(db, order_id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Update status (supports per-item or per-address updates)
        order = update_order_status(
            db=db,
            order_id=order_id,
            new_status=new_status,
            changed_by=str(current_user.id),
            notes=status_data.notes,
            scheduled_date=status_data.scheduled_date,
            technician_name=status_data.technician_name,
            technician_contact=status_data.technician_contact,
            lab_name=status_data.lab_name,
            order_item_id=status_data.order_item_id,
            address_id=status_data.address_id
        )
        
        return {
            "status": "success",
            "message": f"Order status updated to {new_status.value}",
            "order_id": order.id,
            "order_number": order.order_number,
            "current_status": order.order_status.value
        }
    
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating order status: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error updating order status: {str(e)}"
        )

