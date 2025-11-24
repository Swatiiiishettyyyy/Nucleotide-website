# Postman Testing Documentation - Complete Guide

## Overview
This directory contains comprehensive Postman testing documentation for all modules in the Nucleotide API. Each module has its own documentation file with detailed endpoint-by-endpoint testing instructions.

## Documentation Structure

### Module Documentation Files

1. **[01_Auth_OTP_Module.md](./01_Auth_OTP_Module.md)** - Authentication and OTP endpoints
   - Send OTP
   - Verify OTP
   - Logout

2. **[02_Profile_Module.md](./02_Profile_Module.md)** - User profile management
   - Get Profile
   - Edit Profile

3. **[03_Product_Module.md](./03_Product_Module.md)** - Product management
   - Add Product
   - View All Products
   - Get Product Detail

4. **[04_Cart_Module.md](./04_Cart_Module.md)** - Shopping cart operations
   - Add to Cart
   - Update Cart Item
   - Delete Cart Item
   - Clear Cart
   - View Cart

5. **[05_Address_Module.md](./05_Address_Module.md)** - Address management
   - Save Address
   - Get Address List
   - Delete Address

6. **[06_Member_Module.md](./06_Member_Module.md)** - Member management
   - Save Member
   - Get Member List

7. **[07_Orders_Module.md](./07_Orders_Module.md)** - Order management
   - Create Order
   - Verify Payment
   - Get Order List
   - Get Order by ID
   - Get Order Tracking
   - Update Order Status

8. **[08_Audit_Module.md](./08_Audit_Module.md)** - Audit log queries
   - Get OTP Audit Logs
   - Get Cart Audit Logs
   - Get Session Audit Logs

## Quick Start Guide

### 1. Setup Postman Environment

Create a new environment in Postman with these variables:

```
base_url: http://localhost:8000
access_token: (will be set automatically after verify-otp)
user_id: (will be set automatically after verify-otp)
```

### 2. Authentication Flow (Required First)

1. **Send OTP**
   - Endpoint: `POST /auth/send-otp`
   - See: [01_Auth_OTP_Module.md](./01_Auth_OTP_Module.md)

2. **Verify OTP**
   - Endpoint: `POST /auth/verify-otp`
   - **IMPORTANT:** Save the `access_token` from response
   - See: [01_Auth_OTP_Module.md](./01_Auth_OTP_Module.md)

3. **Use Token**
   - Add header to all protected endpoints: `Authorization: Bearer <access_token>`

### 3. Recommended Testing Order

1. **Authentication** (Required)
   - Send OTP → Verify OTP → Get access token

2. **Profile Setup**
   - Get Profile → Edit Profile (optional)

3. **Product Setup** (If testing product creation)
   - Add Product → View Products → Get Product Detail

4. **Member Setup** (Required for cart)
   - Save Member (create 1-4 members based on product plan type)

5. **Address Setup** (Required for cart)
   - Save Address → Get Address List

6. **Cart Operations**
   - Add to Cart → View Cart → Update Cart → Delete Cart Item

7. **Order Operations**
   - Create Order → Verify Payment → Get Order List → Track Order

8. **Audit Logs** (Optional)
   - Get OTP Audit Logs → Get Cart Audit Logs → Get Session Audit Logs

## Base URL

All endpoints use the base URL:
```
http://localhost:8000
```

For production, replace with your production URL.

## Authentication

Most endpoints require authentication. Include the access token in the Authorization header:

```
Authorization: Bearer <access_token>
```

The access token is obtained from the "Verify OTP" endpoint.

## Common Request Headers

### For JSON Requests
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### For GET Requests (No Body)
```
Authorization: Bearer <access_token>
```

## Testing Workflow Example

### Complete E-commerce Flow

1. **User Registration/Login**
   ```
   POST /auth/send-otp
   POST /auth/verify-otp (get access_token)
   ```

2. **Profile Setup**
   ```
   GET /profile/me
   PUT /profile/edit (optional)
   ```

3. **Browse Products**
   ```
   GET /products/viewProduct
   GET /products/detail/{ProductId}
   ```

4. **Setup Members and Address**
   ```
   POST /member/save (create members)
   POST /address/save (create address)
   ```

