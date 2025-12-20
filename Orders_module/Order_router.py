"""
Order router - handles order creation, payment, and tracking.
"""
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from typing import List, Optional
from collections import defaultdict
import uuid
import logging
import json

from deps import get_db
from Login_module.Utils.auth_user import get_current_user, get_current_member
from Login_module.User.user_model import User
from Member_module.Member_model import Member
from .Order_schema import (
    CreateOrderRequest,
    OrderResponse,
    RazorpayOrderResponse,
    VerifyPaymentRequest,
    PaymentVerificationResponse,
    UpdateOrderStatusRequest,
    OrderItemTrackingResponse,
    OrderTrackingResponse
)
from .Order_crud import (
    create_order_from_cart,
    verify_and_complete_payment,
    update_order_status,
    get_order_by_id,
    get_user_orders,
    mark_payment_failed_or_cancelled
)
from .razorpay_service import create_razorpay_order, verify_webhook_signature, get_payment_details
from .Order_model import OrderStatus, PaymentStatus, Order
from Cart_module.Cart_model import CartItem

router = APIRouter(prefix="/orders", tags=["Orders"])

logger = logging.getLogger(__name__)


def get_client_info(request: Request):
    """Extract client IP and user agent from request"""
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


def extract_and_validate_group_id(snapshot) -> Optional[str]:
    """
    Extract and validate group_id from order snapshot's cart_item_data.
    
    This function:
    - Extracts group_id from JSON data stored in snapshot
    - Validates that group_id is a valid string (not None, not empty, not wrong type)
    - Returns None if group_id is invalid or missing (for backward compatibility)
    
    Args:
        snapshot: OrderSnapshot object containing cart_item_data JSON
        
    Returns:
        str: Valid group_id if found and valid, None otherwise
    """
    if not snapshot or not snapshot.cart_item_data:
        return None
    
    group_id = snapshot.cart_item_data.get("group_id")
    
    # Validate group_id: must be a non-empty string
    if group_id is None:
        return None
    
    # Ensure it's a string type (handle edge cases where JSON might have wrong type)
    if not isinstance(group_id, str):
        logger.warning(f"Invalid group_id type: {type(group_id)}, expected str. Value: {group_id}")
        return None
    
    # Ensure it's not empty
    if not group_id.strip():
        logger.warning(f"Empty group_id found in snapshot {snapshot.id}")
        return None
    
    return group_id


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
            Address.user_id == current_user.id,
            Address.is_deleted == False
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
        # First, verify order belongs to user BEFORE payment verification (security check)
        order = db.query(Order).filter(Order.id == payment_data.order_id).first()
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Order not found"
            )
        
        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Order does not belong to you"
            )
        
        # Now verify and complete payment
        # Note: verify_and_complete_payment commits the transaction internally
        order = verify_and_complete_payment(
            db=db,
            order_id=payment_data.order_id,
            razorpay_order_id=payment_data.razorpay_order_id,
            razorpay_payment_id=payment_data.razorpay_payment_id,
            razorpay_signature=payment_data.razorpay_signature
        )
        
        # Refresh order to get latest state after payment verification
        db.refresh(order)
        
        # Delete cart items after successful payment
        # Validate order has items before processing
        if not order.items:
            logger.warning(f"Order {order.order_number} has no items, skipping cart deletion")
        else:
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
            payment_status=order.payment_status.value,
            order_status=order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status)
        )
    
    except ValueError as e:
        db.rollback()
        # Get the order to return payment status in error response
        payment_status = "unknown"
        order_status = None
        order_number = None
        
        try:
            order = db.query(Order).filter(Order.id == payment_data.order_id).first()
            if order:
                payment_status = order.payment_status.value if hasattr(order.payment_status, 'value') else str(order.payment_status)
                order_status = order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status)
                order_number = order.order_number
        except Exception as db_error:
            # Log database error but don't fail - use default values
            logger.warning(f"Error fetching order details for error response: {db_error}")
        
        # Return user-friendly error message with payment status
        error_message = str(e)
        payment_failed_indicator = "PAYMENT FAILED"
        
        if "Invalid payment signature" in error_message or "verification failed" in error_message.lower():
            error_message = f"{payment_failed_indicator}: Payment verification failed. Please check your payment details and try again. If the problem persists, please contact support."
            # Ensure payment_status is set to failed if not already
            if payment_status not in ["failed", "FAILED"]:
                payment_status = "failed"
        elif "already failed" in error_message.lower():
            error_message = f"{payment_failed_indicator}: Payment for this order has already failed. Please create a new order to retry payment."
            payment_status = "failed"
        elif "already cancelled" in error_message.lower():
            error_message = f"PAYMENT CANCELLED: Payment for this order was cancelled. Please create a new order to proceed with payment."
            payment_status = "cancelled"
        elif "already completed" in error_message.lower():
            error_message = "Payment for this order has already been completed successfully."
        else:
            # For any other payment-related error, mark as failed
            if payment_status == "unknown" or payment_status not in ["completed", "COMPLETED"]:
                error_message = f"{payment_failed_indicator}: {error_message}"
                payment_status = "failed"
        
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "status": "failed",
                "error": error_message,
                "payment_status": payment_status.upper() if payment_status != "unknown" else "FAILED",
                "order_id": payment_data.order_id,
                "order_number": order_number,
                "order_status": order_status,
                "message": f"Payment verification failed. Payment status: {payment_status.upper() if payment_status != 'unknown' else 'FAILED'}"
            }
        )
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
    current_member: Optional[Member] = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """Get all orders for current user. If a member is selected, shows only orders where that member appears."""
    orders = get_user_orders(db, current_user.id)
    
    result = []
    for order in orders:
        # Filter order items by member if a member is selected
        order_items_to_process = order.items
        if current_member:
            # Only include order items for the selected member
            order_items_to_process = [item for item in order.items if item.member_id == current_member.id]
            # Skip this order if no items match the selected member
            if not order_items_to_process:
                continue
        # Group order items by product AND group_id to distinguish different packs of same product
        # 
        # Why this grouping is needed:
        # - When a user orders multiple packs of the same product (e.g., 2 couple packs),
        #   all items have the same product_id but different group_ids
        # - Without group_id in the key, all members from different packs would be grouped together
        # - With group_id, each pack appears as a separate item in the response
        # 
        # Example: 2 couple packs of product_id=10
        #   - Pack 1: group_id="abc123" → members [1, 2] → separate item
        #   - Pack 2: group_id="xyz789" → members [3, 4] → separate item
        #   Without group_id: all 4 members would appear in one item (incorrect)
        from collections import defaultdict
        grouped_items = defaultdict(list)
        for item in order_items_to_process:
            # Extract and validate group_id from snapshot (optimized: parse JSON once)
            snapshot = item.snapshot if item.snapshot else None
            group_id = extract_and_validate_group_id(snapshot)
            
            # Build group key: product_id + group_id + order_id
            # - product_id: identifies the product
            # - group_id: distinguishes different packs of same product (from cart grouping)
            # - order_id: ensures uniqueness across orders
            # 
            # Fallback behavior: If group_id is None (old orders or invalid data),
            # group by product_id only. This maintains backward compatibility.
            if group_id:
                group_key = f"{item.product_id}_{group_id}_{item.order_id}"
            else:
                # Backward compatibility: old orders created before group_id was implemented
                group_key = f"{item.product_id}_{item.order_id}"
            grouped_items[group_key].append(item)
        
        order_items = []
        for group_key, items in grouped_items.items():
            # Use first item as representative for product info
            # All items in this group share the same product and group_id
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
            
            # Extract group_id (already validated during grouping, reuse for response)
            # This avoids re-parsing JSON - group_id was already extracted above
            group_id = extract_and_validate_group_id(snapshot)
            
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
            
            # Calculate total_amount: price is per product group, not per member
            # For couple/family products, there are multiple order items but price is calculated once per product
            # This matches the cart calculation logic: quantity * unit_price (per product, not per member)
            item_total_amount = first_item.quantity * first_item.unit_price
            
            order_items.append({
                "product_id": product_id,
                "product_name": product_name,
                "group_id": group_id,  # Group ID to distinguish different packs of same product
                "member_ids": list(set(member_ids)),
                "address_ids": unique_address_ids,
                "member_address_map": member_address_map,  # Full details with member-address mapping
                "quantity": first_item.quantity,
                "total_amount": item_total_amount
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
            "created_at": order.created_at.isoformat() if order.created_at else None,
            "items": order_items
        })
    
    return result


