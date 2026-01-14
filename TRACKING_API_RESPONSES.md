# Tracking API JSON Responses Documentation

This document provides comprehensive documentation of all JSON request and response structures for the Tracking API endpoints.

## Base URL
```
POST /api/tracking/event
```

## Authentication
- **Optional**: The endpoint accepts both authenticated and anonymous requests
- **Bearer Token**: If provided, user_id will be extracted and hashed with bcrypt
- **CSRF Protection**: NOT required for this endpoint

---

## Request JSON Structure

### TrackingEventRequest

```json
{
  "ga_consent": boolean,              // Required: Google Analytics consent flag
  "location_consent": boolean,        // Required: Location tracking consent flag
  "ga_client_id": string | null,      // Optional: Google Analytics Client ID (format: GA1.2.{10-20 digits}.{10-20 digits})
  "session_id": string | null,       // Optional: Session identifier (max 255 chars)
  "latitude": number | null,          // Optional: Latitude (-90 to 90), required if location_consent=true
  "longitude": number | null,         // Optional: Longitude (-180 to 180), required if location_consent=true
  "accuracy": number | null,          // Optional: Location accuracy in meters (>= 0), required if location_consent=true
  "page_url": string | null,           // Optional: Current page URL (max 500 chars)
  "referrer": string | null,          // Optional: Referrer URL (max 500 chars)
  "device_info": {                    // Optional: Device information object
    "user_agent": string | null,      // User agent string
    "device_type": string | null,     // Device type: mobile, desktop, tablet
    "browser": string | null,         // Browser name and version
    "os": string | null,              // Operating system
    "language": string | null,         // Language code (e.g., en-US)
    "timezone": string | null         // Timezone (e.g., America/Los_Angeles)
  } | null
}
```

### Validation Rules

1. **GA Consent Rules:**
   - If `ga_consent = false`: `ga_client_id` must be `null`
   - If `ga_consent = true`: `ga_client_id` can be provided (optional but recommended)

2. **Location Consent Rules:**
   - If `location_consent = true`: `latitude` and `longitude` are **required**
   - If `location_consent = false`: `latitude`, `longitude`, and `accuracy` must all be `null`

3. **GA Client ID Format:**
   - Must match pattern: `GA1.2.{10-20 digits}.{10-20 digits}`
   - Invalid formats will be ignored (set to null)

---

## Success Response JSON Structure

### TrackingEventResponse

**Status Code:** `201 Created`

```json
{
  "success": boolean,                 // Always true for successful requests
  "message": string,                  // Descriptive message based on consent settings
  "data": {
    "record_id": string,              // UUID of the created tracking record
    "user_type": string,              // "authenticated" or "anonymous"
    "user_id_hashed": boolean,        // Present only if user_type="authenticated"
    "consents": {
      "ga_consent": boolean,          // GA consent flag that was stored
      "location_consent": boolean     // Location consent flag that was stored
    },
    "fields_stored": string[],        // Array of field names that were stored (not null)
    "fields_null": string[],          // Array of field names that are null (not stored)
    "timestamp": string               // ISO 8601 timestamp in IST timezone
  }
}
```

### Message Variants

The `message` field varies based on consent settings:

- **Both consents enabled**: `"Tracking data recorded successfully"`
- **GA only**: `"Analytics tracking enabled, location tracking disabled"`
- **Location only**: `"Location tracking enabled, analytics tracking disabled"`
- **Neither**: `"Consent preferences recorded"`

### Fields Stored vs Null

The `fields_stored` and `fields_null` arrays indicate which fields were actually stored in the database:

**Always Stored (if provided):**
- `user_id` (if authenticated)
- `session_id` (if provided)
- `ga_consent` (always)
- `location_consent` (always)

**Conditionally Stored (based on consent):**
- `ga_client_id` - stored only if `ga_consent = true`
- `page_url` - stored only if `ga_consent = true` and provided
- `referrer` - stored only if `ga_consent = true` and provided
- `user_agent` - stored only if `ga_consent = true` and provided
- `device_type` - stored only if `ga_consent = true` and provided
- `browser` - stored only if `ga_consent = true` and provided
- `operating_system` - stored only if `ga_consent = true` and provided
- `language` - stored only if `ga_consent = true` and provided
- `timezone` - stored only if `ga_consent = true` and provided
- `ip_address` - stored only if `ga_consent = true`
- `latitude` - stored only if `location_consent = true` and provided
- `longitude` - stored only if `location_consent = true` and provided
- `accuracy` - stored only if `location_consent = true` and provided

---

## Error Response JSON Structures

### 1. Validation Error

**Status Code:** `400 Bad Request`

```json
{
  "detail": {
    "error_code": "VALIDATION_ERROR",
    "message": string,                // Detailed validation error message
    "request_id": string              // UUID for request tracking
  }
}
```

