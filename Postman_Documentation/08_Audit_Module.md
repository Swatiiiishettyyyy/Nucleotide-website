# Postman Testing Documentation - Audit Module

## Base URL
```
http://localhost:8000/audit
```

## Overview
This module provides audit log query endpoints for retrieving audit logs. Useful for compliance, forensics, and debugging. Includes OTP audit logs, cart audit logs, and session audit logs.

---

## Endpoint 1: Get OTP Audit Logs

### Details
- **Method:** `GET`
- **Endpoint:** `/audit/otp`
- **Description:** Get OTP audit logs. Admin users can see all logs, regular users can only see their own logs.

### Headers
```
Authorization: Bearer <access_token>
```

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| user_id | integer | No | Filter by user ID (admin only) | 1 |
| event_type | string | No | Filter by event type (GENERATED, VERIFIED, FAILED, BLOCKED) | "VERIFIED" |
| phone_number | string | No | Filter by phone number (partial match) | "9876543210" |
| correlation_id | string | No | Filter by correlation ID | "abc-123-def" |
| start_date | datetime | No | Start date (ISO format) | "2025-11-24T00:00:00" |
| end_date | datetime | No | End date (ISO format) | "2025-11-24T23:59:59" |
| limit | integer | No | Limit results (1-1000, default: 100) | 100 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "count": 5,
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "device_id": "device-123",
      "event_type": "VERIFIED",
      "phone_number": "+919876543210",
      "reason": "OTP verified successfully. IP: 192.168.1.1",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "abc-123-def",
      "timestamp": "2025-11-24T10:00:00"
    },
    {
      "id": 2,
      "user_id": null,
      "device_id": null,
      "event_type": "GENERATED",
      "phone_number": "+919876543210",
      "reason": "OTP generated and sent",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "xyz-456-ghi",
      "timestamp": "2025-11-24T09:58:00"
    }
  ]
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
2. Set URL to: `http://localhost:8000/audit/otp`
   - Optionally add query parameters: `?event_type=VERIFIED&limit=50`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains audit logs

### Prerequisites
- Valid access token

### Notes
- Regular users can only see their own logs
- Admin users can see all logs and filter by user_id
- Event types: GENERATED, VERIFIED, FAILED, BLOCKED
- Results are ordered by timestamp (newest first)
- Maximum limit is 1000 records

---

## Endpoint 2: Get Cart Audit Logs

### Details
- **Method:** `GET`
- **Endpoint:** `/audit/cart`
- **Description:** Get cart audit logs. Admin users can see all logs, regular users can only see their own logs.

### Headers
```
Authorization: Bearer <access_token>
```

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| user_id | integer | No | Filter by user ID (admin only) | 1 |
| action | string | No | Filter by action (ADD, UPDATE, DELETE, CLEAR, VIEW) | "ADD" |
| entity_type | string | No | Filter by entity type (CART_ITEM, CART) | "CART_ITEM" |
| correlation_id | string | No | Filter by correlation ID | "abc-123-def" |
| start_date | datetime | No | Start date (ISO format) | "2025-11-24T00:00:00" |
| end_date | datetime | No | End date (ISO format) | "2025-11-24T23:59:59" |
| limit | integer | No | Limit results (1-1000, default: 100) | 100 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "count": 3,
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "username": "John Doe",
      "action": "ADD",
      "entity_type": "CART_ITEM",
      "entity_id": 1,
      "details": {
        "product_id": 2,
        "plan_type": "couple",
        "quantity": 1,
        "member_ids": [1, 2],
        "address_id": 1
      },
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "abc-123-def",
      "created_at": "2025-11-24T10:00:00"
    },
    {
      "id": 2,
      "user_id": 1,
      "username": "John Doe",
      "action": "UPDATE",
      "entity_type": "CART_ITEM",
      "entity_id": 1,
      "details": {
        "product_id": 2,
        "old_quantity": 1,
        "new_quantity": 2
      },
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "xyz-456-ghi",
      "created_at": "2025-11-24T10:05:00"
    }
  ]
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
2. Set URL to: `http://localhost:8000/audit/cart`
   - Optionally add query parameters: `?action=ADD&limit=50`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains cart audit logs

### Prerequisites
- Valid access token

### Notes
- Regular users can only see their own logs
- Admin users can see all logs and filter by user_id
- Actions: ADD, UPDATE, DELETE, CLEAR, VIEW
- Entity types: CART_ITEM, CART
- Results are ordered by created_at (newest first)

---

## Endpoint 3: Get Session Audit Logs

### Details
- **Method:** `GET`
- **Endpoint:** `/audit/sessions`
- **Description:** Get session audit logs. Admin users can see all logs, regular users can only see their own logs.

