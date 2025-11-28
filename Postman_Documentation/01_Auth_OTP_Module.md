# Postman Testing Documentation - Auth/OTP Module

## Base URL
```
http://localhost:8000/auth
```

## Overview
This module handles user authentication using OTP (One-Time Password) via mobile number. It includes OTP generation, verification, and session management.

---

## Endpoint 1: Send OTP

### Details
- **Method:** `POST`
- **Endpoint:** `/auth/send-otp`
- **Description:** Send OTP to the provided mobile number. Rate limited to prevent abuse (max 15 per hour).

### Headers
```
Content-Type: application/json
```

### Request Body
```json
{
  "country_code": "+91",
  "mobile": "9876543210",
  "purpose": "login"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| country_code | string | **Yes** | Country code with + prefix (1-5 characters) | "+91" |
| mobile | string | **Yes** | Mobile number (10-15 digits) | "9876543210" |
| purpose | string | **Yes** | Purpose of OTP (max 50 characters) | "login" |

### Success Response (200 OK)
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

### Error Responses

#### 403 Forbidden - User Blocked
```json
{
  "detail": "Account temporarily blocked due to too many failed attempts. Try again in 10 minutes."
}
```

#### 429 Too Many Requests - Rate Limit Exceeded
```json
{
  "detail": "OTP request limit reached. Remaining: 5"
}
```

#### 400 Bad Request - Invalid Input
```json
{
  "detail": [
    {
      "loc": ["body", "mobile"],
      "msg": "Mobile number must be 10-15 digits",
      "type": "value_error"
    }
  ]
}
```

### Testing Steps
1. Open Postman and create a new POST request
2. Set URL to: `http://localhost:8000/auth/send-otp`
3. Set Headers: `Content-Type: application/json`
4. In Body tab, select "raw" and "JSON"
5. Paste the request body JSON
6. Click "Send"
7. Copy the OTP from response for next endpoint

### Prerequisites
- None (public endpoint)

### Notes
- OTP expires in 120 seconds (2 minutes) by default
- Maximum 15 OTP requests per hour per mobile number
- User gets blocked for 10 minutes after 5-6 failed verification attempts

---

## Endpoint 2: Verify OTP

### Details
- **Method:** `POST`
- **Endpoint:** `/auth/verify-otp`
- **Description:** Verify OTP and create user session. Returns access token on successful verification.

### Headers
```
Content-Type: application/json
```

### Request Body
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

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| country_code | string | **Yes** | Country code with + prefix (1-5 characters) | "+91" |
| mobile | string | **Yes** | Mobile number (10-15 digits) | "9876543210" |
| otp | string | **Yes** | OTP received (4-8 digits) | "123456" |
| device_id | string | **Yes** | Unique device identifier (1-255 characters) | "device-uuid-12345" |
| device_platform | string | **Yes** | Platform: web/mobile/ios (max 50 characters) | "web" |
| device_details | string | **Yes** | JSON string with device info (max 1000 characters) | "{\"browser\":\"Chrome\"}" |

### Success Response (200 OK)
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

### Error Responses

#### 400 Bad Request - Invalid/Expired OTP
```json
{
  "detail": "OTP expired or not found"
}
```

```json
{
  "detail": "Invalid OTP. 3 attempts remaining before block."
}
```

#### 403 Forbidden - Account Blocked
```json
{
  "detail": "Too many failed attempts. Account blocked for 10 minutes."
}
```

#### 429 Too Many Requests - IP Rate Limit
```json
{
  "detail": "Too many verification attempts from this IP. Please try again later."
}
```

### Testing Steps
1. First, call the "Send OTP" endpoint and get the OTP
2. Create a new POST request in Postman
3. Set URL to: `http://localhost:8000/auth/verify-otp`
4. Set Headers: `Content-Type: application/json`
5. In Body tab, select "raw" and "JSON"
6. Paste the request body JSON with the OTP from step 1
7. Click "Send"
8. **IMPORTANT:** Copy the `access_token` from response - you'll need it for authenticated endpoints

### Prerequisites
- Valid OTP from "Send OTP" endpoint
- OTP must not be expired (within 2 minutes)

### Notes
- Access token expires in 86400 seconds (24 hours) by default
- Maximum 4 active sessions per user
- Token must be included in Authorization header for protected endpoints: `Bearer <access_token>`

---

## Endpoint 3: Logout

### Details
- **Method:** `POST`
- **Endpoint:** `/auth/logout`
- **Description:** Logout from current device/session. Only deletes the current session; other sessions remain active.

### Headers
```
Content-Type: application/json
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
  "message": "Logged out successfully from this device."
}
```

### Error Responses

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Invalid authorization header"
}
```

```json
{
  "detail": "Invalid token: Token expired"
}
```

#### 404 Not Found - Session Not Found
```json
{
  "detail": "Session not found or already inactive"
}
```

### Testing Steps
1. Create a new POST request in Postman
2. Set URL to: `http://localhost:8000/auth/logout`
3. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. After logout, the token will be invalid for subsequent requests

### Prerequisites
- Valid access token from "Verify OTP" endpoint
- Token must be included in Authorization header

### Notes
- Only the current session is deactivated
- Other active sessions on different devices remain active
- After logout, you need to verify OTP again to get a new token

---

## Complete Testing Flow

### Step-by-Step Complete Authentication Flow

1. **Send OTP**
   - Request: `POST /auth/send-otp`
   - Body: `{"country_code": "+91", "mobile": "9876543210", "purpose": "login"}`
   - Save: OTP from response

2. **Verify OTP**
   - Request: `POST /auth/verify-otp`
   - Body: `{"country_code": "+91", "mobile": "9876543210", "otp": "<saved_otp>", "device_id": "device-123"}`
   - Save: `access_token` from response

3. **Use Token for Authenticated Endpoints**
   - Add header: `Authorization: Bearer <access_token>`
   - Use this token for all protected endpoints

4. **Logout (Optional)**
   - Request: `POST /auth/logout`
   - Header: `Authorization: Bearer <access_token>`

---

## Environment Variables for Postman

Create a Postman environment with these variables:

```
base_url: http://localhost:8000
access_token: (will be set after verify-otp)
mobile: 9876543210
country_code: +91
```

### Setting Variables in Postman Tests

Add this to "Tests" tab in "Verify OTP" request:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set("access_token", jsonData.data.access_token);
    pm.environment.set("user_id", jsonData.data.user_id);
}
```

Then use in other requests:
- URL: `{{base_url}}/auth/logout`
- Header: `Authorization: Bearer {{access_token}}`

---

## Common Issues and Solutions

### Issue: "OTP expired or not found"
- **Solution:** Request a new OTP. OTPs expire in 2 minutes.

### Issue: "Account temporarily blocked"
- **Solution:** Wait for the block period to expire (10 minutes) or use a different mobile number.

### Issue: "Too many requests"
- **Solution:** Wait for the rate limit window to reset (1 hour) or use a different mobile number.

### Issue: "Invalid authorization header"
- **Solution:** Ensure the Authorization header format is: `Bearer <token>` (with space between Bearer and token).


