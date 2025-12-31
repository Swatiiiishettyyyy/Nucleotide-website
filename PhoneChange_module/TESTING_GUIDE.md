# Phone Change Module Testing Guide

This guide provides comprehensive testing instructions for the Phone Change Module API endpoints.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Authentication Setup](#authentication-setup)
3. [Test Data Setup](#test-data-setup)
4. [Phone Change Flow Overview](#phone-change-flow-overview)
5. [Testing Step 1: Verify Old Number](#testing-step-1-verify-old-number)
6. [Testing Step 2: Verify New Number](#testing-step-2-verify-new-number)
7. [Testing Cancel Functionality](#testing-cancel-functionality)
8. [Error Scenarios](#error-scenarios)
9. [API Endpoints Reference](#api-endpoints-reference)
10. [Test Checklist](#test-checklist)
11. [Status Codes Reference](#status-codes-reference)

---

## Prerequisites

### Environment Setup

1. **Server Running**: Ensure the FastAPI server is running
   ```bash
   # Default port: 8030
   # Base URL: http://localhost:8030
   ```

2. **Database**: Ensure MySQL database is running and migrations are applied
   ```bash
   .\venv\Scripts\python.exe -m alembic upgrade head
   ```

3. **Redis**: Ensure Redis is running (required for OTP storage)
   ```bash
   # Redis is used for storing OTP codes
   ```

4. **Tools**: Use one of the following for testing:
   - **Postman** (Recommended)
   - **cURL**
   - **HTTPie**
   - **FastAPI Swagger UI** (`http://localhost:8030/docs`)

---

## Authentication Setup

All phone change endpoints require authentication via JWT token.

### Step 1: Request OTP for Login

```http
POST http://localhost:8030/auth/send-otp
Content-Type: application/json

{
  "phone": "+919876543210"
}
```

### Step 2: Verify OTP and Get Access Token

```http
POST http://localhost:8030/auth/verify-otp
Content-Type: application/json

{
  "phone": "+919876543210",
  "otp": "1234"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": 1,
    "expires_in": 86400
  }
}
```

**Save the `access_token` for subsequent requests.**

---

## Test Data Setup

### 1. User Account Setup

Ensure you have a user account with:
- A valid phone number (current/old phone)
- A self profile member (member with `is_self_profile = True`)

### 2. Test Phone Numbers

You'll need:
- **Current/Old Phone**: Your current registered phone number
- **New Phone**: A phone number that is:
  - Different from your current number
  - Not already registered in the system

### 3. OTP Testing

**Note**: OTP is logged in server logs for development/testing. Check server console/logs to see the OTP when testing.

---

## Phone Change Flow Overview

The phone change process consists of 2 steps with OTP verification:

```
┌─────────────────────────────────────────────────────┐
│ Step 1: Verify Old Number                          │
│                                                     │
│  1.1 POST /api/phone-change/verify-old-number      │
│     → Send OTP to current phone                    │
│     → Returns: request_id, otp                     │
│                                                     │
│  1.2 POST /api/phone-change/confirm-old-number     │
│     → Verify OTP from old phone                    │
│     → Returns: session_token (valid for 10 min)    │
└─────────────────────────────────────────────────────┘
                     ↓
┌─────────────────────────────────────────────────────┐
│ Step 2: Verify New Number                          │
│                                                     │
│  2.1 POST /api/phone-change/verify-new-number      │
│     → Send OTP to new phone                        │
│     → Returns: request_id, otp                     │
│                                                     │
│  2.2 POST /api/phone-change/confirm-new-number     │
│     → Verify OTP from new phone                    │
│     → Updates users.mobile and members.mobile      │
│     → Returns: new_phone                           │
└─────────────────────────────────────────────────────┘
```

### Important Notes

- **Session Token**: Valid for 10 minutes after Step 1 completion
- **OTP Expiry**: OTP expires in 3 minutes
- **Max Attempts**: 3 attempts per OTP verification step
- **Cooldown**: 15 minutes lock after max attempts exceeded
- **Rate Limit**: Max 10,000 requests per day per user

---

## Testing Step 1: Verify Old Number

### Test Case 1.1: Initiate Old Number Verification

**Endpoint**: `POST /api/phone-change/verify-old-number`

```http
POST http://localhost:8030/api/phone-change/verify-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "old_phone": "9876543210"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully to your current phone number",
  "request_id": 1,
  "otp": "1234",
  "otp_expires_in": 180,
  "remaining_attempts": 3
}
```

**Notes:**
- `old_phone` must match your current registered phone number
- OTP is included in response for development/testing
- Check server logs to see the OTP if not in response
- `request_id` is used in the next step

### Test Case 1.2: Confirm Old Number OTP

**Endpoint**: `POST /api/phone-change/confirm-old-number`

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1,
  "otp": "1234"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Old phone number verified successfully",
  "session_token": "abc123def456...",
  "session_expires_in": 600
}
```

**Notes:**
- Save the `session_token` for Step 2
- Session token is valid for 10 minutes (600 seconds)
- After this step, you can proceed to Step 2

### Test Case 1.3: Invalid OTP

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1,
  "otp": "9999"
}
```

**Expected Error (First Attempt):**
```json
{
  "detail": "Invalid OTP. 2 attempts remaining."
}
```

**Expected Error (After 3 Failed Attempts):**
```json
{
  "detail": "Maximum 3 attempts exceeded. Please try again in 15 minutes."
}
```

### Test Case 1.4: OTP Expired

Wait 3+ minutes after receiving OTP, then try to verify:

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1,
  "otp": "1234"
}
```

**Expected Error:**
```json
{
  "detail": "OTP has expired. Please request a new one."
}
```

**Solution**: Call `/verify-old-number` again to get a new OTP.

---

## Testing Step 2: Verify New Number

**Prerequisite**: Complete Step 1 and save the `session_token`.

### Test Case 2.1: Initiate New Number Verification

**Endpoint**: `POST /api/phone-change/verify-new-number`

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456...",
  "new_phone": "9876543211"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully to your new phone number",
  "request_id": 1,
  "otp": "5678",
  "otp_expires_in": 180,
  "remaining_attempts": 3
}
```

**Notes:**
- `new_phone` must be different from your current phone
- `new_phone` must not be already registered in the system
- OTP is sent to the new phone number
- Check server logs for OTP if not in response

### Test Case 2.2: Confirm New Number OTP (Complete Phone Change)

**Endpoint**: `POST /api/phone-change/confirm-new-number`

```http
POST http://localhost:8030/api/phone-change/confirm-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456...",
  "otp": "5678"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Phone number changed successfully",
  "new_phone": "9876543211"
}
```

**Notes:**
- After this step, your phone number is updated in:
  - `users.mobile`
  - `members.mobile` (for self profile member)
- The request status is set to `COMPLETED`
- Session token is invalidated

### Test Case 2.3: New Phone Same as Old Phone

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456...",
  "new_phone": "9876543210"
}
```

**Expected Error:**
```json
{
  "detail": "New number cannot be the same as current number"
}
```

### Test Case 2.4: New Phone Already Registered

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456...",
  "new_phone": "9999999999"
}
```

**Expected Error (if phone is already registered):**
```json
{
  "detail": "This phone number is already registered"
}
```

### Test Case 2.5: Session Token Expired

Wait 10+ minutes after Step 1, then try Step 2:

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456...",
  "new_phone": "9876543211"
}
```

**Expected Error:**
```json
{
  "detail": "Session expired. Please start the process again."
}
```

**Solution**: Start from Step 1 again.

---

## Testing Cancel Functionality

### Endpoint: `POST /api/phone-change/cancel`

You can cancel the phone change process at any point (before completion).

### Test Case: Cancel by Session Token

```http
POST http://localhost:8030/api/phone-change/cancel
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "abc123def456..."
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Phone change process cancelled successfully"
}
```

### Test Case: Cancel by Request ID

```http
POST http://localhost:8030/api/phone-change/cancel
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Phone change process cancelled successfully"
}
```

**Notes:**
- Can cancel using either `session_token` OR `request_id`
- Request status is set to `CANCELLED`
- Cannot cancel if already `COMPLETED`

---

## Error Scenarios

### 1. Phone Number Mismatch

```http
POST http://localhost:8030/api/phone-change/verify-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "old_phone": "9999999999"
}
```

**Expected Error:**
```json
{
  "detail": "Phone number does not match your current number"
}
```

### 2. Invalid Phone Format

```http
POST http://localhost:8030/api/phone-change/verify-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "old_phone": "123"
}
```

**Expected Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "old_phone"],
      "msg": "Phone number must be 10-15 digits",
      "type": "value_error"
    }
  ]
}
```

### 3. Invalid OTP Format

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1,
  "otp": "12"
}
```

**Expected Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "otp"],
      "msg": "OTP must be 4 digits",
      "type": "value_error"
    }
  ]
}
```

### 4. Invalid Session Token

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "session_token": "invalid_token",
  "new_phone": "9876543211"
}
```

**Expected Error:**
```json
{
  "detail": "Invalid or expired session token"
}
```

### 5. Missing Required Fields

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "request_id": 1
}
```

