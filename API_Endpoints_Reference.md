# API Endpoints Reference

## Login Module

### POST /auth/send-otp
**Request Body:**
```json
{
  "country_code": "+91",
  "mobile": "9876543210",
  "purpose": "login"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "OTP sent successfully to 9876543210.",
  "data": {
    "mobile": "9876543210",
    "otp": "123456",
    "expires_in": 120,
    "purpose": "login"
  }
}
```

### POST /auth/verify-otp
**Request Body:**
```json
{
  "country_code": "+91",
  "mobile": "9876543210",
  "otp": "123456",
  "device_id": "device-uuid-12345",
  "device_platform": "web",
  "device_details": "{\"browser\":\"Chrome\", \"version\":\"120.0\"}"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "OTP verified successfully.",
  "data": {
    "user_id": 1,
    "name": null,
    "mobile": "9876543210",
    "email": null,
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "Bearer",
    "expires_in": 86400
  }
}
```

### POST /auth/logout
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Logged out successfully from this device."
}
```

---

## Profile Module

### GET /profile/me
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Profile retrieved successfully.",
  "data": {
    "user_id": 1,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "mobile": "9876543210"
  }
}
```

### PUT /profile/edit
**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "mobile": "9876543210"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Profile updated successfully.",
  "data": {
    "user_id": 1,
    "name": "John Doe Updated",
    "email": "john.doe@example.com",
    "mobile": "9876543210"
  }
}
```

---

## Product Module

### POST /products/addProduct
**Request Body:**
```json
{
  "Name": "DNA Test Kit - Single",
  "ShortDescription": "Starter plan for one member",
  "Description": "Complete DNA testing kit for single person",
  "Price": 5000.00,
  "SpecialPrice": 4500.00,
  "Discount": "10%",
  "Images": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
  ],
  "plan_type": "single",
  "max_members": 1,
  "category_id": 1
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Product created successfully.",
  "data": {
    "ProductId": 1,
    "Name": "DNA Test Kit - Single",
    "ShortDescription": "Starter plan for one member",
    "Description": "Complete DNA testing kit for single person",
    "Price": 5000.0,
    "SpecialPrice": 4500.0,
    "Discount": "10%",
    "Images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg"
    ],
    "plan_type": "single",
    "max_members": 1,
    "category": {
      "id": 1,
      "name": "Genetic Testing"
    }
  }
}
```

### GET /products/viewProduct
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Product list fetched successfully.",
  "data": [
    {
      "ProductId": 1,
      "Name": "DNA Test Kit - Single",
      "ShortDescription": "Starter plan for one member",
      "Description": "Complete DNA testing kit for single person",
      "Price": 5000.00,
      "SpecialPrice": 4500.00,
      "Discount": "10%",
      "Images": [
        "https://example.com/image1.jpg"
      ],
      "plan_type": "single",
      "max_members": 1,
      "category": {
        "id": 1,
        "name": "Genetic Testing"
      }
    }
  ]
}
```

### GET /products/detail/{ProductId}
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Product fetched successfully.",
  "data": {
    "ProductId": 1,
    "Name": "DNA Test Kit - Single",
    "ShortDescription": "Starter plan for one member",
    "Description": "Complete DNA testing kit for single person",
    "Price": 5000.00,
    "SpecialPrice": 4500.00,
    "Discount": "10%",
    "Images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg"
    ],
    "plan_type": "single",
    "max_members": 1,
    "category": {
      "id": 1,
      "name": "Genetic Testing"
    }
  }
}
```

### GET /categories
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Category list fetched successfully.",
  "data": [
    {
      "id": 1,
      "name": "Genetic Testing"
    },
    {
      "id": 2,
      "name": "Wellness"
    }
  ]
}
```

### POST /categories
**Request Body:**
```json
{
  "name": "Wellness"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Category created successfully.",
  "data": {
    "id": 2,
    "name": "Wellness"
  }
}
```

---

## Cart Module

### POST /cart/add
**Request Body:**
```json
{
  "product_id": 1,
  "address_id": 1,
  "member_ids": [1],
  "quantity": 1
}
```

**Response Body:**
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

### PUT /cart/update/{cart_item_id}
**Request Body:**
```json
{
  "quantity": 2
}
```

**Response Body:**
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

### DELETE /cart/delete/{cart_item_id}
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Cart item(s) deleted successfully. 2 item(s) removed."
}
```

### DELETE /cart/clear
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Cleared 5 item(s) from the cart."
}
```

### GET /cart/view
**Request Body:**
```
(No body required)
```

