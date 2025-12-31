# Consent Module Testing Guide

This guide provides comprehensive testing instructions for the Consent Module API endpoints.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Authentication Setup](#authentication-setup)
3. [Test Data Setup](#test-data-setup)
4. [Testing Regular User Consent](#testing-regular-user-consent)
5. [Testing Partner Consent (Product 11)](#testing-partner-consent-product-11)
6. [Testing Manage Consent Page](#testing-manage-consent-page)
7. [Error Scenarios](#error-scenarios)
8. [API Endpoints Reference](#api-endpoints-reference)
9. [Test Checklist](#test-checklist)

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

3. **Redis**: Ensure Redis is running (required for OTP functionality)
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

All consent endpoints require authentication via JWT token.

### Step 1: Request OTP

```http
POST http://localhost:8030/auth/send-otp
Content-Type: application/json

{
  "phone": "+919876543210"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully"
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

### Step 3: Set Active Member Profile

Before testing consent endpoints, ensure you have selected an active member profile:

```http
PUT http://localhost:8030/member/select/{member_id}
Authorization: Bearer {access_token}
```

**Note**: All consent operations are member-scoped. You must have a member profile selected.

---

## Test Data Setup

### 1. Ensure Consent Products Exist

The consent system requires products to be available in the `consent_products` table.

**Product IDs:**
- Products 1-10: Regular consent products
- Product 11: Partner consent (Child simulator) - requires special handling
- Products 12-17: Regular consent products

### 2. Create Test Member Profile

```http
POST http://localhost:8030/member
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "name": "Test User",
  "dob": "1990-01-01",
  "gender": "male",
  "relationship": "self",
  "mobile": "+919876543210"
}
```

### 3. For Partner Consent Testing

You'll need:
- **User Account**: Your main user account
- **Partner Account**: A separate user account OR a member under the same user account
- **Partner Mobile**: Partner's mobile number for OTP verification

---

## Testing Regular User Consent

### Endpoint: `POST /consent/record`

This endpoint records consent for products 1-10 and 12-17 (NOT product 11).

### Test Case 1: Record Consent (Yes)

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 1,
  "consent_value": "yes",
  "consent_source": "product"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Consent recorded successfully.",
  "data": {
    "id": 1,
    "user_id": 1,
    "user_phone": "+919876543210",
    "product_id": 1,
    "product": "Product Name",
    "consent_given": 1,
    "consent_source": "product",
    "status": "yes",
    "created_at": "2025-01-17T10:00:00",
    "updated_at": null
  }
}
```

### Test Case 2: Update Consent (No)

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 1,
  "consent_value": "no",
  "consent_source": "product"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Consent declined successfully.",
  "data": {
    "id": 1,
    "status": "no",
    ...
  }
}
```

### Test Case 3: Record Consent for New Product

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 2,
  "consent_value": "yes",
  "consent_source": "product"
}
```

### Test Case 4: Decline Consent (No Record Exists)

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 3,
  "consent_value": "no",
  "consent_source": "product"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Consent declined. No record stored.",
  "data": null
}
```

### Test Case 5: Reactivate Consent

1. First, record "no" consent
2. Then, record "yes" consent

**Expected**: Status should change from "no" to "yes"

---

## Testing Partner Consent (Product 11)

Product 11 requires partner consent via OTP-based dual consent flow.

### Partner Consent Endpoint

**`/consent/partner-request` (OTP-Based Flow)**
- **Use this when:** User wants to initiate partner consent request (calling this endpoint means user has consented)
- **Flow:**
  1. User initiates request (implicitly consents by calling this endpoint) and provides partner mobile number
  2. System sends OTP to partner's mobile
  3. Partner verifies OTP → **Automatically grants consent** (no separate decision step needed)
- **Do NOT include `user_consent`** - calling this endpoint means user has already consented
- **Note:** OTP verification automatically means partner has consented. No separate consent decision endpoint is needed.

### Partner Consent Flow (OTP-Based)

1. **User initiates request** → User consents by calling the endpoint, request created with OTP sent to partner
2. **Partner verifies OTP** → Confirms partner identity and **automatically grants consent**
3. **Both have consented** → `final_status = "yes"` is automatically set when OTP is verified

### Test Case 1: Partner Consent Flow with OTP (Recommended Flow)

**Flow Overview:**
1. User initiates request (calling this endpoint means user has consented)
2. System sends OTP to partner's mobile
3. Partner verifies OTP → **Automatically grants consent** (no separate decision step)

**Note:** Calling `/consent/partner-request` endpoint means the user has already consented. If user wants to decline, they simply don't call this endpoint.

**Prerequisites:**
- Partner must be either:
  - A registered user (has user account)
  - OR a member under the same user account

#### Step 1: User Initiates Partner Consent Request

```http
POST http://localhost:8030/consent/partner-request
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 11,
  "partner_mobile": "+919876543211",
  "partner_name": "Partner Name"
}
```

**Note:** 
- Do NOT include `user_consent` field - calling this endpoint means user has already consented
- Do NOT include `partner_consent` field - partner will give consent after OTP verification

**Expected Response:**
```json
{
  "status": "success",
  "message": "OTP sent to partner at +919876543211 (OTP: 1234 - for testing only)",
  "data": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "partner_mobile": "+919876543211",
    "partner_name": "Partner Name",
    "request_expires_at": "2025-01-17T11:00:00",
    "otp_expires_at": "2025-01-17T10:03:00",
    "otp": "1234",
    "_test_mode": true,
    "_note": "⚠️ TESTING MODE: OTP included in response. Remove in production when Twilio is integrated."
  }
}
```

**Save the `request_id` for next steps.**

#### Step 2: Partner Verifies OTP

```http
POST http://localhost:8030/consent/partner-verify-otp
Content-Type: application/json

{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "partner_mobile": "+919876543211",
  "otp": "1234"
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "OTP verified successfully. Partner consent has been automatically recorded.",
  "data": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "request_status": "CONSENT_GIVEN",
    "partner_mobile": "+919876543211",
    "partner_consent": "yes",
    "final_status": "yes"
  }
}
```

**Note:** OTP verification automatically grants partner consent. No separate consent decision step is required.

### Test Case 2: Self-Consent Prevention

```http
POST http://localhost:8030/consent/partner-request
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 11,
  "partner_mobile": "+919876543210",
  "partner_name": "Self"
}
```

**Note:** Using your own mobile number as partner mobile.

**Expected Error:**
```json
{
  "detail": "Partner mobile cannot be the same as your mobile number"
}
```

### Test Case 3: Invalid Partner (Partner Doesn't Exist)

```http
POST http://localhost:8030/consent/partner-request
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 11,
  "partner_mobile": "+919999999999",
  "partner_name": "Non-existent Partner"
}
```

**Expected Error:**
```json
{
  "detail": "Partner must be a registered user or a member under your account"
}
```

**Note:** The partner mobile number must belong to either:
- A registered user in the system, OR
- A member profile under your account

---

## Testing Manage Consent Page

### Endpoint 1: `GET /consent/manage`

Get all products with their consent status for the selected member.

```http
GET http://localhost:8030/consent/manage
Authorization: Bearer {access_token}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Manage consent page data retrieved successfully.",
  "data": [
    {
      "product_id": 1,
      "product_name": "Product 1",
      "has_consent": true,
      "consent_status": "yes",
      "created_at": "2025-01-17T10:00:00",
      "updated_at": null
    },
    {
      "product_id": 2,
      "product_name": "Product 2",
      "has_consent": false,
      "consent_status": "no",
      "created_at": null,
      "updated_at": null
    },
    {
      "product_id": 11,
      "product_name": "Child Simulator",
      "has_consent": true,
      "consent_status": "yes",
      "created_at": "2025-01-17T10:00:00",
      "updated_at": "2025-01-17T10:00:00"
    }
  ]
}
```

**Notes:**
- Product 11 (partner consent) status comes from `partner_consents` table
- Other products come from `user_consents` table
- `has_consent` is `true` when `consent_status == "yes"`

### Endpoint 2: `PUT /consent/manage`

Update multiple consents from the manage consent page.

```http
PUT http://localhost:8030/consent/manage
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_consents": [
    {
      "product_id": 1,
      "status": "yes"
    },
    {
      "product_id": 2,
      "status": "no"
    },
    {
      "product_id": 3,
      "status": "yes"
    }
  ]
}
```

**Expected Response:**
```json
{
  "status": "success",
  "message": "Updated 2 record(s), created 1 record(s).",
  "data": {
    "updated": 2,
    "created": 1,
    "total_processed": 3
  }
}
```

**Notes:**
- Updates existing records if they exist
- Creates new records only if `status == "yes"`
- Skips invalid product IDs
- Product 11 should NOT be included (use partner-record endpoint instead)

### Test Case: Bulk Update

1. Get current consent status: `GET /consent/manage`
2. Update multiple products: `PUT /consent/manage`
3. Verify changes: `GET /consent/manage`

---

## Error Scenarios

### 1. No Member Profile Selected

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 1,
  "consent_value": "yes"
}
```

