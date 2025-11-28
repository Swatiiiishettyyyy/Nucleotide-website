# Postman Testing Documentation - Cart Module

## Base URL
```
http://localhost:8000/cart
```

## Overview
This module handles shopping cart operations. Users can add products to cart, update quantities, delete items, view cart, clear the entire cart, and apply coupon codes for discounts. Cart items are linked to members and addresses. For couple and family plans, members can have either the same address or different addresses. Coupons can be applied to the cart to get discounts, and the system shows "You Save" amount in the cart summary.

---

## Endpoint 1: Add to Cart

### Details
- **Method:** `POST`
- **Endpoint:** `/cart/add`
- **Description:** Add item to cart. For couple/family products, creates multiple rows (2 for couple, 3-4 for family). Every cart item must be linked with member_id and address_id. Addresses can be the same for all members or different for each member.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body - Single Plan Product
```json
{
  "product_id": 1,
  "member_address_map": [
    {"member_id": 1, "address_id": 1}
  ],
  "quantity": 1
}
```

### Request Body - Single Plan Product
```json
{
  "product_id": 1,
  "member_address_map": [
    {"member_id": 1, "address_id": 1}
  ],
  "quantity": 1
}
```

### Request Body - Couple Plan Product (Same Address for Both Members)
```json
{
  "product_id": 2,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 1}
  ],
  "quantity": 1
}
```

### Request Body - Couple Plan Product (Different Addresses for Each Member)
```json
{
  "product_id": 2,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 2}
  ],
  "quantity": 1
}
```

### Request Body - Family Plan Product (Same Address for All Members)
```json
{
  "product_id": 3,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 1},
    {"member_id": 3, "address_id": 1},
    {"member_id": 4, "address_id": 1}
  ],
  "quantity": 1
}
```

### Request Body - Family Plan Product (Different Addresses for Each Member)
```json
{
  "product_id": 3,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 2},
    {"member_id": 3, "address_id": 3},
    {"member_id": 4, "address_id": 4}
  ],
  "quantity": 1
}
```

### Request Body - Family Plan Product (3 Mandatory Members - Minimum)
```json
{
  "product_id": 3,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 1},
    {"member_id": 3, "address_id": 1}
  ],
  "quantity": 1
}
```