**Common Validation Errors:**
- `"ga_client_id must be null when ga_consent is false"`
- `"latitude and longitude are required when location_consent is true"`
- `"latitude, longitude, and accuracy must be null when location_consent is false"`
- Invalid data type or format errors

### 2. Internal Server Error

**Status Code:** `500 Internal Server Error`

```json
{
  "detail": {
    "error_code": "INTERNAL_SERVER_ERROR",
    "message": "An error occurred while recording tracking data. Please try again.",
    "request_id": string              // UUID for request tracking
  }
}
```

This error occurs for:
- Database connection errors
- Database integrity constraint violations
- Unexpected server errors

---

## Example Requests and Responses

### Example 1: Anonymous User with Full Consent

**Request:**
```json
{
  "ga_consent": true,
  "location_consent": true,
  "ga_client_id": "GA1.2.1234567890.0987654321",
  "session_id": "session_abc123",
  "latitude": 19.0760,
  "longitude": 72.8777,
  "accuracy": 10.5,
  "page_url": "https://example.com/products",
  "referrer": "https://google.com",
  "device_info": {
    "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "device_type": "desktop",
    "browser": "Chrome 120.0",
    "os": "Windows 10",
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
    "user_type": "anonymous",
    "consents": {
      "ga_consent": true,
      "location_consent": true
    },
    "fields_stored": [
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
    "fields_null": [
      "user_id"
    ],
    "timestamp": "2026-01-13T15:30:00.000Z"
  }
}
```

### Example 2: Authenticated User with GA Consent Only

**Request:**
```json
{
  "ga_consent": true,
  "location_consent": false,
  "ga_client_id": "GA1.2.1234567890.0987654321",
  "session_id": "session_abc123",
  "page_url": "https://example.com/dashboard",
  "device_info": {
    "device_type": "mobile",
    "browser": "Safari 17.0",
    "os": "iOS 17.0"
  }
}
```

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:**
```json
{
  "success": true,
  "message": "Analytics tracking enabled, location tracking disabled",
  "data": {
    "record_id": "660e8400-e29b-41d4-a716-446655440001",
    "user_type": "authenticated",
    "user_id_hashed": true,
    "consents": {
      "ga_consent": true,
      "location_consent": false
    },
    "fields_stored": [
      "user_id",
      "ga_client_id",
      "session_id",
      "page_url",
      "user_agent",
      "device_type",
      "browser",
      "operating_system",
      "ip_address"
    ],
    "fields_null": [
      "latitude",
      "longitude",
      "accuracy",
      "referrer",
      "language",
      "timezone"
    ],
    "timestamp": "2026-01-13T15:31:00.000Z"
  }
}
```

### Example 3: Location Consent Only (No GA)

**Request:**
```json
{
  "ga_consent": false,
  "location_consent": true,
  "session_id": "session_xyz789",
  "latitude": 19.0760,
  "longitude": 72.8777,
  "accuracy": 15.0
}
```

**Response:**
```json
{
  "success": true,
  "message": "Location tracking enabled, analytics tracking disabled",
  "data": {
    "record_id": "770e8400-e29b-41d4-a716-446655440002",
    "user_type": "anonymous",
    "consents": {
      "ga_consent": false,
      "location_consent": true
    },
    "fields_stored": [
      "session_id",
      "latitude",
      "longitude",
      "accuracy"
    ],
    "fields_null": [
      "user_id",
      "ga_client_id",
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
    "timestamp": "2026-01-13T15:32:00.000Z"
  }
}
```

### Example 4: No Consent (Consent Preferences Only)

**Request:**
```json
{
  "ga_consent": false,
  "location_consent": false,
  "session_id": "session_minimal"
}
```

**Response:**
```json
{
  "success": true,
  "message": "Consent preferences recorded",
  "data": {
    "record_id": "880e8400-e29b-41d4-a716-446655440003",
    "user_type": "anonymous",
    "consents": {
      "ga_consent": false,
      "location_consent": false
    },
    "fields_stored": [
      "session_id"
    ],
    "fields_null": [
      "user_id",
      "ga_client_id",
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
    "timestamp": "2026-01-13T15:33:00.000Z"
  }
}
```

### Example 5: Validation Error - Location Consent Without Coordinates

**Request:**
```json
{
  "ga_consent": true,
  "location_consent": true,
  "ga_client_id": "GA1.2.1234567890.0987654321"
}
```

**Response:**
```json
{
  "detail": {
    "error_code": "VALIDATION_ERROR",
    "message": "latitude and longitude are required when location_consent is true",
    "request_id": "990e8400-e29b-41d4-a716-446655440004"
  }
}
```

### Example 6: Validation Error - GA Client ID with GA Consent False