**Response Body:**
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
      }
    ]
  }
}
```

### POST /cart/apply-coupon
**Request Body:**
```json
{
  "coupon_code": "SAVE10"
}
```

**Response Body:**
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

### DELETE /cart/remove-coupon
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Coupon removed successfully."
}
```

---

## Address Module

### POST /address/save
**Request Body:**
```json
{
  "address_id": 0,
  "address_label": "Home",
  "street_address": "123 Main Street",
  "landmark": "Near Park",
  "locality": "Lower Parel",
  "city": "Mumbai",
  "state": "Maharashtra",
  "postal_code": "400001",
  "country": "India",
  "save_for_future": true
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Address saved successfully.",
  "data": {
    "address_id": 1,
    "user_id": 1,
    "address_label": "Home",
    "street_address": "123 Main Street",
    "landmark": "Near Park",
    "locality": "Lower Parel",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postal_code": "400001",
    "country": "India",
    "save_for_future": true
  },
  "locality_options": [
    {
      "name": "Lower Parel",
      "branch_type": "Sub Office",
      "delivery_status": "Delivery"
    }
  ]
}
```

### GET /address/list
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Address list fetched successfully.",
  "data": [
    {
      "address_id": 1,
      "user_id": 1,
      "address_label": "Home",
      "street_address": "123 Main Street",
      "landmark": "Near Park",
      "locality": "Lower Parel",
      "city": "Mumbai",
      "state": "Maharashtra",
      "postal_code": "400001",
      "country": "India",
      "save_for_future": true
    }
  ]
}
```

### GET /address/pincode/{postal_code}
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Pincode details fetched successfully.",
  "data": {
    "city": "Bangalore",
    "state": "Karnataka",
    "localities": [
      {
        "name": "Whitefield",
        "branch_type": "Sub Office",
        "delivery_status": "Delivery",
        "district": "Bangalore",
        "state": "Karnataka",
        "pincode": "560066"
      }
    ]
  }
}
```

### DELETE /address/delete/{address_id}
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Address deleted successfully."
}
```

---

## Member Module

### POST /member/save
**Request Body:**
```json
{
  "member_id": 0,
  "name": "John Doe",
  "relation": "self",
  "age": 30,
  "gender": "M",
  "dob": "1995-07-15",
  "mobile": "9876543210"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Member saved successfully."
}
```

### GET /member/list
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Member list fetched successfully.",
  "data": [
    {
      "member_id": 1,
      "name": "John Doe",
      "relation": "self",
      "age": 30,
      "gender": "M",
      "dob": "1995-07-15",
      "mobile": "9876543210"
    },
    {
      "member_id": 2,
      "name": "Jane Doe",
      "relation": "spouse",
      "age": 28,
      "gender": "F",
      "dob": "1997-03-02",
      "mobile": "9876543211"
    }
  ]
}
```

---

## Orders Module

### POST /orders/create
**Request Body:**
```json
{
  "address_id": 1,
  "cart_item_ids": [1, 2, 3]
}
```

**Response Body:**
```json
{
  "razorpay_order_id": "order_MN1234567890",
  "amount": 15050.00,
  "currency": "INR",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001"
}
```

### POST /orders/verify-payment
**Request Body:**
```json
{
  "order_id": 1,
  "razorpay_order_id": "order_MN1234567890",
  "razorpay_payment_id": "pay_MN1234567890",
  "razorpay_signature": "abc123def456..."
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Payment verified successfully. Order confirmed.",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "payment_status": "completed"
}
```

### GET /orders/list
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
[
  {
    "order_id": 1,
    "order_number": "ORD-2025-11-24-001",
    "user_id": 1,
    "address_id": 1,
    "subtotal": 16000.00,
    "discount": 0.00,
    "coupon_code": "SAVE10",
    "coupon_discount": 1000.00,
    "delivery_charge": 50.00,
    "total_amount": 15050.00,
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
]
```

### GET /orders/{order_id}
**Request Body:**
```
(No body required)
```

**Response Body:**
```json
{
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "user_id": 1,
  "address_id": 1,
  "subtotal": 16000.00,
  "discount": 0.00,
  "coupon_code": "SAVE10",
  "coupon_discount": 1000.00,
  "delivery_charge": 50.00,
  "total_amount": 15050.00,
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

### GET /orders/{order_id}/tracking
**Request Body:**
```
(No body required)
```

**Response Body:**
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

### PUT /orders/{order_id}/status
**Request Body:**
```json
{
  "order_id": 1,
  "status": "scheduled",
  "notes": "Sample collection scheduled for next week"
}
```

**Response Body:**
```json
{
  "status": "success",
  "message": "Order status updated to scheduled",
  "order_id": 1,
  "order_number": "ORD-2025-11-24-001",
  "current_status": "scheduled"
}
```