### Request Body - Family Plan Product (3 Mandatory + 1 Optional Member with Mixed Addresses)
```json
{
  "product_id": 3,
  "member_address_map": [
    {"member_id": 1, "address_id": 1},
    {"member_id": 2, "address_id": 1},
    {"member_id": 3, "address_id": 1},
    {"member_id": 4, "address_id": 2}
  ],
  "quantity": 1
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| product_id | integer | **Yes** | Product ID to add (must be > 0) | 1 |
| member_address_map | array | **Yes** | List of member-address mappings. Each object contains `member_id` and `address_id`. Explicitly maps each member to their delivery address. | [{"member_id": 1, "address_id": 1}, {"member_id": 2, "address_id": 1}] |
| quantity | integer | **Yes** | Quantity (must be >= 1) | 1 |

**Note:** The `member_address_map` makes it explicit which member is delivered to which address, eliminating any ambiguity. Multiple members can share the same address_id, or each can have a different address.

### Success Response (200 OK) - Same Address
```json
{
  "status": "success",
  "message": "Product added to cart successfully.",
  "data": {
    "cart_item_ids": [1, 2],
    "cart_id": 1,
    "product_id": 2,
    "address_ids": [1],
    "member_ids": [1, 2],
    "member_address_map": [
      {"member_id": 1, "address_id": 1},
      {"member_id": 2, "address_id": 1}
    ],
    "quantity": 1,
    "plan_type": "couple",
    "price": 9000.00,
    "special_price": 8000.00,
    "total_amount": 8000.00,
    "items_created": 2
  }
}
```

### Success Response (200 OK) - Different Addresses
```json
{
  "status": "success",
  "message": "Product added to cart successfully.",
  "data": {
    "cart_item_ids": [3, 4],
    "cart_id": 3,
    "product_id": 2,
    "address_ids": [1, 2],
    "member_ids": [1, 2],
    "member_address_map": [
      {"member_id": 1, "address_id": 1},
      {"member_id": 2, "address_id": 2}
    ],
    "quantity": 1,
    "plan_type": "couple",
    "price": 9000.00,
    "special_price": 8000.00,
    "total_amount": 8000.00,
    "items_created": 2
  }
}
```

### Error Responses

#### 404 Not Found - Product Not Found
```json
{
  "detail": "Product not found"
}
```

#### 422 Unprocessable Entity - Address Not Found
```json
{
  "detail": "Address 99 not found or does not belong to you."
}
```

#### 422 Unprocessable Entity - Member Not Found
```json
{
  "detail": "One or more member IDs not found for this user."
}
```

#### 422 Unprocessable Entity - Invalid Member Count
```json
{
  "detail": "Couple plan requires exactly 2 members, got 1."
}
```

#### 422 Unprocessable Entity - Invalid Family Plan Member Count
```json
{
  "detail": "Family plan requires 3-4 members (3 mandatory + 1 optional), got 2."
}
```

#### 422 Unprocessable Entity - Address Count Mismatch
```json
{
  "detail": "Address count mismatch. Provide either 1 shared address or 2 addresses (one per member). Got 3 address(es) for 2 member(s)."
}
```

#### 422 Unprocessable Entity - Address Not Found
```json
{
  "detail": "Address(es) [99, 100] not found or do not belong to you."
}
```

#### 422 Unprocessable Entity - Duplicate Members
```json
{
  "detail": "Duplicate member IDs are not allowed. Each member can only be added once per product."
}
```

#### 422 Unprocessable Entity - Member Already in Same Category
```json
{
  "detail": {
    "message": "Members already associated with another product in 'Genetic Testing' category.",
    "conflicts": [
      {
        "member_id": 7,
        "member_name": "Jane Doe",
        "existing_product_id": 12,
        "existing_product_name": "Genome Duo",
        "existing_plan_type": "couple"
      }
    ]
  }
}
```

#### 422 Unprocessable Entity - Item Already in Cart
```json
{
  "detail": "This product with the same members is already in your cart."
}
```

### Testing Steps
1. Ensure you have:
   - Valid access token
   - Created at least one address (use Address module)
   - Created required members (use Member module)
   - Product exists in system
2. Create a new POST request in Postman
3. Set URL to: `http://localhost:8000/cart/add`
4. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
5. In Body tab, select "raw" and "JSON"
6. Paste the appropriate request body based on product plan type
7. Click "Send"
8. Save `cart_id` from response for update/delete operations

### Prerequisites
- Valid access token (from Auth module)
- At least one address created (Address module)
- Required members created (Member module)
- Product exists in system (Product module)

### Notes
- Single plan requires exactly 1 member
- Couple plan requires exactly 2 members
- Family plan requires 3-4 members (3 mandatory + 1 optional)
- Address can be a single integer (shared by all members) or a list of integers (one per member)
- Address count must be either 1 (shared) or match the member count (one per member)
- Members can have the same address or different addresses for couple/family plans
- Members cannot be mapped to multiple products *within the same category* (enforced automatically)
- Same product with the same members cannot be added twice (address differences are ignored for duplicate check)

---

## Endpoint 2: Update Cart Item

### Details
- **Method:** `PUT`
- **Endpoint:** `/cart/update/{cart_item_id}`
- **Description:** Update cart item quantity. For couple/family products, updates all items in the group.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| cart_item_id | integer | Yes | Cart item ID | 1 |

### Request Body
```json
{
  "quantity": 2
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| quantity | integer | **Yes** | New quantity (must be >= 1) | 2 |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Cart item(s) updated successfully. 2 item(s) updated.",
  "data": {
    "cart_item_id": 1,
    "product_id": 2,
    "quantity": 2,
    "price": 9000.00,
    "special_price": 8000.00,
    "total_amount": 16000.00,
    "items_updated": 2
  }
}
```

### Error Responses

#### 404 Not Found - Cart Item Not Found
```json
{
  "detail": "Cart item not found"
}
```