**Expected Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "otp"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### 6. Unauthorized Access (No Token)

```http
POST http://localhost:8030/api/phone-change/verify-old-number
Content-Type: application/json

{
  "old_phone": "9876543210"
}
```

**Expected Error:**
```json
{
  "detail": "Not authenticated"
}
```

### 7. Rate Limit Exceeded

If you exceed 10,000 requests per day:

**Expected Error:**
```json
{
  "detail": "Maximum 10000 phone change requests per day. Please try again tomorrow."
}
```

### 8. Account Locked (Max Attempts)

After 3 failed OTP attempts:

**Expected Error:**
```json
{
  "detail": "Maximum 3 attempts exceeded. Please try again in 15 minutes."
}
```

**Solution**: Wait 15 minutes before trying again.

---

## API Endpoints Reference

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/phone-change/verify-old-number` | Send OTP to current phone | Yes |
| POST | `/api/phone-change/confirm-old-number` | Verify OTP for current phone | Yes |
| POST | `/api/phone-change/verify-new-number` | Send OTP to new phone | Yes |
| POST | `/api/phone-change/confirm-new-number` | Verify OTP for new phone and complete | Yes |
| POST | `/api/phone-change/cancel` | Cancel phone change process | Yes |

### Request/Response Schemas

#### VerifyOldNumberRequest
```json
{
  "old_phone": "9876543210"
}
```

#### ConfirmOldNumberRequest
```json
{
  "request_id": 1,
  "otp": "1234"
}
```

#### VerifyNewNumberRequest
```json
{
  "session_token": "abc123def456...",
  "new_phone": "9876543211"
}
```

#### ConfirmNewNumberRequest
```json
{
  "session_token": "abc123def456...",
  "otp": "5678"
}
```

#### CancelPhoneChangeRequest
```json
{
  "session_token": "abc123def456..."
}
```
OR
```json
{
  "request_id": 1
}
```

---

## Test Checklist

### Step 1: Verify Old Number

- [ ] Initiate old number verification with correct phone
- [ ] Initiate with incorrect phone (should fail)
- [ ] Initiate with invalid phone format (should fail)
- [ ] Confirm OTP with correct OTP
- [ ] Confirm OTP with incorrect OTP (3 attempts)
- [ ] Confirm OTP after expiry (should fail)
- [ ] Verify request_id is returned
- [ ] Verify session_token is returned after confirmation
- [ ] Test account lock after 3 failed attempts
- [ ] Test cooldown period (15 minutes)

### Step 2: Verify New Number

- [ ] Initiate new number verification with valid session token
- [ ] Initiate with expired session token (should fail)
- [ ] Initiate with invalid session token (should fail)
- [ ] Initiate with same phone as old phone (should fail)
- [ ] Initiate with already registered phone (should fail)
- [ ] Confirm new number OTP with correct OTP
- [ ] Confirm new number OTP with incorrect OTP (3 attempts)
- [ ] Confirm new number OTP after expiry (should fail)
- [ ] Verify phone number is updated in database after completion
- [ ] Verify self profile member phone is updated
- [ ] Test session token expiry (10 minutes)

### Cancel Functionality

- [ ] Cancel by session_token
- [ ] Cancel by request_id
- [ ] Cancel after Step 1 completion
- [ ] Cancel after Step 2.1 (before final confirmation)
- [ ] Cancel already completed request (should fail or ignore)
- [ ] Cancel with invalid session_token (should fail)
- [ ] Cancel with invalid request_id (should fail)

### Error Handling

- [ ] No authentication token
- [ ] Invalid/expired token
- [ ] Phone number validation errors
- [ ] OTP format validation errors
- [ ] Invalid request_id
- [ ] Invalid session_token
- [ ] Missing required fields
- [ ] Rate limit exceeded
- [ ] Database errors (race conditions)

### Edge Cases

- [ ] Concurrent phone change requests (should cancel previous)
- [ ] Phone change while logged in from multiple devices
- [ ] Request expiry (10 minutes for abandoned requests)
- [ ] OTP expiry (3 minutes)
- [ ] Session token expiry (10 minutes)
- [ ] Multiple OTP requests (should invalidate previous OTP)
- [ ] Phone number already taken (race condition check)

---

## Status Codes Reference

The phone change request can have the following statuses:

| Status | Description |
|--------|-------------|
| `old_number_pending` | Step 1 initiated, waiting for OTP verification |
| `old_number_verified` | Step 1 completed, session token generated |
| `new_number_pending` | Step 2 initiated, waiting for OTP verification |
| `completed` | Phone change completed successfully |
| `cancelled` | Process cancelled by user |
| `expired` | Request expired (10 minutes inactivity) |
| `failed_old_otp` | Failed to verify old number OTP |
| `failed_new_otp` | Failed to verify new number OTP |
| `locked` | Account locked after max attempts |
| `failed_db_update` | Database update failed |
| `failed_sms` | SMS sending failed (if SMS service integrated) |

---

## Testing with cURL

### Step 1.1: Verify Old Number

```bash
curl -X POST "http://localhost:8030/api/phone-change/verify-old-number" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "old_phone": "9876543210"
  }'
