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
    OrderItemTrackingResponse
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
    Create order from all cart items for the authenticated user.
    Creates Razorpay order for payment.
    No COD option - payment must be completed online.
    
    Request: {"cart_id": 1} - cart_id is used as reference, all authenticated user's cart items are included
    Response: {"order_id": 1, "order_number": "ORD123456", "razorpay_order_id": "...", "amount": 27550, "currency": "INR"}
    
    Note: user_id is automatically fetched from the access token (current_user)
    """
    try:
        # Validate cart_id exists and belongs to authenticated user
        cart_reference = db.query(CartItem).filter(
            CartItem.id == request_data.cart_id,
            CartItem.user_id == current_user.id
        ).first()
        
        if not cart_reference:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Cart item not found or does not belong to you"
            )
        
        # Get all cart items for the user
        cart_items = db.query(CartItem).filter(
            CartItem.user_id == current_user.id
        ).order_by(CartItem.group_id, CartItem.created_at).all()
        
        if not cart_items:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cart is empty. Add items to cart before creating order."
            )
        
        # Get unique addresses from cart items
        unique_cart_address_ids = {item.address_id for item in cart_items if item.address_id}
        
        if not unique_cart_address_ids:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cart items must have valid address IDs"
            )
        
        # Use the first address from cart items as primary address
        primary_address_id = next(iter(sorted(unique_cart_address_ids)))
        
        # Verify the address belongs to the user
        from Address_module.Address_model import Address
        address = db.query(Address).filter(
            Address.id == primary_address_id,
            Address.user_id == current_user.id
        ).first()
        
        if not address:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Address ID {primary_address_id} not found or does not belong to you"
            )
        
        # Calculate total amount (will be recalculated in create_order_from_cart with coupon)
        # This is just for Razorpay order creation - actual order will have correct totals
        subtotal = 0.0
        delivery_charge = 0.0
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
        
        # Calculate product discount (per product group, not per cart item row)
        processed_groups = set()
        product_discount = 0.0
        for item in cart_items:
            group_key = item.group_id or f"single_{item.id}"
            if group_key not in processed_groups:
                discount_per_item = item.product.Price - item.product.SpecialPrice
                product_discount += discount_per_item * item.quantity
                processed_groups.add(group_key)
        
        # Calculate total amount
        # Note: subtotal already uses SpecialPrice (product discount is already applied)
        # So we only subtract coupon_discount, not product_discount
        # This matches the corrected cart calculation: grand_total = subtotal_amount + delivery_charge - coupon_amount
        total_amount = subtotal + delivery_charge - coupon_discount
        total_amount = max(0.0, total_amount)  # Ensure not negative

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
        
        # Get all cart item IDs
        cart_item_ids = [item.id for item in cart_items]
        
        # Create order in database
        order = create_order_from_cart(
            db=db,
            user_id=current_user.id,
            address_id=primary_address_id,
            cart_item_ids=cart_item_ids,
            razorpay_order_id=razorpay_order.get("id")
        )
        
        logger.info(f"Order {order.order_number} created for user {current_user.id}")
        
        return RazorpayOrderResponse(
            order_id=order.id,
            order_number=order.order_number,
            razorpay_order_id=razorpay_order.get("id"),
            amount=total_amount,
            currency="INR"
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
        # Group order items by product (group_id equivalent) to build member_address_map
        from collections import defaultdict
        grouped_items = defaultdict(list)
        for item in order.items:
            # Use product_id as group key (items with same product_id are grouped)
            group_key = f"{item.product_id}_{item.order_id}"
            grouped_items[group_key].append(item)
        
        order_items = []
        for group_key, items in grouped_items.items():
            # Use first item as representative for product info
            first_item = items[0]
            snapshot = first_item.snapshot if first_item.snapshot else None
            
            # Get product data from snapshot or item
            if snapshot and snapshot.product_data:
                product_data = snapshot.product_data
                product_name = product_data.get("Name", "Unknown")
                product_id = product_data.get("ProductId", first_item.product_id)
            else:
                product_name = first_item.product.Name if first_item.product else "Unknown"
                product_id = first_item.product_id
            
            # Build member_address_map with full details
            member_address_map = []
            member_ids = []
            address_ids = []
            
            for item in items:
                snapshot = item.snapshot if item.snapshot else None
                
                if snapshot:
                    # Use snapshot data (from time of order confirmation)
                    member_data = snapshot.member_data or {}
                    address_data = snapshot.address_data or {}
                    
                    member_details = {
                        "member_id": member_data.get("id", item.member_id),
                        "name": member_data.get("name", "Unknown"),
                        "relation": member_data.get("relation"),
                        "age": member_data.get("age"),
                        "gender": member_data.get("gender"),
                        "dob": member_data.get("dob"),
                        "mobile": member_data.get("mobile")
                    }
                    
                    address_details = {
                        "address_id": address_data.get("id", item.address_id),
                        "address_label": address_data.get("address_label"),
                        "street_address": address_data.get("street_address"),
                        "landmark": address_data.get("landmark"),
                        "locality": address_data.get("locality"),
                        "city": address_data.get("city"),
                        "state": address_data.get("state"),
                        "postal_code": address_data.get("postal_code"),
                        "country": address_data.get("country")
                    }
                else:
                    # Fallback to original tables
                    member = item.member
                    address = item.address
                    
                    member_details = {
                        "member_id": member.id if member else item.member_id,
                        "name": member.name if member else "Unknown",
                        "relation": member.relation.value if member and hasattr(member.relation, 'value') else (str(member.relation) if member else None),
                        "age": member.age if member else None,
                        "gender": member.gender if member else None,
                        "dob": member.dob.isoformat() if member and member.dob else None,
                        "mobile": member.mobile if member else None
                    }
                    
                    address_details = {
                        "address_id": address.id if address else item.address_id,
                        "address_label": address.address_label if address else None,
                        "street_address": address.street_address if address else None,
                        "landmark": address.landmark if address else None,
                        "locality": address.locality if address else None,
                        "city": address.city if address else None,
                        "state": address.state if address else None,
                        "postal_code": address.postal_code if address else None,
                        "country": address.country if address else None
                    }
                
                member_address_map.append({
                    "member": member_details,
                    "address": address_details,
                    "order_item_id": item.id,
                    "quantity": item.quantity,
                    "unit_price": item.unit_price,
                    "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                    "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None,
                    "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
                    "technician_name": item.technician_name,
                    "technician_contact": item.technician_contact
                })
                
                member_ids.append(member_details["member_id"])
                if address_details["address_id"]:
                    address_ids.append(address_details["address_id"])
            
            # Get unique address IDs
            unique_address_ids = list(set(address_ids))
            
            order_items.append({
                "product_id": product_id,
                "product_name": product_name,
                "member_ids": list(set(member_ids)),
                "address_ids": unique_address_ids,
                "member_address_map": member_address_map,  # Full details with member-address mapping
                "quantity": first_item.quantity,
                "total_amount": sum(item.unit_price * item.quantity for item in items)
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
    
    # Group order items by product to build member_address_map
    from collections import defaultdict
    grouped_items = defaultdict(list)
    for item in order.items:
        # Use product_id as group key (items with same product_id are grouped)
        group_key = f"{item.product_id}_{order.id}"
        grouped_items[group_key].append(item)
    
    order_items = []
    for group_key, items in grouped_items.items():
        # Use first item as representative for product info
        first_item = items[0]
        snapshot = first_item.snapshot if first_item.snapshot else None
        
        # Get product data from snapshot or item
        if snapshot and snapshot.product_data:
            product_data = snapshot.product_data
            product_name = product_data.get("Name", "Unknown")
            product_id = product_data.get("ProductId", first_item.product_id)
        else:
            product_name = first_item.product.Name if first_item.product else "Unknown"
            product_id = first_item.product_id
        
        # Build member_address_map with full details
        member_address_map = []
        member_ids = []
        address_ids = []
        
        for item in items:
            snapshot = item.snapshot if item.snapshot else None
            
            if snapshot:
                # Use snapshot data (from time of order confirmation)
                member_data = snapshot.member_data or {}
                address_data = snapshot.address_data or {}
                
                member_details = {
                    "member_id": member_data.get("id", item.member_id),
                    "name": member_data.get("name", "Unknown"),
                    "relation": member_data.get("relation"),
                    "age": member_data.get("age"),
                    "gender": member_data.get("gender"),
                    "dob": member_data.get("dob"),
                    "mobile": member_data.get("mobile")
                }
                
                address_details = {
                    "address_id": address_data.get("id", item.address_id),
                    "address_label": address_data.get("address_label"),
                    "street_address": address_data.get("street_address"),
                    "landmark": address_data.get("landmark"),
                    "locality": address_data.get("locality"),
                    "city": address_data.get("city"),
                    "state": address_data.get("state"),
                    "postal_code": address_data.get("postal_code"),
                    "country": address_data.get("country")
                }
            else:
                # Fallback to original tables
                member = item.member
                address = item.address
                
                member_details = {
                    "member_id": member.id if member else item.member_id,
                    "name": member.name if member else "Unknown",
                    "relation": member.relation.value if member and hasattr(member.relation, 'value') else (str(member.relation) if member else None),
                    "age": member.age if member else None,
                    "gender": member.gender if member else None,
                    "dob": member.dob.isoformat() if member and member.dob else None,
                    "mobile": member.mobile if member else None
                }
                
                address_details = {
                    "address_id": address.id if address else item.address_id,
                    "address_label": address.address_label if address else None,
                    "street_address": address.street_address if address else None,
                    "landmark": address.landmark if address else None,
                    "locality": address.locality if address else None,
                    "city": address.city if address else None,
                    "state": address.state if address else None,
                    "postal_code": address.postal_code if address else None,
                    "country": address.country if address else None
                }
            
            member_address_map.append({
                "member": member_details,
                "address": address_details,
                "order_item_id": item.id,
                "quantity": item.quantity,
                "unit_price": item.unit_price,
                "order_status": item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status),
                "status_updated_at": item.status_updated_at.isoformat() if item.status_updated_at else None,
                "scheduled_date": item.scheduled_date.isoformat() if item.scheduled_date else None,
                "technician_name": item.technician_name,
                "technician_contact": item.technician_contact
            })
            
            member_ids.append(member_details["member_id"])
            if address_details["address_id"]:
                address_ids.append(address_details["address_id"])
        
        # Get unique address IDs
        unique_address_ids = list(set(address_ids))
        
        order_items.append({
            "product_id": product_id,
            "product_name": product_name,
            "member_ids": list(set(member_ids)),
            "address_ids": unique_address_ids,
            "member_address_map": member_address_map,  # Full details with member-address mapping
            "quantity": first_item.quantity,
            "total_amount": sum(item.unit_price * item.quantity for item in items)
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


@router.get("/{order_id}/{order_item_id}/tracking", response_model=OrderItemTrackingResponse)
def get_order_item_tracking(
    order_id: int,
    order_item_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get tracking information for a specific order item.
    Returns detailed status history, member, address, and product information for the order item.
    """
    from .Order_model import OrderItem
    
    # Verify order exists and belongs to user
    order = get_order_by_id(db, order_id, user_id=current_user.id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Get the specific order item
    order_item = db.query(OrderItem).filter(
        OrderItem.id == order_item_id,
        OrderItem.order_id == order_id,
        OrderItem.user_id == current_user.id
    ).first()
    
    if not order_item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order item not found"
        )
    
    # Get snapshot data
    snapshot = order_item.snapshot if order_item.snapshot else None
    
    # Get member data from snapshot or item
    if snapshot and snapshot.member_data:
        member_data = snapshot.member_data
        member = {
            "member_id": member_data.get("id", order_item.member_id),
            "name": member_data.get("name", "Unknown"),
            "relation": member_data.get("relation"),
            "age": member_data.get("age"),
            "gender": member_data.get("gender"),
            "dob": member_data.get("dob"),
            "mobile": member_data.get("mobile")
        }
    else:
        # Fallback to original member
        member_obj = order_item.member
        member = {
            "member_id": member_obj.id if member_obj else order_item.member_id,
            "name": member_obj.name if member_obj else "Unknown",
            "relation": member_obj.relation.value if member_obj and hasattr(member_obj.relation, 'value') else (str(member_obj.relation) if member_obj else None),
            "age": member_obj.age if member_obj else None,
            "gender": member_obj.gender if member_obj else None,
            "dob": member_obj.dob.isoformat() if member_obj and member_obj.dob else None,
            "mobile": member_obj.mobile if member_obj else None
        }
    
    # Get address data from snapshot or item
    if snapshot and snapshot.address_data:
        address_data = snapshot.address_data
        address = {
            "address_id": address_data.get("id", order_item.address_id),
            "address_label": address_data.get("address_label"),
            "street_address": address_data.get("street_address"),
            "landmark": address_data.get("landmark"),
            "locality": address_data.get("locality"),
            "city": address_data.get("city"),
            "state": address_data.get("state"),
            "postal_code": address_data.get("postal_code"),
            "country": address_data.get("country")
        }
    else:
        # Fallback to original address
        address_obj = order_item.address
        address = {
            "address_id": address_obj.id if address_obj else order_item.address_id,
            "address_label": address_obj.address_label if address_obj else None,
            "street_address": address_obj.street_address if address_obj else None,
            "landmark": address_obj.landmark if address_obj else None,
            "locality": address_obj.locality if address_obj else None,
            "city": address_obj.city if address_obj else None,
            "state": address_obj.state if address_obj else None,
            "postal_code": address_obj.postal_code if address_obj else None,
            "country": address_obj.country if address_obj else None
        }
    
    # Get product data from snapshot or item
    if snapshot and snapshot.product_data:
        product_data = snapshot.product_data
        product = {
            "product_id": product_data.get("ProductId", order_item.product_id),
            "name": product_data.get("Name", "Unknown"),
            "price": product_data.get("Price"),
            "special_price": product_data.get("SpecialPrice"),
            "plan_type": product_data.get("plan_type"),
            "category": product_data.get("category"),
            "images": product_data.get("Images")
        }
    else:
        # Fallback to original product
        product_obj = order_item.product
        product = {
            "product_id": product_obj.ProductId if product_obj else order_item.product_id,
            "name": product_obj.Name if product_obj else "Unknown",
            "price": product_obj.Price if product_obj else None,
            "special_price": product_obj.SpecialPrice if product_obj else None,
            "plan_type": product_obj.plan_type.value if product_obj and hasattr(product_obj.plan_type, 'value') else (str(product_obj.plan_type) if product_obj else None),
            "category": {
                "id": product_obj.category.id if product_obj and product_obj.category else None,
                "name": product_obj.category.name if product_obj and product_obj.category else None
            } if product_obj else None,
            "images": product_obj.Images if product_obj else None
        }
    
    # Get status history for this order item
    item_status_history = []
    for hist in order.status_history:
        hist_item_id = getattr(hist, 'order_item_id', None)
        if hist_item_id == order_item_id:
            item_status_history.append({
                "status": hist.status.value,
                "previous_status": hist.previous_status.value if hist.previous_status else None,
                "notes": hist.notes,
                "changed_by": hist.changed_by,
                "created_at": hist.created_at.isoformat() if hist.created_at else None,
                "order_item_id": hist_item_id
            })
    
    return {
        "order_id": order.id,
        "order_number": order.order_number,
        "order_item_id": order_item.id,
        "current_status": order_item.order_status.value if hasattr(order_item.order_status, 'value') else str(order_item.order_status),
        "status_history": item_status_history,
        "member": member,
        "address": address,
        "product": product,
        "quantity": order_item.quantity,
        "unit_price": order_item.unit_price,
        "scheduled_date": order_item.scheduled_date.isoformat() if order_item.scheduled_date else None,
        "technician_name": order_item.technician_name,
        "technician_contact": order_item.technician_contact
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
    Status transitions are flexible - can update from any stage to any stage.
    
    Valid statuses: order_confirmed, scheduled, schedule_confirmed_by_lab,
    sample_collected, sample_received_by_lab, testing_in_progress, report_ready
    
    Request body:
    - status: New status to transition to
    - notes: Notes about the status change
    - order_item_id (optional): Update specific order item
    - address_id (optional): Update all items with this address
    - scheduled_date (optional): Scheduled date for technician visit (only needed for statuses like 'scheduled')
    - technician_name (optional): Technician name (only needed for statuses like 'scheduled', 'sample_collected')
    - technician_contact (optional): Technician contact (only needed for statuses like 'scheduled', 'sample_collected')
    
    Note: Technician details (scheduled_date, technician_name, technician_contact) are optional.
    They are typically required for: scheduled, schedule_confirmed_by_lab, sample_collected
    They are NOT needed for: order_confirmed, sample_received_by_lab, testing_in_progress, report_ready
    """
    try:
        # Validate status
        try:
            new_status = OrderStatus(status_data.status)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status: {status_data.status}. Valid statuses: {[s.value for s in OrderStatus]}"
            )
        
        # Verify order exists
        order = get_order_by_id(db, order_id, user_id=current_user.id)
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        # Update status (supports per-item or per-address updates)
        # Status transitions are flexible - no validation of sequential progression
        order = update_order_status(
            db=db,
            order_id=order_id,
            new_status=new_status,
            changed_by=str(current_user.id),
            notes=status_data.notes,
            order_item_id=status_data.order_item_id,
            address_id=status_data.address_id,
            scheduled_date=status_data.scheduled_date,
            technician_name=status_data.technician_name,
            technician_contact=status_data.technician_contact
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