#### 400 Bad Request - Invalid Quantity
```json
{
  "detail": [
    {
      "loc": ["body", "quantity"],
      "msg": "Quantity must be at least 1",
      "type": "value_error"
    }
  ]
}
```

### Testing Steps
1. Ensure you have a cart item (use "Add to Cart" endpoint)
2. Create a new PUT request in Postman
3. Set URL to: `http://localhost:8000/cart/update/1`
   - Replace `1` with your actual cart_item_id
4. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
5. In Body tab, select "raw" and "JSON"
6. Paste the request body with new quantity
7. Click "Send"
8. Verify the quantity and total_amount are updated

### Prerequisites
- Valid access token
- Cart item must exist and belong to the user

### Notes
- For couple/family products, updating one item updates all items in the group
- Quantity must be at least 1
- Total amount is recalculated based on new quantity

---

## Endpoint 3: Delete Cart Item

### Details
- **Method:** `DELETE`
- **Endpoint:** `/cart/delete/{cart_item_id}`
- **Description:** Delete cart item. For couple/family products, deletes all items in the group (all members).

### Headers
```
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| cart_item_id | integer | Yes | Cart item ID to delete | 1 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Cart item(s) deleted successfully. 2 item(s) removed."
}
```

### Error Responses

#### 404 Not Found - Cart Item Not Found
```json
{
  "detail": "Cart item not found"
}
```

### Testing Steps
1. Ensure you have a cart item (use "Add to Cart" endpoint)
2. Create a new DELETE request in Postman
3. Set URL to: `http://localhost:8000/cart/delete/1`
   - Replace `1` with your actual cart_item_id
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify the item is deleted (use "View Cart" to confirm)

### Prerequisites
- Valid access token
- Cart item must exist and belong to the user

### Notes
- For couple/family products, deleting one item deletes all items in the group
- This action cannot be undone

---

## Endpoint 4: Clear Cart

### Details
- **Method:** `DELETE`
- **Endpoint:** `/cart/clear`
- **Description:** Clear all cart items for current user.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Cleared 5 item(s) from the cart."
}
```

### Error Responses
No specific error responses (returns success even if cart is empty)

### Testing Steps
1. Ensure you have items in cart (use "Add to Cart" endpoint)
2. Create a new DELETE request in Postman
3. Set URL to: `http://localhost:8000/cart/clear`
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify all items are cleared (use "View Cart" to confirm)

### Prerequisites
- Valid access token

### Notes
- Deletes all cart items for the current user
- This action cannot be undone
- Returns count of deleted items

---

## Endpoint 5: View Cart

### Details
- **Method:** `GET`
- **Endpoint:** `/cart/view`
- **Description:** View cart items for current user. Returns cart items grouped by product with summary.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK) - With Items (No Coupon)
```json
{
  "status": "success",
  "message": "Cart data fetched successfully.",
  "data": {
    "user_id": 1,
    "username": "John Doe",
    "cart_summary": {
      "cart_id": 1,
      "total_items": 2,
      "total_cart_items": 3,
      "subtotal_amount": 21000.00,
      "discount_amount": 0.00,
      "coupon_amount": 0.00,
      "coupon_code": null,
      "you_save": 0.00,
      "delivery_charge": 50.00,
      "grand_total": 21050.00
    },
    "cart_items": [
      {
        "cart_item_ids": [1, 2],
        "product_id": 2,
        "address_ids": [1],
        "member_ids": [1, 2],
        "member_address_map": [
          {"member_id": 1, "address_id": 1},
          {"member_id": 2, "address_id": 1}
        ],
        "product_name": "DNA Test Kit - Couple",
        "product_images": "https://example.com/image.jpg",
        "plan_type": "couple",
        "price": 9000.00,
        "special_price": 8000.00,
        "quantity": 1,
        "members_count": 2,
        "discount_per_item": 1000.00,
        "total_amount": 8000.00,
        "group_id": "1_2_abc123"
      },
      {
        "cart_item_ids": [3],
        "product_id": 1,
        "address_ids": [1],
        "member_ids": [3],
        "member_address_map": [
          {
            "member": {
              "member_id": 3,
              "name": "Bob Smith",
              "relation": "self",
              "age": 35,
              "gender": "M",
              "dob": "1988-05-10",
              "mobile": "9876543212"
            },
            "address": {
              "address_id": 1,
              "address_label": "Home",
              "street_address": "456 Oak Avenue",
              "landmark": "Near School",
              "locality": "Suburb",
              "city": "Delhi",
              "state": "Delhi",
              "postal_code": "110001",
              "country": "India"
            }
          }
        ],
        "product_name": "DNA Test Kit - Single",
        "product_images": "https://example.com/image2.jpg",
        "plan_type": "single",
        "price": 5000.00,
        "special_price": 4500.00,
        "quantity": 2,
        "members_count": 1,
        "discount_per_item": 500.00,
        "total_amount": 9000.00,
        "group_id": null
      }
    ]
  }
}
```