### Headers
```
Authorization: Bearer <access_token>
```

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| user_id | integer | No | Filter by user ID (admin only) | 1 |
| event_type | string | No | Filter by event type (CREATED, DEACTIVATED, EXPIRED) | "CREATED" |
| correlation_id | string | No | Filter by correlation ID | "abc-123-def" |
| limit | integer | No | Limit results (1-1000, default: 100) | 100 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "count": 2,
  "data": [
    {
      "id": 1,
      "user_id": 1,
      "session_id": 1,
      "device_id": "device-123",
      "event_type": "CREATED",
      "reason": "New session created after OTP verification",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "abc-123-def",
      "timestamp": "2025-11-24T10:00:00"
    },
    {
      "id": 2,
      "user_id": 1,
      "session_id": 1,
      "device_id": "device-123",
      "event_type": "DEACTIVATED",
      "reason": "User logout",
      "ip_address": "192.168.1.1",
      "user_agent": "Mozilla/5.0...",
      "correlation_id": "xyz-456-ghi",
      "timestamp": "2025-11-24T11:00:00"
    }
  ]
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
2. Set URL to: `http://localhost:8000/audit/sessions`
   - Optionally add query parameters: `?event_type=CREATED&limit=50`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains session audit logs

### Prerequisites
- Valid access token

### Notes
- Regular users can only see their own logs
- Admin users can see all logs and filter by user_id
- Event types: CREATED, DEACTIVATED, EXPIRED
- Results are ordered by timestamp (newest first)

---

## Complete Testing Flow

### Step-by-Step Audit Testing

1. **Generate Some Activity**
   - Send OTP: `POST /auth/send-otp`
   - Verify OTP: `POST /auth/verify-otp`
   - Add to cart: `POST /cart/add`
   - View cart: `GET /cart/view`

2. **Get OTP Audit Logs**
   - Request: `GET /audit/otp`
   - Verify: OTP events are logged

3. **Get OTP Audit Logs - Filtered**
   - Request: `GET /audit/otp?event_type=VERIFIED&limit=10`
   - Verify: Only VERIFIED events are returned

4. **Get Cart Audit Logs**
   - Request: `GET /audit/cart`
   - Verify: Cart actions are logged

5. **Get Cart Audit Logs - Filtered**
   - Request: `GET /audit/cart?action=ADD&limit=10`
   - Verify: Only ADD actions are returned

6. **Get Session Audit Logs**
   - Request: `GET /audit/sessions`
   - Verify: Session events are logged

7. **Get Session Audit Logs - Filtered**
   - Request: `GET /audit/sessions?event_type=CREATED&limit=10`
   - Verify: Only CREATED events are returned

8. **Test Date Range Filter**
   - Request: `GET /audit/otp?start_date=2025-11-24T00:00:00&end_date=2025-11-24T23:59:59`
   - Verify: Only logs within date range are returned

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
user_id: (set after verify-otp)
```

### Example URLs
```
{{base_url}}/audit/otp?event_type=VERIFIED&limit=50
{{base_url}}/audit/cart?action=ADD
{{base_url}}/audit/sessions?event_type=CREATED
```

---

## Common Issues and Solutions

### Issue: No audit logs returned
- **Solution:** Ensure you've performed some actions (OTP, cart operations, etc.) that generate audit logs. Logs are created automatically when actions occur.

### Issue: "Not authenticated"
- **Solution:** Ensure you have a valid access token in the Authorization header.

### Issue: Can't see other users' logs
- **Solution:** Regular users can only see their own logs. Admin users can see all logs. Check if your user has admin privileges.

### Issue: Date filter not working
- **Solution:** Ensure dates are in ISO format: "YYYY-MM-DDTHH:MM:SS" (e.g., "2025-11-24T10:00:00").

### Issue: Limit exceeded
- **Solution:** Maximum limit is 1000. Use pagination by combining date filters with limit to get more results.

---

## Use Cases

### Compliance and Forensics
- Track all user actions for compliance requirements
- Investigate security incidents
- Monitor user behavior patterns

### Debugging
- Trace issues using correlation_id
- Debug payment or order issues
- Track session problems

### Analytics
- Analyze user activity patterns
- Monitor system usage
- Generate reports

---

## Best Practices

1. **Use Correlation IDs**: When testing, note the correlation_id from responses to trace complete request flows.

2. **Date Range Queries**: Use start_date and end_date to limit results and improve performance.

3. **Limit Results**: Always use limit parameter to avoid large responses. Default is 100, max is 1000.

4. **Filter by Event Type**: Use event_type/action filters to get specific types of logs.

5. **Admin Access**: Admin users should use user_id filter to see specific user's logs.

