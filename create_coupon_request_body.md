# Create Coupon Endpoint - Request Body

**Endpoint:** `POST /cart/create-coupon`  
**Authentication:** Not required (no auth token needed)

## Request Body Schema

```json
{
  "coupon_code": "string (required, 1-50 chars, will be converted to uppercase)",
  "description": "string (optional, max 500 chars)",
  "discount_type": "string (required, 'percentage' or 'fixed')",
  "discount_value": "float (required, > 0)",
  "min_order_amount": "float (optional, default: 0.0, >= 0)",
  "max_discount_amount": "float (optional, null = no cap, >= 0)",
  "max_uses": "integer (optional, null = unlimited, >= 1)",
  "valid_from": "datetime (required, ISO format: 'YYYY-MM-DDTHH:MM:SS')",
  "valid_until": "datetime (required, ISO format: 'YYYY-MM-DDTHH:MM:SS')",
  "status": "string (optional, default: 'active', values: 'active', 'inactive', 'expired')"
}
```

## Example Request Bodies

### Example 1: Percentage Discount Coupon (10% Off)
```json
{
  "coupon_code": "SAVE10",
  "description": "Get 10% off on your order. Maximum discount ₹500.",
  "discount_type": "percentage",
  "discount_value": 10.0,
  "min_order_amount": 500.0,
  "max_discount_amount": 500.0,
  "max_uses": 100,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2025-12-31T23:59:59",
  "status": "active"
}
```

### Example 2: Fixed Amount Discount (₹200 Off)
```json
{
  "coupon_code": "FLAT200",
  "description": "Get flat ₹200 off on orders above ₹1000",
  "discount_type": "fixed",
  "discount_value": 200.0,
  "min_order_amount": 1000.0,
  "max_discount_amount": null,
  "max_uses": 50,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2025-12-31T23:59:59",
  "status": "active"
}
```

### Example 3: Unlimited Use Coupon (25% Off)
```json
{
  "coupon_code": "SALE25",
  "description": "Big Sale - 25% off on all orders above ₹2000",
  "discount_type": "percentage",
  "discount_value": 25.0,
  "min_order_amount": 2000.0,
  "max_discount_amount": 2000.0,
  "max_uses": null,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2025-12-31T23:59:59",
  "status": "active"
}
```

### Example 4: Welcome Bonus (50% Off, One-Time Use)
```json
{
  "coupon_code": "WELCOME50",
  "description": "Welcome bonus - 50% off for new users",
  "discount_type": "percentage",
  "discount_value": 50.0,
  "min_order_amount": 0.0,
  "max_discount_amount": 1000.0,
  "max_uses": 1,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2025-12-31T23:59:59",
  "status": "active"
}
```

### Example 5: Free Shipping (₹50 Off, No Minimum)
```json
{
  "coupon_code": "FREESHIP",
  "description": "Free shipping on all orders",
  "discount_type": "fixed",
  "discount_value": 50.0,
  "min_order_amount": 0.0,
  "max_discount_amount": null,
  "max_uses": null,
  "valid_from": "2024-01-01T00:00:00",
  "valid_until": "2025-12-31T23:59:59",
  "status": "active"
}
```

## Field Details

| Field | Type | Required | Description | Constraints |
|-------|------|----------|-------------|-------------|
| `coupon_code` | string | Yes | Unique coupon code | 1-50 chars, auto-uppercased |
| `description` | string | No | Coupon description | Max 500 chars |
| `discount_type` | string | Yes | Type of discount | 'percentage' or 'fixed' |
| `discount_value` | float | Yes | Discount value | > 0, percentage: 0-100, fixed: amount in ₹ |
| `min_order_amount` | float | No | Minimum order to apply | Default: 0.0, >= 0 |
| `max_discount_amount` | float | No | Maximum discount cap | null = no cap, >= 0 |
| `max_uses` | integer | No | Total uses allowed | null = unlimited, >= 1 if set |
| `valid_from` | datetime | Yes | Coupon valid from | ISO format datetime |
| `valid_until` | datetime | Yes | Coupon valid until | ISO format datetime |
| `status` | string | No | Coupon status | Default: 'active', values: 'active', 'inactive', 'expired' |

## Validation Rules

1. **coupon_code**: Automatically converted to uppercase and trimmed
2. **discount_type**: Must be exactly 'percentage' or 'fixed' (case-insensitive)
3. **discount_value**: 
   - For 'percentage': Must be between 0 and 100
   - For 'fixed': Must be > 0 (amount in ₹)
4. **status**: Must be 'active', 'inactive', or 'expired' (case-insensitive)
5. **valid_from** and **valid_until**: Must be valid ISO datetime strings

## Success Response

```json
{
  "status": "success",
  "message": "Coupon 'SAVE10' created successfully",
  "data": {
    "id": 1,
    "coupon_code": "SAVE10",
    "description": "Get 10% off on your order. Maximum discount ₹500.",
    "discount_type": "percentage",
    "discount_value": 10.0,
    "user_id": null,
    "min_order_amount": 500.0,
    "max_discount_amount": 500.0,
    "max_uses": 100,
    "valid_from": "2024-01-01T00:00:00",
    "valid_until": "2025-12-31T23:59:59",
    "status": "active"
  }
}
```

## Error Responses

### 400 Bad Request - Duplicate Coupon Code
```json
{
  "detail": "Coupon code 'SAVE10' already exists"
}
```

### 422 Unprocessable Entity - Validation Error
```json
{
  "status": "error",
  "message": "Request validation failed.",
  "details": [
    {
      "source": "body",
      "field": "discount_type",
      "message": "discount_type must be \"percentage\" or \"fixed\"",
      "type": "value_error"
    }
  ]
}
```

### 500 Internal Server Error
```json
{
  "detail": "Error creating coupon: <error message>"
}
```