### Success Response (200 OK) - Empty Cart
```json
{
  "status": "success",
  "message": "Cart is empty.",
  "data": {
    "cart_summary": null,
    "cart_items": []
  }
}
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
2. Set URL to: `http://localhost:8000/cart/view`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains cart items and summary

### Prerequisites
- Valid access token

### Success Response (200 OK) - With Items (With Coupon Applied)
```json
{
  "status": "success",
  "message": "Cart data fetched successfully.",
  "data": {
    "user_id": 1,
    "username": "John Doe",
    "cart_summary": {
      "cart_id": 1,
      "total_items": 2,
      "total_cart_items": 3,
      "subtotal_amount": 21000.00,
      "discount_amount": 0.00,
      "coupon_amount": 1000.00,
      "coupon_code": "SAVE10",
      "you_save": 1000.00,
      "delivery_charge": 50.00,
      "grand_total": 20050.00
    },
    "cart_items": [
      {
        "cart_item_ids": [1, 2],
        "product_id": 2,
        "address_ids": [1],
        "member_ids": [1, 2],
        "member_address_map": [
          {"member_id": 1, "address_id": 1},
          {"member_id": 2, "address_id": 1}
        ],
        "product_name": "DNA Test Kit - Couple",
        "product_images": "https://example.com/image.jpg",
        "plan_type": "couple",
        "price": 9000.00,
        "special_price": 8000.00,
        "quantity": 1,
        "members_count": 2,
        "discount_per_item": 1000.00,
        "total_amount": 8000.00,
        "group_id": "1_2_abc123"
      }
    ]
  }
}
```

### Notes
- Returns empty cart if no items exist
- Items are grouped by group_id for couple/family products
- Summary includes subtotal, discount amount, coupon amount, delivery charge, and grand total
- Delivery charge is fixed at 50.00
- `coupon_amount` shows the discount from applied coupon (0.00 if no coupon)
- `coupon_code` shows the applied coupon code (null if no coupon)
- `you_save` shows total savings (discount + coupon)
- `grand_total` = subtotal + delivery_charge - coupon_amount - discount_amount
- `address_ids` contains unique address IDs used in the group
- `member_address_map` shows the address assigned to each member
- `discount_per_item` shows the discount per product (price - special_price)
- `cart_item_ids` is a list of all cart item IDs in the group (for couple/family products)
- `total_items` in summary is the number of product groups, `total_cart_items` is the total individual cart item rows

---

## Endpoint 6: Apply Coupon

### Details
- **Method:** `POST`
- **Endpoint:** `/cart/apply-coupon`
- **Description:** Apply a coupon code to the cart. Validates the coupon, calculates discount amount, and shows "You Save" amount. Only one coupon can be applied at a time. Applying a new coupon replaces any previously applied coupon.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body
```json
{
  "coupon_code": "SAVE10"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| coupon_code | string | **Yes** | Coupon code to apply (1-50 characters, case-insensitive, will be converted to uppercase) | "SAVE10" |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Coupon 'SAVE10' applied successfully",
  "data": {
    "coupon_code": "SAVE10",
    "coupon_description": "10% off on orders above ₹1000",
    "discount_type": "percentage",
    "discount_value": 10.0,
    "discount_amount": 1000.00,
    "you_save": 1000.00,
    "subtotal_amount": 10000.00,
    "delivery_charge": 50.00,
    "grand_total": 9050.00
  }
}
```