```

### Step 1.2: Confirm Old Number

```bash
curl -X POST "http://localhost:8030/api/phone-change/confirm-old-number" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": 1,
    "otp": "1234"
  }'
```

### Step 2.1: Verify New Number

```bash
curl -X POST "http://localhost:8030/api/phone-change/verify-new-number" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "YOUR_SESSION_TOKEN",
    "new_phone": "9876543211"
  }'
```

### Step 2.2: Confirm New Number

```bash
curl -X POST "http://localhost:8030/api/phone-change/confirm-new-number" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "YOUR_SESSION_TOKEN",
    "otp": "5678"
  }'
```

### Cancel Phone Change

```bash
curl -X POST "http://localhost:8030/api/phone-change/cancel" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "session_token": "YOUR_SESSION_TOKEN"
  }'
```

---

## Testing with FastAPI Swagger UI

1. Navigate to `http://localhost:8030/docs`
2. Click "Authorize" button (top right)
3. Enter: `Bearer YOUR_ACCESS_TOKEN`
4. Click "Authorize"
5. Test endpoints directly from the UI

**Advantages:**
- Interactive API documentation
- No need to manually construct requests
- See request/response schemas
- Test all endpoints easily

---

## Complete Flow Example

Here's a complete flow example:

### 1. Get Access Token

