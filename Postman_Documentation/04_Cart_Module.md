# Postman Testing Documentation - Cart Module

## Base URL
```
http://localhost:8000/cart
```

## Overview
This module handles shopping cart operations. Users can add products to cart, update quantities, delete items, view cart, and clear the entire cart. Cart items are linked to members and addresses. For couple and family plans, members can have either the same address or different addresses.

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

### Request Body - Single Plan Product (Single Address)
```json
{
  "product_id": 1,
  "address_id": 1,
  "member_ids": [1],
  "quantity": 1
}
```

### Request Body - Couple Plan Product (Same Address for Both Members)
```json
{
  "product_id": 2,
  "address_id": 1,
  "member_ids": [1, 2],
  "quantity": 1
}
```

### Request Body - Couple Plan Product (Different Addresses for Each Member)
```json
{
  "product_id": 2,
  "address_id": [1, 2],
  "member_ids": [1, 2],
  "quantity": 1
}
```

### Request Body - Family Plan Product (Same Address for All Members)
```json
{
  "product_id": 3,
  "address_id": 1,
  "member_ids": [1, 2, 3, 4],
  "quantity": 1
}
```

### Request Body - Family Plan Product (Different Addresses for Each Member)
```json
{
  "product_id": 3,
  "address_id": [1, 2, 3, 4],
  "member_ids": [1, 2, 3, 4],
  "quantity": 1
}
```

### Request Body - Family Plan Product (3 Mandatory Members - Minimum)
```json
{
  "product_id": 3,
  "address_id": 1,
  "member_ids": [1, 2, 3],
  "quantity": 1
}
```

### Request Body - Family Plan Product (3 Mandatory + 1 Optional Member)
```json
{
  "product_id": 3,
  "address_id": [1, 1, 1, 2],
  "member_ids": [1, 2, 3, 4],
  "quantity": 1
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| product_id | integer | Yes | Product ID to add | 1 |
| address_id | integer or array | Yes | Shipping address ID(s). Single address (shared) or list of addresses (one per member). Must be 1 address or match member count. | 1 or [1, 2] |
| member_ids | array | Yes | List of member IDs (1 for single, 2 for couple, 3-4 for family) | [1, 2] |
| quantity | integer | Yes | Quantity (default: 1) | 1 |

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
| quantity | integer | Yes | New quantity (must be >= 1) | 2 |

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

### Success Response (200 OK) - With Items
```json
{
  "status": "success",
  "message": "Cart data fetched successfully.",
  "data": {
    "user_id": 1,
    "username": "John Doe",
    "cart_summary": {
      "total_items": 2,
      "total_cart_items": 3,
      "subtotal_amount": 21000.00,
      "delivery_charge": 50.00,
      "grand_total": 21050.00
    },
    "cart_items": [
      {
        "cart_id": 1,
        "cart_item_ids": [1, 2],
        "product_id": 2,
        "address_ids": [1],
        "address_id": 1,
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
        "total_amount": 8000.00,
        "group_id": "1_2_abc123"
      },
      {
        "cart_id": 3,
        "cart_item_ids": [3],
        "product_id": 1,
        "address_id": 1,
        "member_ids": [3],
        "product_name": "DNA Test Kit - Single",
        "product_images": "https://example.com/image2.jpg",
        "plan_type": "single",
        "price": 5000.00,
        "special_price": 4500.00,
        "quantity": 2,
        "members_count": 1,
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

### Notes
- Returns empty cart if no items exist
- Items are grouped by group_id for couple/family products
- Summary includes subtotal, delivery charge, and grand total
- Delivery charge is fixed at 50.00
- `address_ids` contains unique address IDs used in the group
- `address_id` (singular) is provided for backward compatibility when all members share the same address
- `member_address_map` shows the address assigned to each member

---

## Complete Testing Flow

### Step-by-Step Cart Testing

1. **Prerequisites Setup**
   - Create address: `POST /address/save`
   - Create members: `POST /member/save` (create 1, 2, or 4 members based on product type)
   - Ensure products exist: `GET /products/viewProduct`

2. **Add Single Plan Product to Cart**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 1, "address_id": 1, "member_ids": [1], "quantity": 1}`
   - Save: cart_id from response

3. **Add Couple Plan Product to Cart (Same Address)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 2, "address_id": 1, "member_ids": [1, 2], "quantity": 1}`
   - Save: cart_id from response

4. **Add Couple Plan Product to Cart (Different Addresses)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 2, "address_id": [1, 2], "member_ids": [1, 2], "quantity": 1}`
   - Save: cart_id from response

5. **Add Family Plan Product to Cart (3 Members - Minimum)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 3, "address_id": 1, "member_ids": [1, 2, 3], "quantity": 1}`
   - Save: cart_id from response

6. **Add Family Plan Product to Cart (4 Members - Maximum)**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 3, "address_id": [1, 1, 1, 2], "member_ids": [1, 2, 3, 4], "quantity": 1}`
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

12. **Clear Cart**
    - Request: `DELETE /cart/clear`
    - Verify: All items removed

13. **View Cart**
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
```

### Example URLs
```
{{base_url}}/cart/add
{{base_url}}/cart/update/{{cart_item_id}}
{{base_url}}/cart/view
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