### Error Responses

#### 400 Bad Request - Empty Cart
```json
{
  "detail": "Cart is empty. Add items to cart before applying coupon."
}
```

#### 400 Bad Request - Invalid Coupon Code
```json
{
  "detail": "Invalid coupon code"
}
```

#### 400 Bad Request - Coupon Not Active
```json
{
  "detail": "Coupon is not active"
}
```

#### 400 Bad Request - Coupon Expired
```json
{
  "detail": "Coupon has expired"
}
```

#### 400 Bad Request - Coupon Not Yet Valid
```json
{
  "detail": "Coupon is not yet valid"
}
```

#### 400 Bad Request - Minimum Order Amount Not Met
```json
{
  "detail": "Minimum order amount of ₹5000 required"
}
```

#### 400 Bad Request - Usage Limit Reached
```json
{
  "detail": "Coupon usage limit reached"
}
```

#### 400 Bad Request - User Already Used Coupon
```json
{
  "detail": "You have already used this coupon"
}
```

### Testing Steps
1. Ensure you have items in cart (use "Add to Cart" endpoint)
2. Create a new POST request in Postman
3. Set URL to: `http://localhost:8000/cart/apply-coupon`
4. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
5. In Body tab, select "raw" and "JSON"
6. Paste the request body with coupon code
7. Click "Send"
8. Verify the response shows discount amount and "You Save" amount
9. View cart to see updated grand total with coupon discount

### Prerequisites
- Valid access token
- Cart must have items (subtotal > 0)
- Valid coupon code must exist in the system

### Notes
- Only one coupon can be applied at a time
- Applying a new coupon replaces any previously applied coupon
- Coupon is validated for:
  - Validity period (valid_from to valid_until)
  - Status (must be active)
  - Minimum order amount
  - Usage limits (total and per-user)
- Discount amount is calculated based on coupon type:
  - **Percentage**: (subtotal × discount_value) / 100 (capped by max_discount_amount if set)
  - **Fixed**: Fixed discount amount (cannot exceed subtotal)
- Coupon code is case-insensitive (automatically converted to uppercase)
- "You Save" shows the total discount amount from the coupon

---

## Endpoint 7: Remove Coupon

### Details
- **Method:** `DELETE`
- **Endpoint:** `/cart/remove-coupon`
- **Description:** Remove the applied coupon from the cart. This will recalculate the grand total without the coupon discount.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK) - Coupon Removed
```json
{
  "status": "success",
  "message": "Coupon removed successfully."
}
```

### Success Response (200 OK) - No Coupon Applied
```json
{
  "status": "success",
  "message": "No coupon was applied to your cart."
}
```

### Error Responses
No specific error responses (returns success even if no coupon was applied)

### Testing Steps
1. Ensure you have a coupon applied (use "Apply Coupon" endpoint)
2. Create a new DELETE request in Postman
3. Set URL to: `http://localhost:8000/cart/remove-coupon`
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify the response confirms coupon removal
7. View cart to see updated grand total without coupon discount

### Prerequisites
- Valid access token

### Notes
- Removes the currently applied coupon from the cart
- Grand total is recalculated without coupon discount
- Returns success even if no coupon was applied
- This action cannot be undone (you can re-apply the same coupon if valid)

---

## Endpoint 8: List Coupons

### Details
- **Method:** `GET`
- **Endpoint:** `/cart/list-coupons`
- **Description:** List all available coupons in the database. This is a debug endpoint that helps diagnose coupon validation issues.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Found 3 coupon(s)",
  "data": {
    "total_coupons": 3,
    "coupons": [
      {
        "id": 1,
        "coupon_code": "SAVE10",
        "description": "10% off on orders above ₹1000",
        "status": "active",
        "discount_type": "percentage",
        "discount_value": 10.0,
        "min_order_amount": 1000.0,
        "max_discount_amount": 500.0,
        "max_uses": null,
        "max_uses_per_user": 1,
        "valid_from": "2024-01-01T00:00:00",
        "valid_until": "2024-12-31T23:59:59",
        "is_currently_valid": true,
        "created_at": "2024-01-01T00:00:00"
      }
    ]
  }
}
```

### Error Responses

#### 500 Internal Server Error
```json
{
  "detail": "Error listing coupons: <error_message>"
}
```

### Testing Steps
1. Create a new GET request in Postman
2. Set URL to: `http://localhost:8000/cart/list-coupons`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains all available coupons with their details