```http
POST http://localhost:8030/auth/verify-otp
{
  "phone": "+919876543210",
  "otp": "1234"
}
```

**Save**: `access_token`

### 2. Step 1.1: Verify Old Number

```http
POST http://localhost:8030/api/phone-change/verify-old-number
Authorization: Bearer {access_token}
{
  "old_phone": "9876543210"
}
```

**Save**: `request_id` and `otp` (or check server logs)

### 3. Step 1.2: Confirm Old Number

```http
POST http://localhost:8030/api/phone-change/confirm-old-number
Authorization: Bearer {access_token}
{
  "request_id": 1,
  "otp": "1234"
}
```

**Save**: `session_token`

### 4. Step 2.1: Verify New Number

```http
POST http://localhost:8030/api/phone-change/verify-new-number
Authorization: Bearer {access_token}
{
  "session_token": "{session_token}",
  "new_phone": "9876543211"
}
```

**Save**: `otp` (or check server logs)

### 5. Step 2.2: Confirm New Number

```http
POST http://localhost:8030/api/phone-change/confirm-new-number
Authorization: Bearer {access_token}
{
  "session_token": "{session_token}",
  "otp": "5678"
}
```

**Result**: Phone number successfully changed!

---

## Notes

1. **OTP Storage**: OTP is stored in Redis and logged in server logs for development/testing.