**Expected Error:**
```json
{
  "detail": "No member profile selected. Please select a member profile first."
}
```

**Solution**: Select a member profile first.

### 2. Invalid Product ID

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 999,
  "consent_value": "yes"
}
```

**Expected Error:**
```json
{
  "detail": "Consent product with ID 999 not found"
}
```

### 3. Product 11 on Regular Endpoint

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 11,
  "consent_value": "yes"
}
```

**Expected Error:**
```json
{
  "detail": "Product ID 11 requires partner consent. Please use /consent/partner-request endpoint."
}
```

### 4. Invalid Consent Value

```http
POST http://localhost:8030/consent/record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 1,
  "consent_value": "maybe"
}
```

**Expected Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "consent_value"],
      "msg": "consent_value must be \"yes\" or \"no\"",
      "type": "value_error"
    }
  ]
}
```

### 5. Missing Partner Info (Product 11)

```http
POST http://localhost:8030/consent/partner-record
Authorization: Bearer {access_token}
Content-Type: application/json

{
  "product_id": 11,
  "user_consent": "yes"
}
```

**Expected Error:**
```json
{
  "detail": [
    {
      "loc": ["body", "partner_mobile"],
      "msg": "partner_mobile is required when user_consent is \"yes\"",
      "type": "value_error"
    }
  ]
}
```

### 6. Unauthorized Access (No Token)

```http
POST http://localhost:8030/consent/record
Content-Type: application/json

