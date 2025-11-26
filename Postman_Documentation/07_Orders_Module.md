# Postman Testing Documentation - Orders Module

## Base URL
```
http://localhost:8000/orders
```

## Overview
This module handles order creation, payment verification, order tracking, and status management. Orders are created from cart items and require Razorpay payment integration. If a coupon is applied to the cart, the coupon discount is automatically included in the order total. The coupon is removed from the cart after successful payment verification.

---

## Endpoint 1: Create Order

### Details
- **Method:** `POST`
- **Endpoint:** `/orders/create`
- **Description:** Create order from cart items. Creates Razorpay order for payment. No COD option - payment must be completed online.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body
```json
{
  "address_id": null,
  "cart_item_ids": [1, 2, 3]
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| address_id | integer | No | Optional shipping address ID. When omitted, the address from the selected cart items is used. | 1 |
| cart_item_ids | array | Yes | List of cart item IDs to order | [1, 2, 3] |

### Success Response (200 OK) - Without Coupon
```json
{
  "razorpay_order_id": "order_MN1234567890",
  "amount": 16050.00,
  "currency": "INR",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001"
}
```

### Success Response (200 OK) - With Coupon Applied
```json
{
  "razorpay_order_id": "order_MN1234567890",
  "amount": 15050.00,
  "currency": "INR",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001"
}
```
*Note: Amount is reduced by coupon discount (₹1000.00 in this example)*

### Error Responses

#### 404 Not Found - Cart Items Not Found
```json
{
  "detail": "One or more cart items not found"
}
```

#### 422 Unprocessable Entity - Invalid Request
```json
{
  "detail": "Cart is empty or invalid"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Prerequisites:
   - Valid access token
   - Items in cart (use Cart module)
   - (Optional) address_id if you want to override the addresses stored on cart items
2. Create a new POST request in Postman
3. Set URL to: `http://localhost:8000/orders/create`
4. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
5. In Body tab, select "raw" and "JSON"
6. Paste the request body with cart_item_ids from your cart
7. Click "Send"
8. **IMPORTANT:** Save `razorpay_order_id` and `order_id` from response for payment verification

### Prerequisites
- Valid access token
- Items in cart (use Cart module "View Cart" to get cart_item_ids)
- Optional address_id (use Address module) if you need to force a different shipping address

- Creates a Razorpay order for payment
- Order is created with status "order_confirmed" (after payment)
- Cart items are not removed until payment is verified
- **Coupon discount is automatically included** if a coupon is applied to the cart
- Amount calculation: `subtotal + delivery_charge - coupon_discount - discount`
- Amount includes delivery charge (50.00) and excludes coupon discount if applied
- Each order item keeps its own address from the cart; the top-level `address_id` is used as the primary shipping address (defaults to the cart item's address when only one exists)
- **For couple/family packs with different addresses**: Each order item has its own status tracking, allowing independent tracking per address
- **Coupon is removed from cart** after successful payment verification

---

## Endpoint 2: Verify Payment

### Details
- **Method:** `POST`
- **Endpoint:** `/orders/verify-payment`
- **Description:** Verify Razorpay payment and complete order. Removes cart items after successful payment.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body
```json
{
  "order_id": 1,
  "razorpay_order_id": "order_MN1234567890",
  "razorpay_payment_id": "pay_MN1234567890",
  "razorpay_signature": "abc123def456..."
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| order_id | integer | Yes | Order ID from create order response | 1 |
| razorpay_order_id | string | Yes | Razorpay order ID from create order | "order_MN1234567890" |
| razorpay_payment_id | string | Yes | Razorpay payment ID from payment gateway | "pay_MN1234567890" |
| razorpay_signature | string | Yes | Razorpay signature for verification | "abc123def456..." |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Payment verified successfully. Order confirmed.",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "payment_status": "completed"
}
```

### Notes
- Cart items are removed after successful payment verification
- **Applied coupon is removed from cart** after successful payment verification
- Order payment status is updated to "completed"
- Order is now confirmed and ready for processing

### Error Responses

#### 422 Unprocessable Entity - Invalid Signature
```json
{
  "detail": "Invalid payment signature"
}
```

#### 422 Unprocessable Entity - Payment Verification Failed
```json
{
  "detail": "Payment verification failed"
}
```

#### 403 Forbidden - Order Not Belongs to User
```json
{
  "detail": "Order does not belong to you"
}
```

#### 404 Not Found - Order Not Found
```json
{
  "detail": "Order not found"
}
```

### Testing Steps
1. First, create an order using "Create Order" endpoint
2. Complete payment on Razorpay (frontend integration)
3. Get payment details from Razorpay response:
   - razorpay_payment_id
   - razorpay_signature
4. Create a new POST request in Postman
5. Set URL to: `http://localhost:8000/orders/verify-payment`
6. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
7. In Body tab, select "raw" and "JSON"
8. Paste the request body with all payment details
9. Click "Send"
10. Verify order status is updated to "paid" and cart items are removed

### Prerequisites
- Valid access token
- Order created (from "Create Order" endpoint)

- Payment completed on Razorpay
- Valid payment signature from Razorpay

### Notes
- Payment signature is verified for security
- Cart items are automatically removed after successful payment
- Order status changes to "order_confirmed" after payment
- This endpoint should be called from frontend after Razorpay payment success

---

## Endpoint 3: Get Order List

### Details
- **Method:** `GET`
- **Endpoint:** `/orders/list`
- **Description:** Get all orders for current user.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK) - With Orders (No Coupon)
```json
[
  {
    "order_id": 1,
    "order_number": "ORD-2025-11-24-001",
    "user_id": 1,
    "address_id": 1,
    "subtotal": 16000.00,
    "discount": 0.00,
    "coupon_code": null,
    "coupon_discount": 0.00,
    "delivery_charge": 50.00,
    "total_amount": 16050.00,
    "payment_status": "completed",
    "order_status": "order_confirmed",
    "razorpay_order_id": "order_MN1234567890",
    "created_at": "2025-11-24T10:00:00",
    "items": [
      {
        "order_item_id": 1,
        "product_id": 2,
        "product_name": "DNA Test Kit - Couple",
        "member_id": 1,
        "member_name": "John Doe",
        "address_id": 5,
        "address_label": "Home",
        "address_details": {
          "address_label": "Home",
          "street_address": "123 Main St",
          "locality": "Whitefield",
          "city": "Bangalore",
          "state": "Karnataka",
          "postal_code": "560066"
        },
        "quantity": 1,
        "unit_price": 8000.00,
        "total_price": 8000.00,
        "order_status": "order_confirmed",
        "status_updated_at": "2025-11-24T10:00:00"
      },
      {
        "order_item_id": 2,
        "product_id": 2,
        "product_name": "DNA Test Kit - Couple",
        "member_id": 2,
        "member_name": "Jane Doe",
        "address_id": 6,
        "address_label": "Parents House",
        "address_details": {
          "address_label": "Parents House",
          "street_address": "456 Park Ave",
          "locality": "Koramangala",
          "city": "Bangalore",
          "state": "Karnataka",
          "postal_code": "560095"
        },
        "quantity": 1,
        "unit_price": 8000.00,
        "total_price": 8000.00,
        "order_status": "order_confirmed",
        "status_updated_at": "2025-11-24T10:00:00"
      }
    ]
  }
]
```

### Success Response (200 OK) - Empty List
```json
[]
```

### Error Responses

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Create a new GET request in Postman
2. Set URL to: `http://localhost:8000/orders/list`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains all your orders

### Prerequisites
- Valid access token

### Notes
- Returns all orders for the current user
- Returns empty array if no orders exist
- Orders include full item details with product and member information
- Each order item shows its own `order_status` for per-address tracking
- For couple/family packs with different addresses, each item can have different status

---

## Endpoint 4: Get Order by ID

### Details
- **Method:** `GET`
- **Endpoint:** `/orders/{order_id}`
- **Description:** Get order details by ID.

### Headers
```
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| order_id | integer | Yes | Order ID | 1 |

### Request Body
```
(No body required)
```

### Success Response (200 OK) - Without Coupon
```json
{
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "user_id": 1,
  "address_id": 1,
  "subtotal": 16000.00,
  "discount": 0.00,
  "coupon_code": null,
  "coupon_discount": 0.00,
  "delivery_charge": 50.00,
  "total_amount": 16050.00,
  "payment_status": "completed",
  "order_status": "order_confirmed",
  "razorpay_order_id": "order_MN1234567890",
  "created_at": "2025-11-24T10:00:00",
  "items": [
      {
        "order_item_id": 1,
        "product_id": 2,
        "product_name": "DNA Test Kit - Couple",
        "member_id": 1,
        "member_name": "John Doe",
        "address_id": 5,
        "address_label": "Home",
        "address_details": {
          "address_label": "Home",
          "street_address": "123 Main St",
          "locality": "Whitefield",
          "city": "Bangalore",
          "state": "Karnataka",
          "postal_code": "560066"
        },
        "quantity": 1,
        "unit_price": 8000.00,
        "total_price": 8000.00,
        "order_status": "order_confirmed",
        "status_updated_at": "2025-11-24T10:00:00"
      }
  ]
}
```

### Error Responses

#### 404 Not Found - Order Not Found
```json
{
  "detail": "Order not found"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Ensure you have an order (use "Create Order" or "Get Order List")
2. Create a new GET request in Postman
3. Set URL to: `http://localhost:8000/orders/1`
   - Replace `1` with your actual order_id
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify the response contains order details

### Prerequisites
- Valid access token
- Order must exist and belong to the user

### Notes
- Returns detailed information about a specific order
- Includes all order items with product and member details
- Order response includes `subtotal`, `discount`, `coupon_code`, `coupon_discount`, and `delivery_charge` fields
- If a coupon was applied when order was created, `coupon_code` and `coupon_discount` will show the applied coupon details

---

## Endpoint 5: Get Order Tracking

### Details
- **Method:** `GET`
- **Endpoint:** `/orders/{order_id}/tracking`
- **Description:** Get order tracking information with status history.

### Headers
```
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| order_id | integer | Yes | Order ID | 1 |

### Request Body
```
(No body required)
```

### Success Response (200 OK) - Single Address Order
```json
{
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "current_status": "order_confirmed",
  "status_history": [
    {
      "status": "order_confirmed",
      "previous_status": null,
      "notes": "Order created from cart",
      "changed_by": "1",
      "created_at": "2025-11-24T10:00:00",
      "order_item_id": null
    }
  ],
  "estimated_completion": null,
  "address_tracking": [
    {
      "address_id": 5,
      "address_label": "Home",
      "address_details": {
        "address_label": "Home",
        "street_address": "123 Main St",
        "locality": "Whitefield",
        "city": "Bangalore",
        "state": "Karnataka",
        "postal_code": "560066"
      },
      "members": [
        {
          "member_id": 1,
          "member_name": "John Doe",
          "order_item_id": 1,
          "order_status": "order_confirmed"
        }
      ],
      "current_status": "order_confirmed",
      "status_history": [
        {
          "status": "order_confirmed",
          "previous_status": null,
          "notes": "Order item created for member John Doe at address Home",
          "changed_by": "1",
          "created_at": "2025-11-24T10:00:00",
          "order_item_id": 1,
          "member_name": "John Doe"
        }
      ],
      "estimated_completion": null
    }
  ]
}
```

### Success Response (200 OK) - Multiple Addresses (Couple/Family Pack)
```json
{
  "order_id": 2,
  "order_number": "ORD-2025-11-24-002",
  "current_status": "scheduled",
  "status_history": [
    {
      "status": "order_confirmed",
      "previous_status": null,
      "notes": "Order created from cart",
      "changed_by": "1",
      "created_at": "2025-11-24T10:00:00",
      "order_item_id": null
    }
  ],
  "estimated_completion": "2025-12-01T10:00:00",
  "address_tracking": [
    {
      "address_id": 5,
      "address_label": "Home",
      "address_details": {
        "address_label": "Home",
        "street_address": "123 Main St",
        "locality": "Whitefield",
        "city": "Bangalore",
        "state": "Karnataka",
        "postal_code": "560066"
      },
      "members": [
        {
          "member_id": 1,
          "member_name": "John Doe",
          "order_item_id": 3,
          "order_status": "scheduled"
        }
      ],
      "current_status": "scheduled",
      "status_history": [
        {
          "status": "scheduled",
          "previous_status": "order_confirmed",
          "notes": "Sample collection scheduled for address Home",
          "changed_by": "admin",
          "created_at": "2025-11-25T09:00:00",
          "order_item_id": 3,
          "member_name": "John Doe"
        },
        {
          "status": "order_confirmed",
          "previous_status": null,
          "notes": "Order item created for member John Doe at address Home",
          "changed_by": "1",
          "created_at": "2025-11-24T10:00:00",
          "order_item_id": 3,
          "member_name": "John Doe"
        }
      ],
      "estimated_completion": "2025-12-01T10:00:00"
    },
    {
      "address_id": 6,
      "address_label": "Parents House",
      "address_details": {
        "address_label": "Parents House",
        "street_address": "456 Park Ave",
        "locality": "Koramangala",
        "city": "Bangalore",
        "state": "Karnataka",
        "postal_code": "560095"
      },
      "members": [
        {
          "member_id": 2,
          "member_name": "Jane Doe",
          "order_item_id": 4,
          "order_status": "order_confirmed"
        }
      ],
      "current_status": "order_confirmed",
      "status_history": [
        {
          "status": "order_confirmed",
          "previous_status": null,
          "notes": "Order item created for member Jane Doe at address Parents House",
          "changed_by": "1",
          "created_at": "2025-11-24T10:00:00",
          "order_item_id": 4,
          "member_name": "Jane Doe"
        }
      ],
      "estimated_completion": null
    }
  ]
}
```

### Error Responses

#### 404 Not Found - Order Not Found
```json
{
  "detail": "Order not found"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Ensure you have an order (use "Create Order" or "Get Order List")
2. Create a new GET request in Postman
3. Set URL to: `http://localhost:8000/orders/1/tracking`
   - Replace `1` with your actual order_id
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify the response contains status history

### Prerequisites
- Valid access token
- Order must exist and belong to the user

### Notes
- Returns current order status and complete status history
- Status history shows all status changes with timestamps
- Includes who changed the status and any notes
- **Per-address tracking**: For couple/family packs with different addresses, `address_tracking` shows status per address
- Each address group shows its members, current status, and status history
- Order-level status is synced based on all item statuses
- If all items have the same address, only one entry appears in `address_tracking`

---

## Endpoint 6: Update Order Status

### Details
- **Method:** `PUT`
- **Endpoint:** `/orders/{order_id}/status`
- **Description:** Update order status. Typically used by admin/lab technicians.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| order_id | integer | Yes | Order ID | 1 |

### Request Body - Basic Status Update (Entire Order)
```json
{
  "order_id": 1,
  "status": "scheduled",
  "notes": "Sample collection scheduled for next week"
}
```

### Request Body - Status Update for Specific Address
```json
{
  "order_id": 1,
  "status": "scheduled",
  "notes": "Sample collection scheduled for address Home",
  "address_id": 5
}
```

### Request Body - Status Update for Specific Order Item
```json
{
  "order_id": 1,
  "status": "sample_collected",
  "notes": "Sample collected from John Doe",
  "order_item_id": 3
}
```

### Request Body - Status Update with Schedule
```json
{
  "order_id": 1,
  "status": "schedule_confirmed_by_lab",
  "notes": "Lab technician assigned",
  "scheduled_date": "2025-12-01T10:00:00",
  "technician_name": "Dr. Smith",
  "technician_contact": "9876543210",
  "lab_name": "ABC Lab"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| order_id | integer | Yes | Order ID | 1 |
| status | string | Yes | New status (see valid statuses below) | "scheduled" |
| notes | string | No | Additional notes | "Sample collection scheduled" |
| scheduled_date | datetime | No | Scheduled date/time | "2025-12-01T10:00:00" |
| technician_name | string | No | Technician name | "Dr. Smith" |
| technician_contact | string | No | Technician contact | "9876543210" |
| lab_name | string | No | Lab name | "ABC Lab" |
| order_item_id | integer | No | Update status for specific order item only | 3 |
| address_id | integer | No | Update status for all items with this address | 5 |

### Status Update Behavior
- **No `order_item_id` or `address_id`**: Updates entire order and all items
- **With `order_item_id`**: Updates only that specific order item
- **With `address_id`**: Updates all order items with that address (useful for couple/family packs with same address)
- Order-level status is automatically synced based on item statuses

### Valid Order Statuses
- `pending_payment` - Order created, payment pending
- `order_confirmed` - Payment verified, order confirmed
- `scheduled` - Sample collection scheduled
- `schedule_confirmed_by_lab` - Lab confirmed schedule
- `sample_collected` - Sample collected from customer
- `sample_received_by_lab` - Sample received at lab
- `testing_in_progress` - Testing in progress
- `report_ready` - Report is ready

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Order status updated to scheduled",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "current_status": "scheduled"
}
```

### Error Responses

#### 400 Bad Request - Invalid Status
```json
{
  "detail": "Invalid status: invalid_status"
}
```

#### 404 Not Found - Order Not Found
```json
{
  "detail": "Order not found"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Ensure you have an order (use "Create Order" or "Get Order List")
2. Create a new PUT request in Postman
3. Set URL to: `http://localhost:8000/orders/1/status`
   - Replace `1` with your actual order_id
4. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
5. In Body tab, select "raw" and "JSON"
6. Paste the request body with new status
7. Click "Send"
8. Verify the status is updated (use "Get Order Tracking" to confirm)

### Prerequisites
- Valid access token
- Order must exist

### Notes
- Status updates are logged in status history
- Use valid status values from the list above
- Typically used by admin/lab technicians
- Scheduled date should be in ISO format
- **Per-address tracking**: For couple/family packs with different addresses, you can update status per address using `address_id` or per item using `order_item_id`
- When updating by `address_id`, all items at that address are updated together
- Order-level status is automatically synced to reflect the most common item status

---

## Complete Testing Flow

### Step-by-Step Order Testing

1. **Prerequisites Setup**
   - Create address: `POST /address/save`
   - Create members: `POST /member/save` (based on product plan type)
   - Add products to cart: `POST /cart/add`
   - View cart: `GET /cart/view` (save cart_item_ids)

2. **Create Order**
   - Request: `POST /orders/create`
   - Body: `{"address_id": 1, "cart_item_ids": [1, 2]}`
   - Save: `razorpay_order_id` and `order_id`

3. **Verify Payment** (After Razorpay payment)
   - Request: `POST /orders/verify-payment`
   - Body: Include payment details from Razorpay
   - Verify: Order status is "paid"

4. **Get Order List**
   - Request: `GET /orders/list`
   - Verify: Order appears in list

5. **Get Order by ID**
   - Request: `GET /orders/{order_id}`
   - Verify: Order details match

6. **Get Order Tracking**
   - Request: `GET /orders/{order_id}/tracking`
   - Verify: Status history is shown

7. **Update Order Status**
   - Request: `PUT /orders/{order_id}/status`
   - Body: `{"order_id": 1, "status": "scheduled", "notes": "Scheduled"}`
   - Verify: Status is updated

8. **Get Order Tracking Again**
   - Request: `GET /orders/{order_id}/tracking`
   - Verify: New status appears in history

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
address_id: (set after creating address)
order_id: (set after creating order)
razorpay_order_id: (set after creating order)
```

### Example URLs
```
{{base_url}}/orders/create
{{base_url}}/orders/{{order_id}}
{{base_url}}/orders/{{order_id}}/tracking
```

---

## Common Issues and Solutions

### Issue: "One or more cart items not found"
- **Solution:** Ensure cart_item_ids exist and belong to you. Use "View Cart" to get valid cart_item_ids.

### Issue: "Invalid payment signature"
- **Solution:** Ensure you're using the correct signature from Razorpay. Signature must match the payment details.

### Issue: "Order not found"
- **Solution:** Ensure the order_id exists and belongs to you. Use "Get Order List" to get valid order IDs.

### Issue: "Invalid status"
- **Solution:** Use one of the valid status values: pending_payment, order_confirmed, scheduled, etc.

### Issue: Payment verification fails
- **Solution:** Ensure payment was actually completed on Razorpay. Test with Razorpay test credentials.

### Issue: Cart items not removed after payment
- **Solution:** Ensure payment verification was successful. Cart items are only removed after successful payment verification.