### Prerequisites
- Valid access token

### Notes
- This is a debug endpoint to help diagnose coupon validation issues
- Returns all coupons in the database regardless of validity
- `is_currently_valid` indicates if the coupon is currently valid based on status, valid_from, and valid_until dates
- Useful for testing and troubleshooting coupon-related issues

---

## Endpoint 9: Create Coupon

### Details
- **Method:** `POST`
- **Endpoint:** `/cart/create-coupon`
- **Description:** Create a new coupon in the database. This allows adding coupons for testing or administrative purposes. No authentication required.

### Headers
```
Content-Type: application/json
```

### Request Body
```json
{
  "coupon_code": "SAVE20",
  "description": "20% off on orders above ₹2000",
  "user_id": null,
  "discount_type": "percentage",
  "discount_value": 20.0,
  "min_order_amount": 2000.0,
  "max_discount_amount": 1000.0,
  "max_uses": 100,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2024-12-31T23:59:59",
  "status": "active"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| coupon_code | string | **Yes** | Coupon code (1-50 characters, will be converted to uppercase) | "SAVE20" |
| description | string | No | Coupon description (max 500 characters) | "20% off on orders above ₹2000" |
| user_id | integer | No | User ID if coupon is applicable to one user only (null = all users) | null or 1 |
| discount_type | string | **Yes** | Discount type: "percentage" or "fixed" | "percentage" |
| discount_value | float | **Yes** | Discount value (percentage 0-100 or fixed amount, must be > 0) | 20.0 |
| min_order_amount | float | No | Minimum order amount to apply coupon (default: 0.0) | 2000.0 |
| max_discount_amount | float | No | Maximum discount cap for percentage coupons (default: null) | 1000.0 |
| max_uses | integer | No | Total uses allowed (null = unlimited, not required) | 100 |
| valid_from | datetime | **Yes** | Coupon valid from date (ISO format) | "2024-01-01T00:00:00" |
| valid_until | datetime | **Yes** | Coupon valid until date (ISO format) | "2024-12-31T23:59:59" |
| status | string | No | Coupon status: "active", "inactive", or "expired" (default: "active") | "active" |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Coupon 'SAVE20' created successfully",
  "data": {
    "id": 2,
    "coupon_code": "SAVE20",
    "description": "20% off on orders above ₹2000",
    "discount_type": "percentage",
    "discount_value": 20.0,
    "user_id": null,
    "min_order_amount": 2000.0,
    "max_discount_amount": 1000.0,
    "max_uses": 100,
    "valid_from": "2024-01-01T00:00:00",
    "valid_until": "2024-12-31T23:59:59",
    "status": "active"
  }
}
```

### Error Responses

#### 400 Bad Request - Coupon Code Already Exists
```json
{
  "detail": "Coupon code 'SAVE20' already exists"
}
```

#### 422 Unprocessable Entity - Invalid Discount Type
```json
{
  "detail": [
    {
      "loc": ["body", "discount_type"],
      "msg": "discount_type must be \"percentage\" or \"fixed\"",
      "type": "value_error"
    }
  ]
}
```

#### 422 Unprocessable Entity - Invalid Discount Value
```json
{
  "detail": [
    {
      "loc": ["body", "discount_value"],
      "msg": "Percentage discount must be between 0 and 100",
      "type": "value_error"
    }
  ]
}
```

#### 500 Internal Server Error
```json
{
  "detail": "Error creating coupon: <error_message>"
}
```

### Testing Steps
1. Create a new POST request in Postman
2. Set URL to: `http://localhost:8000/cart/create-coupon`
3. Set Headers:
   - `Content-Type: application/json`
4. In Body tab, select "raw" and "JSON"
5. Paste the request body with coupon details
6. Click "Send"
7. Verify the response shows the created coupon details

### Prerequisites
- No authentication required (but recommended for production)

