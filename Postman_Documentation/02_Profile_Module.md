# Postman Testing Documentation - Profile Module

## Base URL
```
http://localhost:8000/profile
```

## Overview
This module handles user profile management. Users can view and update their profile information including name, email, and mobile number.

---

## Endpoint 1: Get Profile

### Details
- **Method:** `GET`
- **Endpoint:** `/profile/me`
- **Description:** Get current user's profile information.

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
  "message": "Profile retrieved successfully.",
  "data": {
    "user_id": 1,
    "name": "John Doe",
    "email": "john.doe@example.com",
    "mobile": "9876543210"
  }
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
2. Set URL to: `http://localhost:8000/profile/me`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains your profile information

### Prerequisites
- Valid access token from Auth module (Verify OTP endpoint)

### Notes
- This endpoint requires authentication
- Returns the profile of the user associated with the access token

---

## Endpoint 2: Edit Profile

### Details
- **Method:** `PUT`
- **Endpoint:** `/profile/edit`
- **Description:** Update user profile. At least one field (name, email, or mobile) must be provided.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body - Update Name Only
```json
{
  "name": "John Doe Updated",
  "email": null,
  "mobile": null
}
```

### Request Body - Update Email Only
```json
{
  "name": null,
  "email": "newemail@example.com",
  "mobile": null
}
```

### Request Body - Update Mobile Only
```json
{
  "name": null,
  "email": null,
  "mobile": "9876543211"
}
```

### Request Body - Update All Fields
```json
{
  "name": "John Doe",
  "email": "john.doe@example.com",
  "mobile": "9876543210"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| name | string | **Yes** | User's full name | "John Doe" |
| email | string | **Yes** | User's email address | "john@example.com" |
| mobile | string | **Yes** | User's mobile number | "9876543210" |

### Success Response (200 OK)
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

### Error Responses

#### 400 Bad Request - No Fields Provided
```json
{
  "detail": "At least one field (name, email, or mobile) must be provided"
}
```

#### 400 Bad Request - Email Already Exists
```json
{
  "detail": "Email already exists"
}
```

#### 400 Bad Request - Mobile Already Exists
```json
{
  "detail": "Mobile number already exists"
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Create a new PUT request in Postman
2. Set URL to: `http://localhost:8000/profile/edit`
3. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
4. In Body tab, select "raw" and "JSON"
5. Paste one of the request body examples
6. Click "Send"
7. Verify the response shows updated profile information

### Prerequisites
- Valid access token from Auth module (Verify OTP endpoint)

### Notes
- At least one field must be provided in the request
- Email and mobile must be unique across all users
- If you provide the same email/mobile as your current profile, it will be accepted
- All profile updates are logged in audit trail

---

## Complete Testing Flow

### Step-by-Step Profile Testing

1. **Get Current Profile**
   - Request: `GET /profile/me`
   - Header: `Authorization: Bearer <access_token>`
   - Verify: Current profile data

2. **Update Profile - Name**
   - Request: `PUT /profile/edit`
   - Header: `Authorization: Bearer <access_token>`
   - Body: `{"name": "New Name"}`
   - Verify: Name is updated

3. **Get Updated Profile**
   - Request: `GET /profile/me`
   - Header: `Authorization: Bearer <access_token>`
   - Verify: Name is changed

4. **Update Profile - Email**
   - Request: `PUT /profile/edit`
   - Header: `Authorization: Bearer <access_token>`
   - Body: `{"email": "newemail@example.com"}`
   - Verify: Email is updated

5. **Update Profile - Mobile**
   - Request: `PUT /profile/edit`
   - Header: `Authorization: Bearer <access_token>`
   - Body: `{"mobile": "9876543211"}`
   - Verify: Mobile is updated

6. **Update All Fields**
   - Request: `PUT /profile/edit`
   - Header: `Authorization: Bearer <access_token>`
   - Body: `{"name": "John Doe", "email": "john@example.com", "mobile": "9876543210"}`
   - Verify: All fields are updated

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
user_id: (set after verify-otp)
```

### Example URL
```
{{base_url}}/profile/me
```

---

## Common Issues and Solutions

### Issue: "At least one field must be provided"
- **Solution:** Ensure at least one of name, email, or mobile is provided in the request body.

### Issue: "Email already exists"
- **Solution:** The email you're trying to use is already registered to another user. Use a different email or your current email.

### Issue: "Mobile number already exists"
- **Solution:** The mobile number you're trying to use is already registered to another user. Use a different mobile or your current mobile.

### Issue: "Not authenticated"
- **Solution:** Ensure you have a valid access token in the Authorization header with format: `Bearer <token>`.


 