# @router.get("/tracking", response_model=List[OrderTrackingResponse])
# def get_all_orders_tracking(
#     request: Request,
#     current_user: User = Depends(get_current_user),
#     db: Session = Depends(get_db)
# ):
#     """
#     Get comprehensive tracking information for all orders of the current user.
#     Returns detailed order information including pricing, product/plan breakdown, 
#     address-wise tracking, and member details. Clearly indicates current vs past orders.
#     """
#     from .Order_schema import OrderItemTracking, MemberDetails, AddressDetails
#     from .Order_model import OrderStatus
#     
#     orders = get_user_orders(db, current_user.id)
#     
#     result = []
#     for order in orders:
#         # Build order items list - clean mapping of member, address, product, and status
#         order_items_list = []
#         
#         for item in order.items:
#             snapshot = item.snapshot if item.snapshot else None
#             
#             # Get product details
#             if snapshot and snapshot.product_data:
#                 product_data = snapshot.product_data
#                 product_id = product_data.get("ProductId", item.product_id)
#                 product_name = product_data.get("Name", "Unknown Product")
#                 plan_type = product_data.get("plan_type", None)
#                 unit_price = item.unit_price
#             else:
#                 product_obj = item.product
#                 product_id = product_obj.ProductId if product_obj else item.product_id
#                 product_name = product_obj.Name if product_obj else "Unknown Product"
#                 plan_type = product_obj.plan_type.value if product_obj and hasattr(product_obj.plan_type, 'value') else (str(product_obj.plan_type) if product_obj else None)
#                 unit_price = item.unit_price
#             
#             quantity = item.quantity
#             
#             # Extract and validate group_id from snapshot (optimized: parse JSON once per item)
#             # group_id distinguishes different packs of the same product
#             group_id = extract_and_validate_group_id(snapshot)
#             
#             # Get member details
#             if snapshot and snapshot.member_data:
#                 member_data = snapshot.member_data
#                 member = MemberDetails(
#                     member_id=member_data.get("id", item.member_id),
#                     name=member_data.get("name", "Unknown"),
#                     relation=member_data.get("relation"),
#                     age=member_data.get("age"),
#                     gender=member_data.get("gender"),
#                     dob=member_data.get("dob"),
#                     mobile=member_data.get("mobile")
#                 )
#             else:
#                 member_obj = item.member
#                 relation_val = None
#                 if member_obj:
#                     if hasattr(member_obj.relation, 'value'):
#                         relation_val = member_obj.relation.value
#                     else:
#                         relation_val = str(member_obj.relation) if member_obj.relation else None
#                 
#                 member = MemberDetails(
#                     member_id=member_obj.id if member_obj else item.member_id,
#                     name=member_obj.name if member_obj else "Unknown",
#                     relation=relation_val,
#                     age=member_obj.age if member_obj else None,
#                     gender=member_obj.gender if member_obj else None,
#                     dob=member_obj.dob.isoformat() if member_obj and member_obj.dob else None,
#                     mobile=member_obj.mobile if member_obj else None
#                 )
#             
#             # Get address details
#             if snapshot and snapshot.address_data:
#                 address_data = snapshot.address_data
#                 address = AddressDetails(
#                     address_id=address_data.get("id", item.address_id),
#                     address_label=address_data.get("address_label"),
#                     street_address=address_data.get("street_address"),
#                     landmark=address_data.get("landmark"),
#                     locality=address_data.get("locality"),
#                     city=address_data.get("city"),
#                     state=address_data.get("state"),
#                     postal_code=address_data.get("postal_code"),
#                     country=address_data.get("country")
#                 )
#             else:
#                 address_obj = item.address
#                 address = AddressDetails(
#                     address_id=address_obj.id if address_obj else item.address_id,
#                     address_label=address_obj.address_label if address_obj else None,
#                     street_address=address_obj.street_address if address_obj else None,
#                     landmark=address_obj.landmark if address_obj else None,
#                     locality=address_obj.locality if address_obj else None,
#                     city=address_obj.city if address_obj else None,
#                     state=address_obj.state if address_obj else None,
#                     postal_code=address_obj.postal_code if address_obj else None,
#                     country=address_obj.country if address_obj else None
#                 )
#             
#             # Get current and previous status
#             current_status = item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status)
#             previous_status = None
#             
#             # Get status history for this order item
#             item_status_history = []
#             for hist in order.status_history:
#                 if hist.order_item_id == item.id:
#                     item_status_history.append({
#                         "status": hist.status.value,
#                         "previous_status": hist.previous_status.value if hist.previous_status else None,
#                         "notes": hist.notes,
#                         "created_at": hist.created_at.isoformat() if hist.created_at else None
#                     })
#             
#             # Sort status history by created_at (most recent first) for display
#             item_status_history.sort(key=lambda x: x.get("created_at") or "", reverse=True)
#             
#             # Get previous status from the most recent history entry (which contains previous_status)
#             if item_status_history:
#                 previous_status = item_status_history[0].get("previous_status")
#             
#             order_items_list.append(OrderItemTracking(
#                 order_item_id=item.id,
#                 product_id=product_id,
#                 product_name=product_name,
#                 plan_type=str(plan_type).lower() if plan_type else None,
#                 group_id=group_id,  # Group ID to distinguish different packs of same product
#                 quantity=quantity,
#                 unit_price=unit_price,
#                 member=member,
#                 address=address,
#                 current_status=current_status,
#                 previous_status=previous_status,
#                 status_updated_at=item.status_updated_at,
#                 scheduled_date=item.scheduled_date,
#                 technician_name=item.technician_name,
#                 technician_contact=item.technician_contact,
#                 created_at=item.created_at,
#                 status_history=item_status_history
#             ))
#         
#         # Sort order items by product_id to group related items together
#         order_items_list.sort(key=lambda x: (x.product_id or 0, x.order_item_id))
#         
#         # Calculate product discount (difference between subtotal and sum of unit prices)
#         # This represents the discount from product pricing (Price - SpecialPrice)
#         # Sum unique products (since items with same product_id share the same price)
#         seen_products = set()
#         total_product_prices = 0.0
#         for item in order_items_list:
#             product_key = item.product_id
#             if product_key and product_key not in seen_products:
#                 total_product_prices += item.quantity * item.unit_price
#                 seen_products.add(product_key)
#         
#         product_discount = max(0.0, total_product_prices - order.subtotal) if order.subtotal else None
#         
#         result.append(OrderTrackingResponse(
#             order_id=order.id,
#             order_number=order.order_number,
#             order_date=order.created_at,
#             payment_status=order.payment_status.value,
#             current_status=order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status),
#             subtotal=order.subtotal,
#             product_discount=product_discount,
#             coupon_code=order.coupon_code,
#             coupon_discount=order.coupon_discount,
#             delivery_charge=order.delivery_charge,
#             total_amount=order.total_amount,
#             order_items=order_items_list
#         ))
#     
#     return result


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Optional[Member] = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Get order details by ID. If a member is selected, shows only order items for that member.
    Allows viewing orders with any payment status (pending/failed/completed) so users can check their order status.
    """
    # Allow viewing orders with any payment status so users can see pending/failed orders
    order = get_order_by_id(db, order_id, user_id=current_user.id, include_all_payment_statuses=True)
    
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Filter order items by member if a member is selected
    order_items_to_process = order.items
    if current_member:
        order_items_to_process = [item for item in order.items if item.member_id == current_member.id]
        if not order_items_to_process:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No order items found for the selected member in this order"
            )
    
    # Group order items by product AND group_id to distinguish different packs of same product
    # 
    # Why this grouping is needed:
    # - When a user orders multiple packs of the same product (e.g., 2 couple packs),
    #   all items have the same product_id but different group_ids
    # - Without group_id in the key, all members from different packs would be grouped together
    # - With group_id, each pack appears as a separate item in the response
    # 
    # Example: 2 couple packs of product_id=10
    #   - Pack 1: group_id="abc123" → members [1, 2] → separate item
    #   - Pack 2: group_id="xyz789" → members [3, 4] → separate item
    #   Without group_id: all 4 members would appear in one item (incorrect)
    from collections import defaultdict
    grouped_items = defaultdict(list)
    for item in order_items_to_process:
        # Extract and validate group_id from snapshot (optimized: parse JSON once)
        snapshot = item.snapshot if item.snapshot else None
        group_id = extract_and_validate_group_id(snapshot)
        
        # Build group key: product_id + group_id + order_id
        # - product_id: identifies the product
        # - group_id: distinguishes different packs of same product (from cart grouping)
        # - order_id: ensures uniqueness across orders
        # 
        # Fallback behavior: If group_id is None (old orders or invalid data),
        # group by product_id only. This maintains backward compatibility.
        if group_id:
            group_key = f"{item.product_id}_{group_id}_{order.id}"
        else:
            # Backward compatibility: old orders created before group_id was implemented
            group_key = f"{item.product_id}_{order.id}"
        grouped_items[group_key].append(item)
    
    order_items = []
    for group_key, items in grouped_items.items():
        # Use first item as representative for product info
        # All items in this group share the same product and group_id
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
        
        # Extract group_id (already validated during grouping, reuse for response)
        # This avoids re-parsing JSON - group_id was already extracted above
        group_id = extract_and_validate_group_id(snapshot)
        
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
        
        # Calculate total_amount: price is per product group, not per member
        # For couple/family products, there are multiple order items but price is calculated once per product
        # This matches the cart calculation logic: quantity * unit_price (per product, not per member)
        item_total_amount = first_item.quantity * first_item.unit_price
        
        order_items.append({
            "product_id": product_id,
            "product_name": product_name,
            "group_id": group_id,  # Group ID to distinguish different packs of same product
            "member_ids": list(set(member_ids)),
            "address_ids": unique_address_ids,
            "member_address_map": member_address_map,  # Full details with member-address mapping
            "quantity": first_item.quantity,
            "total_amount": item_total_amount
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
    current_member: Optional[Member] = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Get order tracking information for a specific order.
    If a member is selected, shows only order items for that member.
    Returns comprehensive order details with order items grouped by product.
    """
    from .Order_schema import OrderItemTracking, MemberDetails, AddressDetails
    from .Order_model import OrderStatus
    
    # Verify order exists and belongs to user
    order = get_order_by_id(db, order_id, user_id=current_user.id)
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found"
        )
    
    # Filter order items by member if a member is selected
    order_items_to_process = order.items
    if current_member:
        order_items_to_process = [item for item in order.items if item.member_id == current_member.id]
        if not order_items_to_process:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No order items found for the selected member in this order"
            )
    
    # Build order items list - clean mapping of member, address, product, and status
    order_items_list = []
    
    for item in order_items_to_process:
        snapshot = item.snapshot if item.snapshot else None
        
        # Get product details
        if snapshot and snapshot.product_data:
            product_data = snapshot.product_data
            product_id = product_data.get("ProductId", item.product_id)
            product_name = product_data.get("Name", "Unknown Product")
            plan_type = product_data.get("plan_type", None)
            unit_price = item.unit_price
        else:
            product_obj = item.product
            product_id = product_obj.ProductId if product_obj else item.product_id
            product_name = product_obj.Name if product_obj else "Unknown Product"
            plan_type = product_obj.plan_type.value if product_obj and hasattr(product_obj.plan_type, 'value') else (str(product_obj.plan_type) if product_obj else None)
            unit_price = item.unit_price
        
        quantity = item.quantity
        
        # Extract and validate group_id from snapshot (optimized: parse JSON once per item)
        # group_id distinguishes different packs of the same product
        group_id = extract_and_validate_group_id(snapshot)
        
        # Get member details
        if snapshot and snapshot.member_data:
            member_data = snapshot.member_data
            member = MemberDetails(
                member_id=member_data.get("id", item.member_id),
                name=member_data.get("name", "Unknown"),
                relation=member_data.get("relation"),
                age=member_data.get("age"),
                gender=member_data.get("gender"),
                dob=member_data.get("dob"),
                mobile=member_data.get("mobile")
            )
        else:
            member_obj = item.member
            relation_val = None
            if member_obj:
                if hasattr(member_obj.relation, 'value'):
                    relation_val = member_obj.relation.value
                else:
                    relation_val = str(member_obj.relation) if member_obj.relation else None
            
            member = MemberDetails(
                member_id=member_obj.id if member_obj else item.member_id,
                name=member_obj.name if member_obj else "Unknown",
                relation=relation_val,
                age=member_obj.age if member_obj else None,
                gender=member_obj.gender if member_obj else None,
                dob=member_obj.dob.isoformat() if member_obj and member_obj.dob else None,
                mobile=member_obj.mobile if member_obj else None
            )
        
        # Get address details
        if snapshot and snapshot.address_data:
            address_data = snapshot.address_data
            address = AddressDetails(
                address_id=address_data.get("id", item.address_id),
                address_label=address_data.get("address_label"),
                street_address=address_data.get("street_address"),
                landmark=address_data.get("landmark"),
                locality=address_data.get("locality"),
                city=address_data.get("city"),
                state=address_data.get("state"),
                postal_code=address_data.get("postal_code"),
                country=address_data.get("country")
            )
        else:
            address_obj = item.address
            address = AddressDetails(
                address_id=address_obj.id if address_obj else item.address_id,
                address_label=address_obj.address_label if address_obj else None,
                street_address=address_obj.street_address if address_obj else None,
                landmark=address_obj.landmark if address_obj else None,
                locality=address_obj.locality if address_obj else None,
                city=address_obj.city if address_obj else None,
                state=address_obj.state if address_obj else None,
                postal_code=address_obj.postal_code if address_obj else None,
                country=address_obj.country if address_obj else None
            )
        
        # Get current and previous status
        current_status = item.order_status.value if hasattr(item.order_status, 'value') else str(item.order_status)
        previous_status = None
        
        # Get status history for this order item
        item_status_history = []
        for hist in order.status_history:
            if hist.order_item_id == item.id:
                item_status_history.append({
                    "status": hist.status.value,
                    "previous_status": hist.previous_status.value if hist.previous_status else None,
                    "notes": hist.notes,
                    "created_at": hist.created_at.isoformat() if hist.created_at else None
                })
        
        # Sort status history by created_at (most recent first) for display
        item_status_history.sort(key=lambda x: x.get("created_at") or "", reverse=True)
        
        # Get previous status from the most recent history entry (which contains previous_status)
        if item_status_history:
            previous_status = item_status_history[0].get("previous_status")
        
        order_items_list.append(OrderItemTracking(
            order_item_id=item.id,
            product_id=product_id,
            product_name=product_name,
            plan_type=str(plan_type).lower() if plan_type else None,
            group_id=group_id,  # Group ID to distinguish different packs of same product
            quantity=quantity,
            unit_price=unit_price,
            member=member,
            address=address,
            current_status=current_status,
            previous_status=previous_status,
            status_updated_at=item.status_updated_at.isoformat() if item.status_updated_at else None,
            scheduled_date=item.scheduled_date.isoformat() if item.scheduled_date else None,
            technician_name=item.technician_name,
            technician_contact=item.technician_contact,
            created_at=item.created_at.isoformat() if item.created_at else None,
            status_history=item_status_history
        ))
    
    # Sort order items by product_id to group related items together
    order_items_list.sort(key=lambda x: (x.product_id or 0, x.order_item_id))
    
    # Calculate product discount (difference between subtotal and sum of unit prices)
    # Sum unique products (since items with same product_id share the same price)
    seen_products = set()
    total_product_prices = 0.0
    for item in order_items_list:
        product_key = item.product_id
        if product_key and product_key not in seen_products:
            total_product_prices += item.quantity * item.unit_price
            seen_products.add(product_key)
    
    product_discount = max(0.0, total_product_prices - order.subtotal) if order.subtotal else None
    
    return OrderTrackingResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_date=order.created_at.isoformat() if order.created_at else None,
        payment_status=order.payment_status.value,
        current_status=order.order_status.value if hasattr(order.order_status, 'value') else str(order.order_status),
        subtotal=order.subtotal,
        product_discount=product_discount,
        coupon_code=order.coupon_code,
        coupon_discount=order.coupon_discount,
        delivery_charge=order.delivery_charge,
        total_amount=order.total_amount,
        order_items=order_items_list
    )