### Notes
- Coupon code is automatically converted to uppercase
- For percentage discounts, discount_value must be between 0 and 100
- For fixed discounts, discount_value is the fixed amount
- If user_id is null, coupon is applicable to all users
- If user_id is set, coupon is only applicable to that specific user
- max_uses is optional - if null, coupon has unlimited uses
- Status can be "active", "inactive", or "expired"

---

## Endpoint 10: Create Test Coupon

### Details
- **Method:** `POST`
- **Endpoint:** `/cart/create-test-coupon`
- **Description:** Create a test coupon for testing purposes. This creates a predefined test coupon (TEST2024) that can be used for testing the coupon functionality.

### Headers
```
(No headers required)
```

### Request Body
```
(No body required)
```

### Success Response (200 OK) - New Coupon Created
```json
{
  "status": "success",
  "message": "Test coupon 'TEST2024' created successfully",
  "data": {
    "id": 1,
    "coupon_code": "TEST2024",
    "description": "Test coupon for testing purposes - 10% off with max ₹500 discount",
    "user_id": null,
    "discount_type": "percentage",
    "discount_value": 10.0,
    "min_order_amount": 1000.0,
    "max_discount_amount": 500.0,
    "max_uses": null,
    "valid_from": "2024-01-01T00:00:00",
    "valid_until": "2025-01-01T00:00:00",
    "status": "active"
  }
}
```

### Success Response (200 OK) - Coupon Already Exists
```json
{
  "status": "success",
  "message": "Test coupon 'TEST2024' already exists",
  "data": {
    "id": 1,
    "coupon_code": "TEST2024",
    "user_id": null,
    "min_order_amount": 1000.0,
    "max_discount_amount": 500.0,
    "max_uses": null
  }
}
```

### Error Responses

#### 500 Internal Server Error
```json
{
  "detail": "Error creating test coupon: <error_message>"
}
```

### Testing Steps
1. Create a new POST request in Postman
2. Set URL to: `http://localhost:8000/cart/create-test-coupon`
3. Click "Send"
4. Verify the response shows the test coupon details
5. Use the coupon code "TEST2024" to test coupon functionality

### Prerequisites
- No authentication required

### Notes
- Creates a predefined test coupon with code "TEST2024"
- Test coupon details:
  - 10% discount (percentage type)
  - Maximum discount cap: ₹500
  - Minimum order amount: ₹1000
  - Valid for 1 year from creation date
  - Unlimited uses
  - Applicable to all users
- If the test coupon already exists, returns existing coupon details
- Useful for quick testing of coupon functionality without creating custom coupons

---

## Complete Testing Flow

### Step-by-Step Cart Testing

1. **Prerequisites Setup**
   - Create address: `POST /address/save`
   - Create members: `POST /member/save` (create 1, 2, or 4 members based on product type)
   - Ensure products exist: `GET /products/viewProduct`

2. **Add Single Plan Product to Cart**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 1, "member_address_map": [{"member_id": 1, "address_id": 1}], "quantity": 1}`
   - Save: cart_id from response

3. **Add Couple Plan Product to Cart (Same Address)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 2, "member_address_map": [{"member_id": 1, "address_id": 1}, {"member_id": 2, "address_id": 1}], "quantity": 1}`
   - Save: cart_id from response

4. **Add Couple Plan Product to Cart (Different Addresses)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 2, "member_address_map": [{"member_id": 1, "address_id": 1}, {"member_id": 2, "address_id": 2}], "quantity": 1}`
   - Save: cart_id from response

5. **Add Family Plan Product to Cart (3 Members - Minimum)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 3, "member_address_map": [{"member_id": 1, "address_id": 1}, {"member_id": 2, "address_id": 1}, {"member_id": 3, "address_id": 1}], "quantity": 1}`
   - Save: cart_id from response

