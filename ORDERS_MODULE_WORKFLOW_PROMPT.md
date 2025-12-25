# Orders Module Workflow and Status Change Scenarios

## Overview
The Orders Module handles the complete order lifecycle from cart to report delivery. It uses a dual-status system: **PaymentStatus** (tracks money/transaction) and **OrderStatus** (tracks order fulfillment). Orders can only progress to fulfillment stages after payment is verified.

---

## Payment Status Values (4 Statuses)

1. **NOT_INITIATED** - Default state when order is created, payment not started
2. **SUCCESS** - Temporary status after frontend verification (before webhook)
3. **VERIFIED** - Final status after webhook confirmation (payment confirmed by Razorpay)
4. **FAILED** - Payment failed or cancelled

---

## Order Status Values (9 Statuses)

1. **CREATED** - Initial state when order is created, payment not completed
2. **AWAITING_PAYMENT_CONFIRMATION** - Payment initiated, waiting for Razorpay/bank confirmation
3. **CONFIRMED** - Payment verified by webhook, order finalized
4. **PAYMENT_FAILED** - Payment failed, order not confirmed
5. **SCHEDULED** - Appointment scheduled for sample collection (post-payment)
6. **SCHEDULE_CONFIRMED_BY_LAB** - Lab confirmed the schedule (post-payment)
7. **SAMPLE_COLLECTED** - Sample collected by technician (post-payment)
8. **SAMPLE_RECEIVED_BY_LAB** - Lab received the sample (post-payment)
9. **TESTING_IN_PROGRESS** - Lab is processing the test (post-payment)
10. **REPORT_READY** - Final status, report is ready (post-payment)

---

## Complete Order Workflow Scenarios

### Scenario 1: Successful Order Flow (Happy Path)

**Step 1: Order Creation**
- User clicks "Place Order" → `POST /orders/create`
- System creates Razorpay order
- Database order created with:
  - `payment_status = NOT_INITIATED`
  - `order_status = CREATED`
  - `razorpay_order_id` stored
- Response: Returns `razorpay_order_id` to frontend

**Step 2: User Initiates Payment**
- Frontend opens Razorpay checkout with `razorpay_order_id`
- User completes payment in Razorpay gateway
- Razorpay processes payment

**Step 3: Frontend Payment Verification**
- Razorpay redirects back to frontend with payment details
- Frontend calls `POST /orders/verify-payment` with:
  - `razorpay_order_id`
  - `razorpay_payment_id`
  - `razorpay_signature`
- System verifies signature
- If valid:
  - `payment_status = SUCCESS` (temporary)
  - `order_status` remains `CREATED` (not confirmed yet)
  - Payment details stored
- If invalid:
  - `payment_status = FAILED`
  - `order_status = PAYMENT_FAILED`

**Step 4: Webhook Confirmation (Final Authority)**
- Razorpay sends `payment.captured` webhook to `POST /orders/webhook`
- System verifies webhook signature
- If valid:
  - `payment_status = VERIFIED` (final)
  - `order_status = CONFIRMED` (order finalized)
  - Cart is cleared (idempotent)
  - Status history created
- Order can now progress to fulfillment stages

**Step 5: Order Fulfillment (Post-Payment Stages)**
- Admin/System updates order status via `PUT /orders/{order_id}/status`
- Status progression:
  - `CONFIRMED` → `SCHEDULED` → `SCHEDULE_CONFIRMED_BY_LAB` → 
  - `SAMPLE_COLLECTED` → `SAMPLE_RECEIVED_BY_LAB` → 
  - `TESTING_IN_PROGRESS` → `REPORT_READY`
- All post-payment statuses require `payment_status = VERIFIED`

---

### Scenario 2: Payment Failure Flow

**Step 1: Order Creation**
- Same as Scenario 1, Step 1
- `payment_status = NOT_INITIATED`
- `order_status = CREATED`

**Step 2: Payment Attempt Fails**
- User attempts payment but it fails (insufficient funds, card declined, etc.)
- Razorpay sends `payment.failed` webhook
- System receives webhook at `POST /orders/webhook`
- If order not already confirmed:
  - `payment_status = FAILED`
  - `order_status = PAYMENT_FAILED`
  - Status history created