{
  "product_id": 1,
  "consent_value": "yes"
}
```

**Expected Error:**
```json
{
  "detail": "Not authenticated"
}
```

---

## API Endpoints Reference

### Regular Consent

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/consent/record` | Record consent for products 1-10, 12-17 | Yes |
| GET | `/consent/manage` | Get all products with consent status | Yes |
| PUT | `/consent/manage` | Update multiple consents | Yes |

### Partner Consent (Product 11) - OTP-Based Flow

| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/consent/partner-request` | Initiate partner consent request (sends OTP) | Yes |
| POST | `/consent/partner-verify-otp` | Partner verifies OTP (automatically grants consent) | No |
| POST | `/consent/partner-resend-otp` | Resend OTP to partner | Yes |
| POST | `/consent/partner-cancel-request` | Cancel partner consent request | Yes |
| GET | `/consent/partner-status/{request_id}` | Get partner consent request status | No |

**Note:** OTP verification (`/consent/partner-verify-otp`) now automatically grants partner consent. No separate consent decision step is required.

### Request/Response Schemas

#### ConsentRecordRequest
```json
{
  "product_id": 1,
  "consent_value": "yes",
  "consent_source": "product"
}
```

#### PartnerConsentRequestRequest (OTP Flow - Recommended)
```json
{
  "product_id": 11,
  "partner_mobile": "+919876543211",
  "partner_name": "Partner Name"
}
```
**Note:** 
- Do NOT include `user_consent` - calling this endpoint means user has already consented
- Partner consent is automatically granted when OTP is verified (no separate decision step needed)

#### PartnerVerifyOTPRequest
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "partner_mobile": "+919876543211",
  "otp": "1234"
}
```

**Note:** OTP verification automatically grants partner consent. The response will show `request_status: "CONSENT_GIVEN"` and `partner_consent: "yes"`.

#### ManageConsentRequest
```json
{
  "product_consents": [
    {
      "product_id": 1,
      "status": "yes"
    }
  ]
}
```

---

## Test Checklist

### Regular Consent (Products 1-10, 12-17)

- [ ] Record consent (yes) for new product
- [ ] Record consent (no) for existing product
- [ ] Decline consent when no record exists
- [ ] Reactivate consent (no → yes)
- [ ] Update consent source
- [ ] Handle invalid product ID
- [ ] Handle missing member profile
- [ ] Handle product 11 on regular endpoint (error)