6. **Add Family Plan Product to Cart (4 Members - Maximum)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 3, "member_address_map": [{"member_id": 1, "address_id": 1}, {"member_id": 2, "address_id": 1}, {"member_id": 3, "address_id": 1}, {"member_id": 4, "address_id": 2}], "quantity": 1}`
   - Save: cart_id from response

7. **View Cart**
   - Request: `GET /cart/view`
   - Verify: All products are in cart with correct address mappings

8. **Update Cart Item Quantity**
   - Request: `PUT /cart/update/{cart_item_id}`
   - Body: `{"quantity": 2}`
   - Verify: Quantity updated

9. **View Cart Again**
   - Request: `GET /cart/view`
   - Verify: Updated quantities and new totals

10. **Delete Single Item**
    - Request: `DELETE /cart/delete/{cart_item_id}`
    - Verify: Item removed

11. **View Cart**
    - Request: `GET /cart/view`
    - Verify: Item is no longer in cart

12. **Apply Coupon**
    - Request: `POST /cart/apply-coupon`
    - Body: `{"coupon_code": "SAVE10"}`
    - Verify: Coupon applied, discount amount shown, "You Save" displayed

13. **View Cart with Coupon**
    - Request: `GET /cart/view`
    - Verify: Cart summary shows coupon_code, coupon_amount, you_save, and updated grand_total

14. **Remove Coupon**
    - Request: `DELETE /cart/remove-coupon`
    - Verify: Coupon removed successfully

15. **View Cart without Coupon**
    - Request: `GET /cart/view`
    - Verify: Cart summary shows coupon_code as null, coupon_amount as 0.00, and original grand_total

16. **Clear Cart**
    - Request: `DELETE /cart/clear`
    - Verify: All items removed

17. **View Cart**
    - Request: `GET /cart/view`
    - Verify: Cart is empty

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
address_id: (set after creating address)
member_id_1: (set after creating member)
member_id_2: (set after creating member)
cart_item_id: (set after adding to cart)
coupon_code: (set coupon code to test, e.g., "SAVE10")
```

### Example URLs
```
{{base_url}}/cart/add
{{base_url}}/cart/update/{{cart_item_id}}
{{base_url}}/cart/view
{{base_url}}/cart/apply-coupon
{{base_url}}/cart/remove-coupon
```

### Example Request Body for Apply Coupon
```json
{
  "coupon_code": "{{coupon_code}}"
}
```

---

## Common Issues and Solutions

### Issue: "Product not found"
- **Solution:** Ensure the product_id exists. Use "View All Products" to get valid product IDs.

### Issue: "Address not found or does not belong to you"
- **Solution:** Create an address first using the Address module, and ensure you're using your own address_id.

### Issue: "One or more members not found"
- **Solution:** Create members first using the Member module, and ensure member_ids belong to you.

### Issue: "Couple plan requires exactly 2 members"
- **Solution:** Ensure you provide exactly 2 member_ids for couple products, 1 for single, and 3-4 for family (3 mandatory + 1 optional).

### Issue: "Address count mismatch"
- **Solution:** Provide either 1 shared address or a number of addresses matching the member count. For example, 2 members need either 1 address or 2 addresses.

### Issue: "Address(es) [X, Y] not found or does not belong to you"
- **Solution:** Ensure all address IDs exist and belong to you. Create addresses first using the Address module.

### Issue: "One or more members are already in your cart for a different product"
- **Solution:** Remove the member from the other product in cart first, or use different members.

### Issue: "This product with the same members is already in your cart"
- **Solution:** Update the quantity of existing cart item instead of adding duplicate. Note: Address differences are ignored when checking for duplicates.

### Issue: "Cart item not found"
- **Solution:** Ensure the cart_item_id exists and belongs to you. Use "View Cart" to get valid cart_item_ids.

### Issue: "Invalid coupon code"
- **Solution:** Check that the coupon code exists in the system. Coupon codes are case-insensitive.

### Issue: "Coupon has expired" or "Coupon is not yet valid"
- **Solution:** Check the coupon's validity period. Coupons have a valid_from and valid_until date.

### Issue: "Minimum order amount of ₹X required"
- **Solution:** Add more items to your cart to meet the minimum order amount required by the coupon.

### Issue: "You have already used this coupon"
- **Solution:** The coupon has a per-user usage limit. You cannot use the same coupon again if you've reached the limit.

### Issue: "Coupon usage limit reached"
- **Solution:** The coupon has reached its total usage limit across all users. Try a different coupon.