- Order cannot proceed to fulfillment

**Alternative: Frontend Verification Failure**
- If frontend verification fails (invalid signature):
  - `payment_status = FAILED`
  - `order_status = PAYMENT_FAILED`
  - User must create new order to retry

---

### Scenario 3: Webhook Arrives Before Frontend Verification

**Step 1: Order Creation**
- Same as Scenario 1, Step 1

**Step 2: Webhook Arrives First**
- Razorpay sends `payment.captured` webhook immediately
- System processes webhook:
  - `payment_status = VERIFIED`
  - `order_status = CONFIRMED`
  - Cart cleared

**Step 3: Frontend Verification (Idempotent)**
- Frontend calls `POST /orders/verify-payment`
- System checks: Order already `CONFIRMED`
- Returns success without changing status (idempotent)
- User sees order confirmed

---

### Scenario 4: Late Payment Failure Webhook

**Step 1: Order Already Confirmed**
- Order is `CONFIRMED` with `payment_status = VERIFIED`
- Order is in fulfillment stage (e.g., `SCHEDULED`)

**Step 2: Late Failure Webhook Arrives**
- Razorpay sends `payment.failed` webhook (late/delayed)
- System checks: Order already `CONFIRMED`
- **Protection**: System ignores failure webhook
- Order status remains unchanged
- Logs warning: "Received payment.failed webhook for confirmed order. Ignoring."

---

### Scenario 5: Order Status Update (Post-Payment)

**Prerequisites:**
- Order must have `payment_status = VERIFIED`
- Order must have `order_status = CONFIRMED` or later

**Status Update Flow:**
- Admin/System calls `PUT /orders/{order_id}/status`
- Request body: `{"status": "SCHEDULED", "notes": "Appointment scheduled"}`
- System validates:
  - Payment is `VERIFIED` (required for post-payment statuses)
  - Status transition is valid
  - Cannot revert to `CREATED` if payment is `VERIFIED`

**Valid Transitions:**
- `CONFIRMED` → `SCHEDULED` → `SCHEDULE_CONFIRMED_BY_LAB` → 
- `SAMPLE_COLLECTED` → `SAMPLE_RECEIVED_BY_LAB` → 
- `TESTING_IN_PROGRESS` → `REPORT_READY`

**Invalid Transitions:**
- Cannot set post-payment status if `payment_status != VERIFIED`
- Cannot revert to `CREATED` if payment is `VERIFIED`
- Cannot skip statuses (must follow sequence)

---

## Status Change Rules and Validations

### Payment Status Rules

1. **NOT_INITIATED → SUCCESS**
   - Trigger: Frontend payment verification succeeds
   - Condition: Valid Razorpay signature

2. **SUCCESS → VERIFIED**
   - Trigger: Webhook `payment.captured` event
   - Condition: Webhook signature valid
   - **Final state** - cannot be changed after this

3. **Any → FAILED**
   - Trigger: Payment fails or verification fails
   - Condition: Invalid signature or Razorpay failure webhook
   - Exception: Cannot fail if already `VERIFIED` (protected)

### Order Status Rules

1. **CREATED → AWAITING_PAYMENT_CONFIRMATION**
   - Trigger: Payment initiated (optional intermediate state)

2. **CREATED/AWAITING_PAYMENT_CONFIRMATION → CONFIRMED**
   - Trigger: Webhook confirms payment
   - Condition: `payment_status = VERIFIED`
   - **Required before any post-payment statuses**

3. **Any → PAYMENT_FAILED**
   - Trigger: Payment fails
   - Condition: Payment verification fails or failure webhook
   - Exception: Cannot fail if already `CONFIRMED` (protected)

4. **CONFIRMED → Post-Payment Statuses**
   - Trigger: Admin/System updates status
   - Condition: `payment_status = VERIFIED` (required)
   - Valid statuses: `SCHEDULED`, `SCHEDULE_CONFIRMED_BY_LAB`, `SAMPLE_COLLECTED`, etc.

