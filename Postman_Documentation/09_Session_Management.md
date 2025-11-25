# Postman Testing Documentation - Session Management Module

## Base URL
```
http://localhost:8000/sessions
```

## Overview
This module handles user session management. Users can view their active sessions, check session count, and revoke sessions. The system automatically limits users to a maximum of 4 active sessions per user. When a 5th session is created, the oldest inactive session is automatically removed.

---

## Endpoint 1: Get Active Sessions

### Details
- **Method:** `GET`
- **Endpoint:** `/sessions/active`
- **Description:** Get all active sessions for the current user. Shows session count, limit status, and details of each active session.

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
  "message": "Found 3 active session(s).",
  "active_sessions_count": 3,
  "max_sessions": 4,
  "limit_reached": false,
  "remaining_slots": 1,
  "sessions": [
    {
      "session_id": 15,
      "device_id": "device-123",
      "device_platform": "web",
      "ip_address": "192.168.1.100",
      "browser_info": "Mozilla/5.0...",
      "last_active": "2025-11-24T10:30:00",
      "created_at": "2025-11-24T09:00:00",
      "is_current": true
    },
    {
      "session_id": 12,
      "device_id": "device-456",
      "device_platform": "mobile",
      "ip_address": "192.168.1.101",
      "browser_info": "Mobile Safari...",
      "last_active": "2025-11-24T08:00:00",
      "created_at": "2025-11-23T15:00:00",
      "is_current": false
    },
    {
      "session_id": 10,
      "device_id": "device-789",
      "device_platform": "ios",
      "ip_address": "192.168.1.102",
      "browser_info": "iOS App...",
      "last_active": "2025-11-23T20:00:00",
      "created_at": "2025-11-23T10:00:00",
      "is_current": false
    }
  ]
}
```

### Success Response (200 OK) - Limit Reached
```json
{
  "status": "success",
  "message": "Found 4 active session(s).",
  "active_sessions_count": 4,
  "max_sessions": 4,
  "limit_reached": true,
  "remaining_slots": 0,
  "sessions": [
    {
      "session_id": 15,
      "device_id": "device-123",
      "device_platform": "web",
      "ip_address": "192.168.1.100",
      "browser_info": "Mozilla/5.0...",
      "last_active": "2025-11-24T10:30:00",
      "created_at": "2025-11-24T09:00:00",
      "is_current": true
    },
    {
      "session_id": 14,
      "device_id": "device-456",
      "device_platform": "mobile",
      "ip_address": "192.168.1.101",
      "browser_info": "Mobile Safari...",
      "last_active": "2025-11-24T08:00:00",
      "created_at": "2025-11-23T15:00:00",
      "is_current": false
    },
    {
      "session_id": 13,
      "device_id": "device-789",
      "device_platform": "ios",
      "ip_address": "192.168.1.102",
      "browser_info": "iOS App...",
      "last_active": "2025-11-23T20:00:00",
      "created_at": "2025-11-23T10:00:00",
      "is_current": false
    },
    {
      "session_id": 11,
      "device_id": "device-abc",
      "device_platform": "android",
      "ip_address": "192.168.1.103",
      "browser_info": "Android App...",
      "last_active": "2025-11-23T18:00:00",
      "created_at": "2025-11-23T12:00:00",
      "is_current": false
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
2. Set URL to: `http://localhost:8000/sessions/active`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains active sessions and count information

### Prerequisites
- Valid access token

### Notes
- Returns all active sessions for the current user
- Sessions are ordered by `last_active` (most recent first)
- `is_current` indicates which session is the one used for the current request
- Maximum 4 active sessions per user (configurable via `MAX_ACTIVE_SESSIONS` environment variable)
- When limit is reached, creating a new session will automatically remove the oldest inactive session

---

## Endpoint 2: Get Session Count

### Details
- **Method:** `GET`
- **Endpoint:** `/sessions/count`
- **Description:** Get the count of active sessions for the current user. Quick check to see if the 4-session limit is reached.

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
  "message": "User has 3 active session(s) out of 4 maximum.",
  "active_sessions": 3,
  "max_sessions": 4,
  "limit_reached": false,
  "remaining_slots": 1
}
```

### Success Response (200 OK) - Limit Reached
```json
{
  "status": "success",
  "message": "User has 4 active session(s) out of 4 maximum.",
  "active_sessions": 4,
  "max_sessions": 4,
  "limit_reached": true,
  "remaining_slots": 0
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
2. Set URL to: `http://localhost:8000/sessions/count`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response shows session count and limit status

### Prerequisites
- Valid access token

### Notes
- Quick endpoint to check session count without full session details
- Useful for checking if user can create a new session
- `limit_reached: true` means user has reached the maximum (4) active sessions

---

## Endpoint 3: Revoke Specific Session

### Details
- **Method:** `POST`
- **Endpoint:** `/sessions/revoke/{session_id}`
- **Description:** Revoke (logout) a specific session. Users can only revoke their own sessions.

### Headers
```
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| session_id | integer | Yes | Session ID to revoke | 12 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Session 12 revoked successfully.",
  "session_id": 12
}
```

### Error Responses

#### 404 Not Found - Session Not Found
```json
{
  "detail": "Session not found"
}
```

#### 403 Forbidden - Not Your Session
```json
{
  "detail": "You can only revoke your own sessions"
}
```

#### 400 Bad Request - Session Already Inactive
```json
{
  "detail": "Session is already inactive"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Get active sessions first (use "Get Active Sessions" endpoint) to find a session_id
2. Create a new POST request in Postman
3. Set URL to: `http://localhost:8000/sessions/revoke/12`
   - Replace `12` with the actual session_id you want to revoke
4. Set Headers:
   - `Authorization: Bearer <your_access_token>`
5. Click "Send"
6. Verify the session is revoked (use "Get Active Sessions" to confirm)

### Prerequisites
- Valid access token
- Session must exist and belong to the user

### Notes
- Users can only revoke their own sessions
- Revoked sessions are marked as inactive and cannot be used for authentication
- Revoking a session logs the user out from that specific device/platform

---

## Endpoint 4: Revoke All Sessions

### Details
- **Method:** `POST`
- **Endpoint:** `/sessions/revoke-all`
- **Description:** Revoke all active sessions for the current user. Useful for logging out from all devices. Note: The current session (the one making this request) is not revoked.

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
  "message": "Revoked 3 session(s) successfully.",
  "session_id": 0
}
```

### Error Responses

#### 404 Not Found - No Active Sessions
```json
{
  "detail": "No active sessions found"
}
```

#### 400 Bad Request - Only Current Session Exists
```json
{
  "detail": "No sessions were revoked (only current session exists)"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Create a new POST request in Postman
2. Set URL to: `http://localhost:8000/sessions/revoke-all`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify all other sessions are revoked (use "Get Active Sessions" to confirm)
6. Note: The current session (used for this request) remains active

### Prerequisites
- Valid access token
- User must have multiple active sessions

### Notes
- Revokes all active sessions except the current one (the session making the request)
- Useful for security purposes (e.g., if user suspects unauthorized access)
- After revoking all sessions, user will need to log in again on other devices
- Current session remains active so the user can continue using the app

---

## How the 4-Session Limit Works

### Automatic Session Management

1. **When Creating a New Session:**
   - System checks current active session count for the user
   - If count < 4: New session is created
   - If count >= 4: Oldest inactive session (by `last_active`) is automatically deleted, then new session is created

2. **Session Tracking:**
   - Each session has a `last_active` timestamp that updates on every authenticated request
   - Sessions are ordered by `last_active` (oldest first) when determining which to remove
   - Only active sessions (`is_active = true`) count toward the limit

3. **Configuration:**
   - Default maximum: 4 sessions
   - Configurable via `MAX_ACTIVE_SESSIONS` environment variable
   - Set in `.env` file: `MAX_ACTIVE_SESSIONS=4`

### Example Scenarios

**Scenario 1: User has 3 active sessions, creates a 4th**
- Result: 4th session is created successfully
- Status: `limit_reached: false`, `remaining_slots: 0`

**Scenario 2: User has 4 active sessions, creates a 5th**
- Result: Oldest session (by `last_active`) is deleted, 5th session is created
- Status: Still 4 active sessions, `limit_reached: true`

**Scenario 3: User revokes 1 session, then creates a new one**
- Result: 1 session revoked, new session created
- Status: Back to 4 active sessions

---

## Complete Testing Flow

### Step-by-Step Session Management Testing

1. **Check Current Session Count**
   - Request: `GET /sessions/count`
   - Verify: Current active session count

2. **View All Active Sessions**
   - Request: `GET /sessions/active`
   - Verify: List of all active sessions with details
   - Note: Which session is marked as `is_current: true`

3. **Create Multiple Sessions** (by logging in from different devices/browsers)
   - Request: `POST /auth/verify-otp` (multiple times from different devices)
   - Verify: Each login creates a new session
   - Check: Session count increases (up to 4)

4. **Test Session Limit**
   - After 4 sessions, create a 5th session
   - Verify: Oldest session is automatically removed
   - Check: Still have 4 active sessions

5. **Revoke a Specific Session**
   - Request: `POST /sessions/revoke/{session_id}`
   - Verify: Session is revoked
   - Check: Session count decreases

6. **Revoke All Sessions**
   - Request: `POST /sessions/revoke-all`
   - Verify: All other sessions are revoked
   - Check: Only current session remains active

7. **Verify Session Count Again**
   - Request: `GET /sessions/count`
   - Verify: Count matches expected value

---

## Environment Variables

Add to your `.env` file to configure session limits:

```env
# Maximum number of active sessions per user (default: 4)
MAX_ACTIVE_SESSIONS=4

# Access token expiry in seconds (default: 86400 = 1 day)
ACCESS_TOKEN_EXPIRE_SECONDS=86400
```

---

## Common Use Cases

### Use Case 1: Check if User Can Create New Session
```bash
GET /sessions/count
# If remaining_slots > 0, user can create a new session
```

### Use Case 2: View All Devices User is Logged In From
```bash
GET /sessions/active
# Shows all active sessions with device/platform information
```

### Use Case 3: Logout from a Specific Device
```bash
POST /sessions/revoke/{session_id}
# Revokes specific session (logs out from that device)
```

### Use Case 4: Security: Logout from All Devices
```bash
POST /sessions/revoke-all
# Revokes all sessions except current one
```

---

## Troubleshooting

### Issue: "Session limit reached" but user only has 3 sessions
- **Solution:** Check if there are inactive sessions that weren't cleaned up. Use "Get Active Sessions" to see all sessions.

### Issue: Cannot revoke a session
- **Solution:** Ensure the session_id belongs to the current user. Users can only revoke their own sessions.

### Issue: Revoke all doesn't work
- **Solution:** If you only have 1 active session (the current one), revoke-all will not revoke anything. This is by design to prevent users from locking themselves out.

### Issue: Session count doesn't match expected
- **Solution:** Sessions are automatically cleaned up based on `last_active` timestamp. Inactive sessions may be removed by cleanup jobs.