**Request:**
```json
{
  "ga_consent": false,
  "location_consent": false,
  "ga_client_id": "GA1.2.1234567890.0987654321"
}
```

**Response:**
```json
{
  "detail": {
    "error_code": "VALIDATION_ERROR",
    "message": "ga_client_id must be null when ga_consent is false",
    "request_id": "aa0e8400-e29b-41d4-a716-446655440005"
  }
}
```

### Example 7: Internal Server Error

**Response:**
```json
{
  "detail": {
    "error_code": "INTERNAL_SERVER_ERROR",
    "message": "An error occurred while recording tracking data. Please try again.",
    "request_id": "bb0e8400-e29b-41d4-a716-446655440006"
  }
}
```

---

## Data Storage Behavior

### Consent-Based Storage

The API implements strict consent-based data storage:

1. **GA Consent = False:**
   - `ga_client_id` → NOT stored (set to null)
   - `page_url` → NOT stored (set to null)
   - `referrer` → NOT stored (set to null)
   - `user_agent` → NOT stored (set to null)
   - `device_type` → NOT stored (set to null)
   - `browser` → NOT stored (set to null)
   - `operating_system` → NOT stored (set to null)
   - `language` → NOT stored (set to null)
   - `timezone` → NOT stored (set to null)
   - `ip_address` → NOT stored (set to null)

2. **Location Consent = False:**
   - `latitude` → NOT stored (set to null)
   - `longitude` → NOT stored (set to null)
   - `accuracy` → NOT stored (set to null)

3. **Always Stored:**
   - `ga_consent` (boolean flag)
   - `location_consent` (boolean flag)
   - `session_id` (if provided)
   - `user_id` (if authenticated, hashed with bcrypt)
   - `created_at` (timestamp, auto-generated)
   - `record_id` (UUID, auto-generated)

### User ID Hashing

For authenticated users:
- `user_id` is extracted from JWT token
- `user_id` is hashed using bcrypt before storage
- Response includes `user_id_hashed: true` flag

For anonymous users:
- `user_id` is `null`
- `user_type` is `"anonymous"`

---

## Notes

1. **IP Address**: Automatically extracted from request headers (not from request body)
2. **User Agent**: Uses `device_info.user_agent` if provided, otherwise falls back to HTTP header
3. **Timestamp**: All timestamps are in IST (Indian Standard Time) timezone
4. **Record ID**: Auto-generated UUID for each tracking record
5. **Request ID**: UUID generated for each API request (used in error responses for tracking)
6. **Idempotency**: Multiple requests with same data will create multiple records (not idempotent)

---

## Field Reference

### Request Fields

| Field | Type | Required | Max Length | Description |
|-------|------|----------|------------|-------------|
| `ga_consent` | boolean | Yes | - | Google Analytics consent flag |
| `location_consent` | boolean | Yes | - | Location tracking consent flag |
| `ga_client_id` | string\|null | Conditional | 255 | GA Client ID (required if ga_consent=true) |
| `session_id` | string\|null | No | 255 | Session identifier |
| `latitude` | number\|null | Conditional | - | Latitude (-90 to 90, required if location_consent=true) |
| `longitude` | number\|null | Conditional | - | Longitude (-180 to 180, required if location_consent=true) |
| `accuracy` | number\|null | Conditional | - | Location accuracy in meters (>= 0) |
| `page_url` | string\|null | No | 500 | Current page URL |
| `referrer` | string\|null | No | 500 | Referrer URL |
| `device_info` | object\|null | No | - | Device information object |

### Device Info Fields

| Field | Type | Required | Max Length | Description |
|-------|------|----------|------------|-------------|
| `user_agent` | string\|null | No | - | User agent string |
| `device_type` | string\|null | No | 50 | Device type: mobile, desktop, tablet |
| `browser` | string\|null | No | 100 | Browser name and version |
| `os` | string\|null | No | 100 | Operating system |
| `language` | string\|null | No | 20 | Language code (e.g., en-US) |
| `timezone` | string\|null | No | 100 | Timezone (e.g., America/Los_Angeles) |

### Response Data Fields

| Field | Type | Description |
|-------|------|-------------|
| `record_id` | string (UUID) | Unique identifier for the tracking record |
| `user_type` | string | "authenticated" or "anonymous" |
| `user_id_hashed` | boolean | Present only if user_type="authenticated" |
| `consents.ga_consent` | boolean | GA consent flag that was stored |
| `consents.location_consent` | boolean | Location consent flag that was stored |
| `fields_stored` | string[] | Array of field names that were stored |
| `fields_null` | string[] | Array of field names that are null |
| `timestamp` | string (ISO 8601) | Timestamp in IST timezone |

---

## Error Codes

| Error Code | Status Code | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Request validation failed |
| `INTERNAL_SERVER_ERROR` | 500 | Server error (database, unexpected errors) |

