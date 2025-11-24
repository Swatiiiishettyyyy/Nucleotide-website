# Postman Testing Documentation - Cart Module

## Base URL
```
http://localhost:8000/cart
```

## Overview
This module handles shopping cart operations. Users can add products to cart, update quantities, delete items, view cart, and clear the entire cart. Cart items are linked to members and addresses.

---

## Endpoint 1: Add to Cart

### Details
- **Method:** `POST`
- **Endpoint:** `/cart/add`
- **Description:** Add item to cart. For couple/family products, creates multiple rows (2 for couple, 4 for family). Every cart item must be linked with member_id and address_id.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body - Single Plan Product
```json
{
  "product_id": 1,
  "address_id": 1,
  "member_ids": [1],
  "quantity": 1
}
```

### Request Body - Couple Plan Product
```json
{
  "product_id": 2,
  "address_id": 1,
  "member_ids": [1, 2],
  "quantity": 1
}
```

### Request Body - Family Plan Product
```json
{
  "product_id": 3,
  "address_id": 1,
  "member_ids": [1, 2, 3, 4],
  "quantity": 1
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| product_id | integer | Yes | Product ID to add | 1 |
| address_id | integer | Yes | Shipping address ID | 1 |
| member_ids | array | Yes | List of member IDs (1 for single, 2 for couple, 4 for family) | [1, 2] |
| quantity | integer | Yes | Quantity (default: 1) | 1 |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Product added to cart successfully.",
  "data": {
    "cart_item_ids": [1, 2],
    "cart_id": 1,
    "product_id": 2,
    "address_id": 1,
    "member_ids": [1, 2],
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

#### 404 Not Found - Address Not Found
```json
{
  "detail": "Address not found or does not belong to you"
}
```

#### 404 Not Found - Member Not Found
```json
{
  "detail": "One or more members not found"
}
```

#### 400 Bad Request - Invalid Member Count
```json
{
  "detail": "Couple plan requires exactly 2 members, got 1"
}
```

#### 400 Bad Request - Duplicate Members
```json
{
  "detail": "Duplicate member IDs are not allowed. Each member can only be added once per product."
}
```

#### 400 Bad Request - Member Already in Same Category
```json
{
  "detail": "One or more members in this request already belong to another product in the 'Genetic Testing' category. A member cannot subscribe to multiple products in the same category."
}
```

#### 400 Bad Request - Item Already in Cart
```json
{
  "detail": "This product with the same members and address is already in your cart."
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
- Family plan requires exactly 4 members
- Members cannot be mapped to multiple products *within the same category* (enforced automatically)
- Same product with same members and address cannot be added twice

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
        "address_id": 1,
        "member_ids": [1, 2],
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

3. **Add Couple Plan Product to Cart**
   - Request: `POST /cart/add`
   - Body: `{"product_id": 2, "address_id": 1, "member_ids": [1, 2], "quantity": 1}`
   - Save: cart_id from response

4. **View Cart**
   - Request: `GET /cart/view`
   - Verify: Both products are in cart

5. **Update Cart Item Quantity**
   - Request: `PUT /cart/update/{cart_item_id}`
   - Body: `{"quantity": 2}`
   - Verify: Quantity updated

6. **View Cart Again**
   - Request: `GET /cart/view`
   - Verify: Updated quantities and new totals

7. **Delete Single Item**
   - Request: `DELETE /cart/delete/{cart_item_id}`
   - Verify: Item removed

8. **View Cart**
   - Request: `GET /cart/view`
   - Verify: Item is no longer in cart

9. **Clear Cart**
   - Request: `DELETE /cart/clear`
   - Verify: All items removed

10. **View Cart**
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
- **Solution:** Ensure you provide exactly 2 member_ids for couple products, 1 for single, and 4 for family.

### Issue: "One or more members are already in your cart for a different product"
- **Solution:** Remove the member from the other product in cart first, or use different members.

### Issue: "This product with the same members and address is already in your cart"
- **Solution:** Update the quantity of existing cart item instead of adding duplicate.

### Issue: "Cart item not found"
- **Solution:** Ensure the cart_item_id exists and belongs to you. Use "View Cart" to get valid cart_item_ids.