### Partner Consent (Product 11)

- [ ] User initiates request with valid partner (registered user)
- [ ] User initiates request with valid partner (member under same account)
- [ ] Handle self-consent prevention
- [ ] Handle invalid partner (not registered/member)
- [ ] Handle missing partner mobile
- [ ] Verify partner consent flow with OTP (OTP verification automatically grants consent)
- [ ] Test request expiration
- [ ] Test OTP expiration
- [ ] Test rate limiting
- [ ] Test OTP resend functionality
- [ ] Test request cancellation
- [ ] Test consent revocation

### Manage Consent Page

- [ ] Get all products with consent status
- [ ] Verify Product 11 status comes from partner_consents
- [ ] Verify other products come from user_consents
- [ ] Update multiple consents (bulk update)
- [ ] Create new consents via bulk update
- [ ] Update existing consents via bulk update
- [ ] Handle invalid product IDs in bulk update
- [ ] Verify changes after bulk update

### Error Handling

- [ ] No authentication token
- [ ] Invalid/expired token
- [ ] No member profile selected
- [ ] Invalid product ID
- [ ] Invalid consent value
- [ ] Invalid consent source
- [ ] Missing required fields
- [ ] Partner consent validation errors

### Edge Cases

- [ ] Multiple consents for same product (should be prevented by unique constraint)
- [ ] Consent for deleted product
- [ ] Consent for deleted member
- [ ] Concurrent consent updates
- [ ] Large bulk updates (many products)

---

## Testing with cURL

### Example: Record Consent

```bash
curl -X POST "http://localhost:8030/consent/record" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_id": 1,
    "consent_value": "yes",
    "consent_source": "product"
  }'
```

### Example: Get Manage Consent Page

```bash
curl -X GET "http://localhost:8030/consent/manage" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

### Example: Update Manage Consent

```bash
curl -X PUT "http://localhost:8030/consent/manage" \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "product_consents": [
      {"product_id": 1, "status": "yes"},
      {"product_id": 2, "status": "no"}
    ]
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

## Notes

1. **Member Scoping**: All consent operations are member-scoped. Ensure you have selected a member profile before testing.

2. **Product 11**: Product 11 (Child Simulator) requires special handling via `/consent/partner-record` endpoint. Do not use `/consent/record` for Product 11.

3. **Partner Eligibility**: For partner consent, the partner must be either:
   - A registered user (has their own account)
   - OR a member under the same user account

4. **Consent Status**: 
   - `has_consent: true` means `consent_status == "yes"`
   - Declining consent when no record exists does not create a record
   - Only "yes" consents are stored initially, but status can be updated to "no"

5. **OTP Flow**: Partner consent uses OTP-based verification. Check Redis for OTP values during testing (if needed).

6. **Rate Limiting**: Partner consent has rate limiting:
   - Max 5 OTP resends per request
   - 10-minute cooldown between requests
   - Max 10 requests per 24 hours per member
   - Max 3 failed OTP verification attempts

---

## Troubleshooting

### Issue: "No member profile selected"
**Solution**: Select a member profile using `PUT /member/select/{member_id}`

### Issue: "Consent product not found"
**Solution**: Ensure consent products exist in the database. Check `consent_products` table.

### Issue: "Partner must be a registered user or member"
**Solution**: Partner must exist either as a user account or as a member under your account.

### Issue: OTP not working
**Solution**: 
- Ensure Redis is running
- Check OTP expiry (3 minutes)
- Verify OTP is stored in Redis with key: `partner_consent_otp:{request_id}`

### Issue: Database constraint errors
**Solution**: 
- Unique constraint on `(member_id, product_id)` for user_consents
- Unique constraint on `(user_member_id, product_id)` for partner_consents
- Ensure you're not creating duplicate records

---

## Additional Resources

- **FastAPI Docs**: `http://localhost:8030/docs`
- **Alternative Docs**: `http://localhost:8030/redoc`
- **Database Models**: `Consent_module/Consent_model.py`
- **CRUD Operations**: `Consent_module/Consent_crud.py`
- **Partner Consent CRUD**: `Consent_module/Partner_consent_crud.py`
- **API Router**: `Consent_module/Consent_router.py`

---

**Last Updated**: 2025-01-17
**Module Version**: v11

