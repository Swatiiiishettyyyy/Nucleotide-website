# Frontend Integration Guide

## Base URL
```
http://localhost:8030  (development)
https://your-domain.com (production)
```

---

## Authentication

### 1. Send OTP
**POST** `/auth/send-otp`

**Request:**
```json
{
  "country_code": "+91",
  "mobile": "9876543210",
  "purpose": "login"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully to 9876543210.",
  "data": {
    "mobile": "9876543210",
    "otp": "1234",
    "expires_in": 120,
    "purpose": "login"
  }
}
```

---

### 2. Verify OTP

**POST** `/auth/verify-otp`

**Request:**
```json
{
  "country_code": "+91",
  "mobile": "9876543210",
  "otp": "1234",
  "device_id": "unique-device-id",
  "device_platform": "web",
  "device_details": "Chrome on Windows"
}
```

**Response (Web - Cookies):**
```json
{
  "status": "success",
  "message": "OTP verified successfully.",
  "data": {
    "user_id": 123,
    "name": "John Doe",
    "mobile": "9876543210",
    "email": "john@example.com",
    "csrf_token": "csrf-token-string"
  }
}
```
**Cookies Set:**
- `access_token` - Path: `/`, HttpOnly, Secure, SameSite=Lax, Max-Age: 900 (15 minutes)
- `refresh_token` - Path: `/auth/refresh`, HttpOnly, Secure, SameSite=Strict, Max-Age: 604800 (7 days)

**Response (Mobile - JSON):**
```json
{
  "status": "success",
  "message": "OTP verified successfully.",
  "data": {
    "user_id": 123,
    "name": "John Doe",
    "mobile": "9876543210",
    "email": "john@example.com",
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "expires_in": 900
  }
}
```

---

### 3. Refresh Token

**POST** `/auth/refresh`

**Web (Cookie-based):**
- Cookies sent automatically
- No request body needed

**Request (Mobile - Body):**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (Web - Cookies):**
```json
{
  "status": "success",
  "message": "Token refreshed successfully",
  "csrf_token": "new-csrf-token-string",
  "expires_in": 900
}
```
**Cookies Updated:**
- `access_token` - New token set in cookie
- `refresh_token` - New token set in cookie (if rotation enabled)

**Response (Mobile - JSON):**
```json
{
  "status": "success",
  "message": "Token refreshed successfully",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expires_in": 900
}
```

---

### 4. Using Tokens in API Requests

**Web:**
- Cookies sent automatically with requests
- Include `X-CSRF-Token` header for state-changing requests (POST, PUT, DELETE, PATCH)
- CSRF token from login/refresh response

**Mobile:**
```
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

### 5. Logout

**POST** `/auth/logout`

**Web:**
- Cookies sent automatically

**Mobile:**
- No request body needed
- Include access token in Authorization header

**Response:**
```json
{
  "status": "success",
  "message": "Logged out successfully"
}
```

**Web:** Cookies cleared automatically

---

## Tracking

### POST `/api/tracking/event`

**Authentication:** Optional (cookie or Bearer token)

**Request:**
```json
{
  "ga_consent": true,
  "location_consent": true,
  "ga_client_id": "GA1.2.1234567890.1234567890",
  "session_id": "session-id-123",
  "latitude": 28.6139,
  "longitude": 77.2090,
  "accuracy": 10.5,
  "page_url": "https://example.com/page",
  "referrer": "https://google.com",
  "device_info": {
    "user_agent": "Mozilla/5.0...",
    "device_type": "mobile",
    "browser": "Chrome 120",
    "os": "Android 14",
    "language": "en-US",
    "timezone": "Asia/Kolkata"
  }
}
```

**Response:**
```json
{
  "success": true,
  "message": "Tracking data recorded successfully",
  "data": {
    "record_id": "550e8400-e29b-41d4-a716-446655440000",
    "user_type": "authenticated",
    "consents": {
      "ga_consent": true,
      "location_consent": true
    },
    "fields_stored": [
      "user_id",
      "ga_client_id",
      "session_id",
      "latitude",
      "longitude",
      "accuracy",
      "page_url",
      "referrer",
      "user_agent",
      "device_type",
      "browser",
      "operating_system",
      "language",
      "timezone",
      "ip_address"
    ],
    "fields_null": [],
    "timestamp": "2026-01-13T15:30:00.000Z"
  }
}
```

**Error Response (400):**
```json
{
  "error_code": "VALIDATION_ERROR",
  "message": "latitude and longitude are required when location_consent is true",
  "request_id": "uuid-string"
}
```

---

## Newsletter

### POST `/newsletter/subscribe`

**Authentication:** Optional (cookie or Bearer token)

**Request:**
```json
{
  "email": "user@example.com"
}
```

**Response (Authenticated):**
```json
{
  "status": "success",
  "message": "Successfully subscribed to newsletter (linked to your account)",
  "data": {
    "user_id": 123,
    "email": "user@example.com"
  }
}
```

**Response (Anonymous):**
```json
{
  "status": "success",
  "message": "Successfully subscribed to newsletter",
  "data": {
    "user_id": null,
    "email": "user@example.com"
  }
}
```

**Error Response (500):**
```json
{
  "detail": "Failed to subscribe to newsletter. Please try again."
}
```

---

## Token Configuration

**Access Token:**
- Lifetime: 15 minutes (900 seconds)
- Web: Stored in cookie `access_token`
- Mobile: Sent in `Authorization: Bearer` header

**Refresh Token:**
- Lifetime: 7 days
- Web: Stored in cookie `refresh_token` (path: `/auth/refresh`)
- Mobile: Sent in request body or stored locally

**CSRF Token (Web only):**
- Received in login/refresh response
- Include in `X-CSRF-Token` header for state-changing requests

---

## Error Responses

**401 Unauthorized:**
```json
{
  "detail": "Not authenticated"
}
```

**400 Bad Request:**
```json
{
  "detail": "The OTP code has expired. Please request a new one."
}
```

**500 Internal Server Error:**
```json
{
  "detail": "An error occurred. Please try again."
}
```