5. **Shopping Cart**
   ```
   POST /cart/add
   GET /cart/view
   PUT /cart/update/{cart_item_id}
   ```

6. **Place Order**
   ```
   POST /orders/create
   POST /orders/verify-payment (after Razorpay payment)
   ```

7. **Track Order**
   ```
   GET /orders/list
   GET /orders/{order_id}
   GET /orders/{order_id}/tracking
   ```

## Postman Collection Setup

### Environment Variables

Set up these variables in your Postman environment:

```javascript
base_url: http://localhost:8000
access_token: (auto-set after verify-otp)
user_id: (auto-set after verify-otp)
address_id: (set after creating address)
member_id_1: (set after creating member)
member_id_2: (set after creating member)
product_id_single: (set after adding product)
product_id_couple: (set after adding product)
product_id_family: (set after adding product)
cart_item_id: (set after adding to cart)
order_id: (set after creating order)
razorpay_order_id: (set after creating order)
```

### Automatic Variable Setting

Add this to the "Tests" tab in "Verify OTP" request:

```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.data.access_token);
    pm.environment.set("user_id", jsonData.data.user_id);
}
```

### Using Variables in Requests

- URL: `{{base_url}}/profile/me`
- Header: `Authorization: Bearer {{access_token}}`
- Body: `{"address_id": {{address_id}}}`

## Error Handling

### Common HTTP Status Codes

- **200 OK** - Request successful
- **400 Bad Request** - Invalid request data
- **401 Unauthorized** - Missing or invalid token
- **403 Forbidden** - Access denied
- **404 Not Found** - Resource not found
- **429 Too Many Requests** - Rate limit exceeded
- **500 Internal Server Error** - Server error

### Error Response Format

```json
{
  "detail": "Error message here"
}
```

## Rate Limiting

Some endpoints have rate limiting:

- **OTP Send**: Max 15 requests per hour per mobile number
- **OTP Verify**: IP-based rate limiting
- **Account Blocking**: 10 minutes after 5-6 failed OTP attempts

## Testing Tips

1. **Start with Authentication**: Always authenticate first to get access token

2. **Use Environment Variables**: Set up Postman environment variables for easier testing

3. **Follow Dependencies**: 
   - Address and Members are required before adding to cart
   - Cart items are required before creating orders

4. **Save IDs**: Save important IDs (address_id, member_id, product_id, etc.) for use in subsequent requests

5. **Test Error Cases**: Test with invalid data to verify error handling

6. **Check Audit Logs**: Use audit endpoints to verify actions were logged

7. **Use Correlation IDs**: Track requests using correlation_id for debugging

## Module Dependencies

```
Auth Module (Required for all protected endpoints)
    ↓
Profile Module
    ↓
Product Module (Optional - for product management)
    ↓
Member Module (Required for Cart)
    ↓
Address Module (Required for Cart)
    ↓
Cart Module (Required for Orders)
    ↓
Orders Module
    ↓
Audit Module (Optional - for logging)
```

## Support and Troubleshooting

### Common Issues

1. **"Not authenticated" error**
   - Solution: Ensure you have a valid access token in Authorization header

2. **"Product not found" error**
   - Solution: Create products first or use existing product IDs

3. **"Address not found" error**
   - Solution: Create address first using Address module

4. **"Member not found" error**
   - Solution: Create members first using Member module

5. **"Cart item not found" error**
   - Solution: Add items to cart first, then use valid cart_item_ids

### Getting Help

- Check individual module documentation files for detailed endpoint information
- Review error responses for specific error messages
- Check audit logs to trace request flows
- Verify all prerequisites are met before testing endpoints

## Additional Resources

- FastAPI Documentation: https://fastapi.tiangolo.com/
- Postman Documentation: https://learning.postman.com/
- Razorpay API Documentation: https://razorpay.com/docs/api/

## Notes

- All endpoints return JSON responses
- Dates are in ISO format (YYYY-MM-DDTHH:MM:SS)
- Amounts are in INR (Indian Rupees)
- Delivery charge is fixed at 50.00 INR
- OTP expires in 120 seconds (2 minutes)
- Access token expires in 86400 seconds (24 hours)

---

**Last Updated:** November 2025
**API Version:** 1.0.0