5. **Post-Payment Status Progression**
   - Must follow sequence (cannot skip)
   - All require `payment_status = VERIFIED`

### Protection Mechanisms

1. **Idempotency**
   - Webhook can be called multiple times safely
   - Frontend verification is idempotent
   - Already confirmed orders return success without changes

2. **Race Condition Protection**
   - Database row-level locking (`SELECT FOR UPDATE`)
   - Prevents concurrent status updates

3. **Never Downgrade Confirmed Orders**
   - Once `CONFIRMED`, cannot go back to `CREATED` or `PAYMENT_FAILED`
   - Late failure webhooks are ignored for confirmed orders

4. **Payment Verification Required**
   - Post-payment statuses require `payment_status = VERIFIED`
   - Cannot progress fulfillment without verified payment

---

## Key Endpoints and Their Status Changes

### `POST /orders/create`
- Creates order and Razorpay order
- Sets: `payment_status = NOT_INITIATED`, `order_status = CREATED`
- Returns: `razorpay_order_id` for frontend

### `POST /orders/verify-payment`
- Verifies payment signature from frontend
- Sets: `payment_status = SUCCESS` (temporary)
- Keeps: `order_status = CREATED` (not confirmed yet)
- Does NOT clear cart (webhook does this)
- Idempotent: Returns success if already verified

### `POST /orders/webhook` (Razorpay Webhook)
- **Only endpoint that confirms orders**
- Handles events: `payment.captured`, `payment.failed`, `order.paid`
- Sets: `payment_status = VERIFIED`, `order_status = CONFIRMED`
- Clears cart (idempotent)
- Final authority for payment confirmation

### `PUT /orders/{order_id}/status`
- Updates order status (admin/system)
- Validates payment is `VERIFIED` for post-payment statuses
- Creates status history
- Updates order items status

### `GET /orders/list`
- Returns user's orders
- Filters by member if `current_member` is set
- Shows orders based on `placed_by_member_id`

---

## Status History Tracking

Every status change is recorded in `order_status_history` table:
- `order_id`: Which order changed
- `order_item_id`: Which item changed (NULL for order-level)
- `status`: New status
- `previous_status`: Previous status
- `notes`: Description of change
- `changed_by`: Who changed it ("system" or user_id)
- `created_at`: Timestamp

---

## Important Notes

1. **Webhook is Final Authority**
   - Only webhook can set `payment_status = VERIFIED`
   - Only webhook can set `order_status = CONFIRMED`
   - Frontend verification is temporary (`SUCCESS`)

2. **Cart Clearing**
   - Cart is cleared ONLY by webhook (idempotent)
   - Frontend verification does NOT clear cart

3. **Order Items Have Individual Status**
   - Each `OrderItem` has its own `order_status`
   - Useful for multi-address orders (couple/family plans)
   - Items can have different statuses

4. **Member Context**
   - `placed_by_member_id` tracks which member profile was active when order was placed
   - Used for filtering orders by member
   - Stored at order creation time

5. **No COD, No Refunds**
   - System only supports online payment (Razorpay)
   - No refund policy implemented

---

## Error Handling

1. **Invalid Payment Signature**
   - Sets `payment_status = FAILED`, `order_status = PAYMENT_FAILED`
   - User must create new order

2. **Webhook Signature Invalid**
   - Returns 401 Unauthorized
   - Razorpay will retry

3. **Order Not Found in Webhook**
   - Returns 200 OK (so Razorpay doesn't retry)
   - Logs warning

4. **Status Update Validation Failures**
   - Returns 422 with error message
   - Status remains unchanged

---

## Summary

The Orders Module uses a secure, webhook-driven payment confirmation system where:
- Frontend verification provides immediate feedback (`SUCCESS`)
- Webhook provides final confirmation (`VERIFIED` + `CONFIRMED`)
- Orders can only progress to fulfillment after payment is verified
- Status changes are tracked and protected against race conditions
- Idempotent operations prevent duplicate processing