@router.get("/{order_id}/{order_item_id}/tracking", response_model=OrderItemTrackingResponse)
def get_order_item_tracking(
    order_id: int,
    order_item_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    current_member: Optional[Member] = Depends(get_current_member),
    db: Session = Depends(get_db)
):
    """
    Get tracking information for a specific order item.
    If a member is selected, verifies the order item belongs to that member.
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
    query = db.query(OrderItem).filter(
        OrderItem.id == order_item_id,
        OrderItem.order_id == order_id,
        OrderItem.user_id == current_user.id
    )
    
    # Filter by member if a member is selected
    if current_member:
        query = query.filter(OrderItem.member_id == current_member.id)
    
    order_item = query.first()
    
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
                "created_at": hist.created_at.isoformat() if hist.created_at else None
            })
    
    # Sort status history by created_at (most recent first) for display
    item_status_history.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    
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
    
    Valid statuses: pending_payment, order_confirmed, scheduled, schedule_confirmed_by_lab,
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
    They are NOT needed for: pending_payment, order_confirmed, sample_received_by_lab, testing_in_progress, report_ready
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


@router.post("/webhook")
async def razorpay_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Razorpay webhook endpoint to handle payment events.
    
    This endpoint:
    - Verifies webhook signature from Razorpay
    - Handles payment events (payment.captured, payment.failed, etc.)
    - Updates order status based on payment events
    - Does NOT require authentication (Razorpay calls this directly)
    
    Webhook events handled:
    - payment.captured: Payment successful, update order to confirmed
    - payment.failed: Payment failed, mark order as failed
    - payment.authorized: Payment authorized (for manual capture)
    - order.paid: Order paid (alternative event for successful payment)
    """
    try:
        # Get raw request body for signature verification
        body_bytes = await request.body()
        body_str = body_bytes.decode('utf-8')
        
        # Get webhook signature from headers
        webhook_signature = request.headers.get("X-Razorpay-Signature")
        if not webhook_signature:
            logger.warning("Webhook request missing X-Razorpay-Signature header")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing webhook signature"
            )
        
        # Verify webhook signature
        if not verify_webhook_signature(body_str, webhook_signature):
            logger.warning("Invalid webhook signature")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature"
            )
        
        # Parse webhook payload
        webhook_data = json.loads(body_str)
        event = webhook_data.get("event")
        payload = webhook_data.get("payload", {})
        
        logger.info(f"Received Razorpay webhook event: {event}")
        
        # Handle different webhook events
        if event == "payment.captured":
            # Payment successful
            payment_entity = payload.get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            order_id_razorpay = payment_entity.get("order_id")
            
            if not payment_id or not order_id_razorpay:
                logger.error(f"Missing payment_id or order_id in payment.captured webhook: {webhook_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing payment_id or order_id in webhook payload"
                )
            
            # Find order by razorpay_order_id
            order = db.query(Order).filter(Order.razorpay_order_id == order_id_razorpay).first()
            if not order:
                logger.warning(f"Order not found for Razorpay order ID: {order_id_razorpay}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            
            # Only process if payment is not already completed
            if order.payment_status == PaymentStatus.COMPLETED:
                logger.info(f"Payment already completed for order {order.order_number}, ignoring webhook")
                return {"status": "success", "message": "Payment already processed"}
            
            # Get payment details from Razorpay to get signature
            payment_details = get_payment_details(payment_id)
            if not payment_details:
                logger.error(f"Could not fetch payment details from Razorpay for payment_id: {payment_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not fetch payment details"
                )
            
            # Extract signature from payment details (if available)
            razorpay_signature = payment_details.get("signature")
            if not razorpay_signature:
                logger.warning(f"No signature in payment details for payment_id: {payment_id}, proceeding without signature verification")
            
            # Verify and complete payment
            try:
                order = verify_and_complete_payment(
                    db=db,
                    order_id=order.id,
                    razorpay_order_id=order_id_razorpay,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=razorpay_signature or ""  # Use empty string if signature not available
                )
                logger.info(f"Payment completed via webhook for order {order.order_number}")
                
                # Note: Cart deletion is handled in verify_payment endpoint, not in webhook
                # Webhook is for server-side updates, cart deletion happens on client-side verify-payment call
                
                return {
                    "status": "success",
                    "message": "Payment processed successfully",
                    "order_id": order.id,
                    "order_number": order.order_number
                }
            except ValueError as e:
                # Payment verification failed or already processed
                logger.warning(f"Payment verification failed for order {order.order_number}: {str(e)}")
                return {
                    "status": "warning",
                    "message": str(e),
                    "order_id": order.id,
                    "order_number": order.order_number
                }
        
        elif event == "payment.failed":
            # Payment failed
            payment_entity = payload.get("payment", {}).get("entity", {})
            payment_id = payment_entity.get("id")
            order_id_razorpay = payment_entity.get("order_id")
            error_description = payment_entity.get("error_description", "Payment failed")
            
            if not order_id_razorpay:
                logger.error(f"Missing order_id in payment.failed webhook: {webhook_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing order_id in webhook payload"
                )
            
            # Find order by razorpay_order_id
            order = db.query(Order).filter(Order.razorpay_order_id == order_id_razorpay).first()
            if not order:
                logger.warning(f"Order not found for Razorpay order ID: {order_id_razorpay}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            
            # Only process if payment is not already completed
            if order.payment_status == PaymentStatus.COMPLETED:
                logger.info(f"Payment already completed for order {order.order_number}, ignoring failure webhook")
                return {"status": "success", "message": "Payment already processed"}
            
            # Mark payment as failed
            try:
                order = mark_payment_failed_or_cancelled(
                    db=db,
                    order_id=order.id,
                    payment_status=PaymentStatus.FAILED,
                    reason=f"Payment failed via webhook: {error_description}"
                )
                logger.info(f"Payment marked as failed via webhook for order {order.order_number}")
                
                return {
                    "status": "success",
                    "message": "Payment failure processed",
                    "order_id": order.id,
                    "order_number": order.order_number
                }
            except ValueError as e:
                logger.warning(f"Could not mark payment as failed for order {order.order_number}: {str(e)}")
                return {
                    "status": "warning",
                    "message": str(e),
                    "order_id": order.id,
                    "order_number": order.order_number
                }
        
        elif event == "order.paid":
            # Alternative event for successful payment (when order is paid)
            order_entity = payload.get("order", {}).get("entity", {})
            order_id_razorpay = order_entity.get("id")
            
            if not order_id_razorpay:
                logger.error(f"Missing order_id in order.paid webhook: {webhook_data}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Missing order_id in webhook payload"
                )
            
            # Find order by razorpay_order_id
            order = db.query(Order).filter(Order.razorpay_order_id == order_id_razorpay).first()
            if not order:
                logger.warning(f"Order not found for Razorpay order ID: {order_id_razorpay}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Order not found"
                )
            
            # Get payment ID from order entity
            payments = order_entity.get("payments", [])
            if not payments:
                logger.warning(f"No payments found in order.paid webhook for order {order.order_number}")
                return {
                    "status": "warning",
                    "message": "No payment ID found in webhook",
                    "order_id": order.id,
                    "order_number": order.order_number
                }
            
            payment_id = payments[0]  # Use first payment
            
            # Only process if payment is not already completed
            if order.payment_status == PaymentStatus.COMPLETED:
                logger.info(f"Payment already completed for order {order.order_number}, ignoring webhook")
                return {"status": "success", "message": "Payment already processed"}
            
            # Get payment details to get signature
            payment_details = get_payment_details(payment_id)
            if not payment_details:
                logger.error(f"Could not fetch payment details from Razorpay for payment_id: {payment_id}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Could not fetch payment details"
                )
            
            razorpay_signature = payment_details.get("signature", "")
            
            # Verify and complete payment
            try:
                order = verify_and_complete_payment(
                    db=db,
                    order_id=order.id,
                    razorpay_order_id=order_id_razorpay,
                    razorpay_payment_id=payment_id,
                    razorpay_signature=razorpay_signature or ""
                )
                logger.info(f"Payment completed via order.paid webhook for order {order.order_number}")
                
                return {
                    "status": "success",
                    "message": "Payment processed successfully",
                    "order_id": order.id,
                    "order_number": order.order_number
                }
            except ValueError as e:
                logger.warning(f"Payment verification failed for order {order.order_number}: {str(e)}")
                return {
                    "status": "warning",
                    "message": str(e),
                    "order_id": order.id,
                    "order_number": order.order_number
                }
        
        else:
            # Unhandled event - log but don't fail
            logger.info(f"Unhandled webhook event: {event}, ignoring")
            return {
                "status": "success",
                "message": f"Event {event} received but not processed"
            }
    
    except HTTPException:
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in webhook payload: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing webhook: {str(e)}"
        )