2. **Phone Number Format**: Phone numbers are normalized (spaces and dashes removed). Must be 10-15 digits.

3. **Session Token**: Valid for 10 minutes after Step 1 completion. Must complete Step 2 within this time.

4. **OTP Expiry**: OTP expires in 3 minutes. Request a new OTP if expired.

5. **Attempt Limits**: 
   - 3 attempts per OTP verification step
   - 15-minute cooldown after max attempts
   - 10 requests per day per user

6. **Database Updates**: 
   - Updates `users.mobile`
   - Updates `members.mobile` for self profile member
   - All updates happen in a transaction

7. **Audit Logging**: All actions are logged in `phone_change_audit_logs` table for audit trail.

8. **SMS Integration**: Currently, OTP is logged but not sent via SMS. When SMS service is integrated, the OTP will be sent via SMS.

---

## Troubleshooting

### Issue: "Phone number does not match your current number"
**Solution**: Ensure `old_phone` exactly matches your registered phone number (without country code if stored that way).

### Issue: "Invalid or expired session token"
**Solution**: 
- Check if session token is correct
- Session token expires in 10 minutes - start from Step 1 again if expired
- Ensure you completed Step 1 successfully

### Issue: "OTP has expired"
**Solution**: Request a new OTP by calling the verify endpoint again.

### Issue: "Maximum 3 attempts exceeded"
**Solution**: Wait 15 minutes for the cooldown period to expire, then start the process again.

### Issue: "This phone number is already registered"
**Solution**: Choose a different phone number that is not registered in the system.

### Issue: OTP not received
**Solution**: 
- Check server logs for OTP (in development mode)
- Ensure Redis is running
- Verify phone number format is correct
- Check if SMS service is integrated (in production)

### Issue: "Session expired"
**Solution**: Complete Step 2 within 10 minutes of Step 1 completion. Start from Step 1 again if expired.

---

## Database Verification

After successful phone change, verify the updates:

```sql
-- Check users table
SELECT id, mobile FROM users WHERE id = {user_id};

-- Check members table (self profile)
SELECT id, user_id, mobile, is_self_profile 
FROM members 
WHERE user_id = {user_id} AND is_self_profile = 1;

-- Check phone_change_requests table
SELECT id, user_id, old_phone, new_phone, status, completed_at
FROM phone_change_requests
WHERE user_id = {user_id}
ORDER BY created_at DESC
LIMIT 1;

-- Check audit logs
SELECT id, request_id, action, status, success, timestamp
FROM phone_change_audit_logs
WHERE user_id = {user_id}
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Additional Resources

- **FastAPI Docs**: `http://localhost:8030/docs`
- **Alternative Docs**: `http://localhost:8030/redoc`
- **Database Models**: `PhoneChange_module/PhoneChange_model.py`
- **CRUD Operations**: `PhoneChange_module/PhoneChange_crud.py`
- **API Router**: `PhoneChange_module/PhoneChange_router.py`

---

**Last Updated**: 2025-01-17
**Module Version**: v11

