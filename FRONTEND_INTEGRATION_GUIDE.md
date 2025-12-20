# Frontend Integration Guide

## Overview

This guide is for frontend developers and fullstack integrators working with the Nucleotide-website_v11 API. It provides detailed information about all API endpoints, with special focus on the Google Meet API (`/gmeet`) endpoints and OAuth callback handling.

**Base URL:** `https://your-domain.com` (or `http://localhost:8030` for development)

---

## Table of Contents

1. [Authentication](#authentication)
2. [API Endpoints Overview](#api-endpoints-overview)
3. [Google Meet API - Detailed Guide](#google-meet-api---detailed-guide)
4. [OAuth Callback Flow](#oauth-callback-flow)
5. [Frontend Implementation Examples](#frontend-implementation-examples)
6. [Error Handling](#error-handling)
7. [Testing](#testing)

---

## Authentication

### Getting an Access Token

Most endpoints require authentication via JWT tokens.

#### 1. Request OTP

```http
POST /auth/send-otp
Content-Type: application/json

{
  "phone": "+919876543210"
}
```

**Response:**
```json
{
  "status": "success",
  "message": "OTP sent successfully"
}
```

#### 2. Verify OTP

```http
POST /auth/verify-otp
Content-Type: application/json

{
  "phone": "+919876543210",
  "otp": "123456"
}
```

**Response:**
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "user_id": 123,
    "expires_in": 86400
  }
}
```

#### 3. Use Token in Requests

Include the token in the `Authorization` header:

```http
GET /profile
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

---

## API Endpoints Overview

### Core Modules

| Module | Base Path | Key Endpoints |
|--------|-----------|--------------|
| Auth | `/auth` | `POST /auth/send-otp`, `POST /auth/verify-otp` |
| Profile | `/profile` | `GET /profile`, `PUT /profile` |
| Products | `/products` | `GET /products`, `GET /products/{id}` |
| Categories | `/categories` | `GET /categories` |
| Cart | `/cart` | `GET /cart`, `POST /cart/add`, `DELETE /cart/{id}` |
| Address | `/address` | `GET /address`, `POST /address`, `PUT /address/{id}` |
| Member | `/member` | `GET /member`, `POST /member`, `PUT /member/{id}` |
| Orders | `/orders` | `POST /orders`, `GET /orders`, `GET /orders/{id}` |
| Consent | `/consent` | `GET /consent`, `POST /consent` |
| Sessions | `/sessions` | `GET /sessions`, `DELETE /sessions/{id}` |

### Google Meet API (`/gmeet`)

See [Google Meet API - Detailed Guide](#google-meet-api---detailed-guide) below.

---

## Google Meet API - Detailed Guide

The Google Meet API enables counsellors to connect their Google Calendar and allows patients to book appointments with automatic Google Meet link generation.

### Concepts

#### 1. Counsellor ID
- **6-character alphanumeric ID** (e.g., `A3X9K2`)
- Auto-generated during first OAuth connection
- Used to identify counsellors in all API calls
- Should be stored securely after OAuth completion

#### 2. OAuth Flow
- Counsellors authorize the app to access their Google Calendar
- One-time setup per counsellor
- Tokens are stored securely and auto-refreshed

#### 3. Appointment Booking
- Patients book appointments with counsellors
- System creates Google Calendar event
- Google Meet link is automatically generated
- Email invitations sent (if patient email provided)

### Endpoints

#### 1. Universal Counsellor Connect

**Endpoint:** `GET /gmeet/counsellor/connect`

**Purpose:** Initiate OAuth flow for counsellor onboarding (new or existing).

**Usage:**
```javascript
// Redirect user to this endpoint
window.location.href = 'https://api.yourapp.com/gmeet/counsellor/connect';
```

**Flow:**
1. User clicks "Connect Calendar" button
2. Frontend redirects to `/gmeet/counsellor/connect`
3. Backend redirects to Google OAuth consent screen
4. User authorizes calendar access
5. Google redirects to `/gmeet/auth/callback`
6. Backend processes OAuth and redirects to frontend success page

**Query Parameters:**
- `return_url` (optional): If `true`, returns JSON instead of redirecting (for API testing)

**Response (if `return_url=true`):**
```json
{
  "status": "success",
  "message": "Authorization URL generated...",
  "authorization_url": "https://accounts.google.com/o/oauth2/auth?...",
  "redirect_uri": "https://api.yourapp.com/gmeet/auth/callback"
}
```

**Important:** This endpoint should be called from a browser (not via fetch/AJAX) because it performs HTTP redirects.

---

#### 2. OAuth Callback (Backend Handled)

**Endpoint:** `GET /gmeet/auth/callback`

**Purpose:** Handles Google OAuth callback. **Do not call this directly from frontend.**

**How it works:**
- Google redirects here after authorization
- Backend exchanges authorization code for tokens
- Backend fetches user info from Google
- Backend creates/updates counsellor record
- Backend redirects to frontend success/error page

**Query Parameters (from Google):**
- `code`: Authorization code
- `state`: Either `"new_counsellor_signup"` or existing `counsellor_id`

**Frontend Redirects:**

If `FRONTEND_COUNSELLOR_SUCCESS_URL` is configured:
```
GET /gmeet/auth/callback?code=...&state=...
→ Redirects to: FRONTEND_COUNSELLOR_SUCCESS_URL?counsellor_id=A3X9K2&name=Dr.%20John&email=john@example.com&is_new=true
```

If `FRONTEND_COUNSELLOR_ERROR_URL` is configured (on error):
```
GET /gmeet/auth/callback?code=...&state=...&error=...
→ Redirects to: FRONTEND_COUNSELLOR_ERROR_URL?error=oauth_failed&message=Failed%20to%20connect...
```

If frontend URLs are NOT configured:
- Returns JSON response instead of redirecting

---

#### 3. Check Availability

**Endpoint:** `GET /gmeet/availability`

**Purpose:** Get available time slots for a counsellor.

**Query Parameters:**
- `counsellor_id` (required): Counsellor's 6-character ID
- `start_time` (required): ISO format datetime (e.g., `2024-12-10T09:00:00+05:30`)
- `end_time` (required): ISO format datetime (e.g., `2024-12-10T18:00:00+05:30`)

**Example Request:**
```javascript
const response = await fetch(
  `https://api.yourapp.com/gmeet/availability?counsellor_id=A3X9K2&start_time=2024-12-10T09:00:00+05:30&end_time=2024-12-10T18:00:00+05:30`
);
const data = await response.json();
```

**Response:**
```json
{
  "status": "success",
  "message": "Availability fetched successfully",
  "counsellor_id": "A3X9K2",
  "start_time": "2024-12-10T09:00:00+05:30",
  "end_time": "2024-12-10T18:00:00+05:30",
  "available_slots": [
    {
      "start": "2024-12-10T09:00:00+05:30",
      "end": "2024-12-10T09:30:00+05:30"
    },
    {
      "start": "2024-12-10T10:00:00+05:30",
      "end": "2024-12-10T10:30:00+05:30"
    }
  ]
}
```

**Frontend Implementation:**
```javascript
async function getAvailability(counsellorId, startTime, endTime) {
  const params = new URLSearchParams({
    counsellor_id: counsellorId,
    start_time: startTime,
    end_time: endTime
  });
  
  const response = await fetch(
    `https://api.yourapp.com/gmeet/availability?${params}`
  );
  
  if (!response.ok) {
    throw new Error('Failed to fetch availability');
  }
  
  return await response.json();
}
```

---

#### 4. Book Appointment

**Endpoint:** `POST /gmeet/book`

**Purpose:** Book a Google Meet appointment.

**Request Body:**
```json
{
  "counsellor_id": "A3X9K2",
  "counsellor_member_id": "MEMBER123",
  "patient_name": "John Doe",
  "patient_email": "john@example.com",
  "patient_phone": "+91-9876543210",
  "start_time": "2024-12-10T10:00:00+05:30",
  "end_time": "2024-12-10T10:30:00+05:30"
}
```

**Example Request:**
```javascript
const response = await fetch('https://api.yourapp.com/gmeet/book', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    counsellor_id: 'A3X9K2',
    counsellor_member_id: 'MEMBER123',
    patient_name: 'John Doe',
    patient_email: 'john@example.com',
    patient_phone: '+91-9876543210',
    start_time: '2024-12-10T10:00:00+05:30',
    end_time: '2024-12-10T10:30:00+05:30'
  })
});

const booking = await response.json();
```

**Response:**
```json
{
  "status": "success",
  "message": "Appointment booked successfully",
  "booking_id": 1,
  "counsellor_id": "A3X9K2",
  "counsellor_member_id": "MEMBER123",
  "google_event_id": "abc123xyz789",
  "meet_link": "https://meet.google.com/abc-defg-hij",
  "calendar_link": "https://www.google.com/calendar/event?eid=...",
  "start_time": "2024-12-10T10:00:00+05:30",
  "end_time": "2024-12-10T10:30:00+05:30",
  "patient_name": "John Doe",
  "patient_email": "john@example.com",
  "patient_phone": "+91-9876543210",
  "notifications_sent": true
}
```

**Important Fields:**
- `meet_link`: Google Meet video call link (share with patient)
- `calendar_link`: Google Calendar event link
- `booking_id`: Use this to cancel the appointment later

---

#### 5. Cancel Appointment

**Endpoint:** `DELETE /gmeet/appointment/{counsellor_id}/{booking_id}`

**Purpose:** Cancel an appointment and remove it from Google Calendar.

**Query Parameters:**
- `send_notifications` (optional): Send cancellation emails (default: `true`)

**Example Request:**
```javascript
const response = await fetch(
  `https://api.yourapp.com/gmeet/appointment/A3X9K2/1?send_notifications=true`,
  { method: 'DELETE' }
);

const result = await response.json();
```

**Response:**
```json
{
  "status": "success",
  "message": "Appointment cancelled successfully",
  "booking_id": 1,
  "counsellor_id": "A3X9K2",
  "google_event_id": "abc123xyz789",
  "notifications_sent": true
}
```

---

## OAuth Callback Flow

### Understanding the Flow

The OAuth callback flow is **automatic** - you don't need to call `/gmeet/auth/callback` directly. Here's how it works:

```
┌─────────────┐
│   Frontend  │
│   (React)   │
└──────┬──────┘
       │
       │ 1. User clicks "Connect Calendar"
       │    window.location.href = '/gmeet/counsellor/connect'
       ▼
┌─────────────────────┐
│   Backend API       │
│ /gmeet/counsellor/  │
│      connect        │
└──────┬──────────────┘
       │
       │ 2. Redirects to Google
       ▼
┌─────────────────────┐
│   Google OAuth      │
│   Consent Screen    │
└──────┬──────────────┘
       │
       │ 3. User authorizes
       │    Google redirects with code
       ▼
┌─────────────────────┐
│   Backend API       │
│ /gmeet/auth/        │
│    callback         │
└──────┬──────────────┘
       │
       │ 4. Backend processes OAuth
       │    Creates/updates counsellor
       │    Redirects to frontend
       ▼
┌─────────────────────┐
│   Frontend          │
│   Success Page      │
│   ?counsellor_id=   │
│   A3X9K2&name=...   │
└─────────────────────┘
```

### Frontend Pages Needed

You need to create **two pages** in your frontend:

#### 1. Success Page

**Route:** `/counsellor/welcome` (or your custom route)

**URL Parameters:**
- `counsellor_id` (string): Unique 6-character ID
- `name` (string): Counsellor's name from Google
- `email` (string): Counsellor's email
- `is_new` (string): `"true"` if first signup, `"false"` if returning

**Example URL:**
```
https://yourapp.com/counsellor/welcome?counsellor_id=A3X9K2&name=Dr.%20John%20Doe&email=john@example.com&is_new=true
```

**Implementation Example (React):**
```jsx
import { useSearchParams } from 'react-router-dom';

function CounsellorWelcomePage() {
  const [searchParams] = useSearchParams();
  const counsellorId = searchParams.get('counsellor_id');
  const name = searchParams.get('name');
  const email = searchParams.get('email');
  const isNew = searchParams.get('is_new') === 'true';

  const copyId = () => {
    navigator.clipboard.writeText(counsellorId);
    alert('Counsellor ID copied to clipboard!');
  };

  return (
    <div>
      <h1>{isNew ? 'Welcome! Calendar Connected!' : 'Welcome Back! Calendar Reconnected!'}</h1>
      <p>Your Google Calendar has been successfully linked.</p>
      
      <div>
        <strong>Counsellor ID:</strong> {counsellorId}
        <button onClick={copyId}>Copy</button>
      </div>
      <div><strong>Name:</strong> {name}</div>
      <div><strong>Email:</strong> {email}</div>
      
      <button onClick={() => window.location.href = '/dashboard'}>
        Go to Dashboard
      </button>
    </div>
  );
}
```

**Implementation Example (Vue):**
```vue
<template>
  <div>
    <h1>{{ isNew ? 'Welcome! Calendar Connected!' : 'Welcome Back! Calendar Reconnected!' }}</h1>
    <p>Your Google Calendar has been successfully linked.</p>
    
    <div>
      <strong>Counsellor ID:</strong> {{ counsellorId }}
      <button @click="copyId">Copy</button>
    </div>
    <div><strong>Name:</strong> {{ name }}</div>
    <div><strong>Email:</strong> {{ email }}</div>
    
    <button @click="goToDashboard">Go to Dashboard</button>
  </div>
</template>

<script>
export default {
  data() {
    return {
      counsellorId: '',
      name: '',
      email: '',
      isNew: false
    };
  },
  mounted() {
    this.counsellorId = this.$route.query.counsellor_id;
    this.name = this.$route.query.name;
    this.email = this.$route.query.email;
    this.isNew = this.$route.query.is_new === 'true';
  },
  methods: {
    copyId() {
      navigator.clipboard.writeText(this.counsellorId);
      alert('Counsellor ID copied to clipboard!');
    },
    goToDashboard() {
      this.$router.push('/dashboard');
    }
  }
};
</script>
```

#### 2. Error Page

**Route:** `/counsellor/error` (or your custom route)

**URL Parameters:**
- `error` (string): Error code (e.g., `"oauth_failed"`, `"token_error"`)
- `message` (string): Human-readable error message

**Example URL:**
```
https://yourapp.com/counsellor/error?error=oauth_failed&message=Failed%20to%20connect%20calendar.%20Please%20try%20again.
```

**Implementation Example (React):**
```jsx
import { useSearchParams } from 'react-router-dom';

function CounsellorErrorPage() {
  const [searchParams] = useSearchParams();
  const errorCode = searchParams.get('error');
  const errorMessage = searchParams.get('message');

  const tryAgain = () => {
    window.location.href = 'https://api.yourapp.com/gmeet/counsellor/connect';
  };

  return (
    <div>
      <h1>Connection Failed</h1>
      <p>{errorMessage || 'An unexpected error occurred while connecting your calendar.'}</p>
      <p>Error Code: {errorCode}</p>
      
      <button onClick={tryAgain}>Try Again</button>
      <button onClick={() => window.history.back()}>Close</button>
    </div>
  );
}
```

### Configuration

Set these environment variables in AWS App Runner:

```bash
FRONTEND_COUNSELLOR_SUCCESS_URL=https://yourapp.com/counsellor/welcome
FRONTEND_COUNSELLOR_ERROR_URL=https://yourapp.com/counsellor/error
```

**Note:** If these are not set, the backend will return JSON responses instead of redirecting (useful for API testing).

---

## Frontend Implementation Examples

### Complete OAuth Flow (React)

```jsx
import React, { useState } from 'react';

function ConnectCalendarButton() {
  const [loading, setLoading] = useState(false);

  const handleConnect = () => {
    setLoading(true);
    // Redirect to backend OAuth endpoint
    // Backend will handle the rest and redirect back to frontend
    window.location.href = 'https://api.yourapp.com/gmeet/counsellor/connect';
  };

  return (
    <button onClick={handleConnect} disabled={loading}>
      {loading ? 'Connecting...' : 'Connect Google Calendar'}
    </button>
  );
}
```

### Booking Flow (React)

```jsx
import React, { useState, useEffect } from 'react';

function AppointmentBooking({ counsellorId }) {
  const [slots, setSlots] = useState([]);
  const [selectedSlot, setSelectedSlot] = useState(null);
  const [patientInfo, setPatientInfo] = useState({
    name: '',
    email: '',
    phone: ''
  });

  // Fetch availability
  useEffect(() => {
    const fetchAvailability = async () => {
      const startTime = '2024-12-10T09:00:00+05:30';
      const endTime = '2024-12-10T18:00:00+05:30';
      
      const response = await fetch(
        `https://api.yourapp.com/gmeet/availability?counsellor_id=${counsellorId}&start_time=${startTime}&end_time=${endTime}`
      );
      
      const data = await response.json();
      setSlots(data.available_slots);
    };

    fetchAvailability();
  }, [counsellorId]);

  // Book appointment
  const handleBooking = async () => {
    const response = await fetch('https://api.yourapp.com/gmeet/book', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        counsellor_id: counsellorId,
        counsellor_member_id: 'MEMBER123', // Get from your system
        patient_name: patientInfo.name,
        patient_email: patientInfo.email,
        patient_phone: patientInfo.phone,
        start_time: selectedSlot.start,
        end_time: selectedSlot.end
      })
    });

    const booking = await response.json();
    
    if (booking.status === 'success') {
      alert(`Appointment booked! Meet link: ${booking.meet_link}`);
      // Redirect to confirmation page
    }
  };

  return (
    <div>
      <h2>Select Time Slot</h2>
      {slots.map((slot, index) => (
        <button
          key={index}
          onClick={() => setSelectedSlot(slot)}
          className={selectedSlot === slot ? 'selected' : ''}
        >
          {new Date(slot.start).toLocaleString()} - {new Date(slot.end).toLocaleString()}
        </button>
      ))}

      {selectedSlot && (
        <div>
          <input
            placeholder="Patient Name"
            value={patientInfo.name}
            onChange={(e) => setPatientInfo({ ...patientInfo, name: e.target.value })}
          />
          <input
            placeholder="Email (optional)"
            value={patientInfo.email}
            onChange={(e) => setPatientInfo({ ...patientInfo, email: e.target.value })}
          />
          <input
            placeholder="Phone"
            value={patientInfo.phone}
            onChange={(e) => setPatientInfo({ ...patientInfo, phone: e.target.value })}
          />
          <button onClick={handleBooking}>Book Appointment</button>
        </div>
      )}
    </div>
  );
}
```

---

## Error Handling

### Common Error Responses

All endpoints return consistent error formats:

```json
{
  "status": "error",
  "message": "Error description",
  "details": [...]
}
```

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (validation errors)
- `401` - Unauthorized (invalid/missing token)
- `404` - Not Found
- `422` - Unprocessable Entity (validation errors)
- `500` - Internal Server Error

### Error Handling Example

```javascript
async function bookAppointment(bookingData) {
  try {
    const response = await fetch('https://api.yourapp.com/gmeet/book', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(bookingData)
    });

    const data = await response.json();

    if (!response.ok) {
      // Handle error
      if (response.status === 400 || response.status === 422) {
        // Validation errors
        console.error('Validation errors:', data.details);
      } else if (response.status === 401) {
        // Unauthorized - redirect to login
        window.location.href = '/login';
      } else {
        // Other errors
        console.error('Error:', data.message);
      }
      throw new Error(data.message);
    }

    return data;
  } catch (error) {
    console.error('Booking failed:', error);
    throw error;
  }
}
```

---

## Testing

### Testing OAuth Flow

1. **Start OAuth:**
   ```javascript
   window.location.href = 'https://api.yourapp.com/gmeet/counsellor/connect?return_url=true';
   ```
   This returns JSON with `authorization_url` for testing.

2. **Test Callback:**
   - Use the `authorization_url` from step 1
   - Complete OAuth in browser
   - Check redirect to your frontend success page

### Testing Endpoints

Use Swagger UI for interactive testing:
```
https://api.yourapp.com/docs
```

### Postman Collection

Create a Postman collection with:
- Environment variables for base URL
- Pre-request scripts for token management
- Tests for response validation

---

## Best Practices

### 1. Store Counsellor ID Securely

After OAuth completion, store the `counsellor_id` securely:
- In your database linked to user account
- In encrypted local storage (if needed)
- Never expose in client-side logs

### 2. Handle Redirects Properly

- Use `window.location.href` for OAuth initiation (not fetch/AJAX)
- Handle popup windows if needed
- Provide clear user feedback during OAuth flow

### 3. Validate Data Before Sending

- Validate datetime formats (ISO 8601)
- Validate email formats
- Validate phone numbers
- Check required fields

### 4. Error Handling

- Always handle network errors
- Display user-friendly error messages
- Log errors for debugging
- Provide retry mechanisms

### 5. Security

- Never expose API keys or tokens in frontend code
- Use HTTPS in production
- Validate all user inputs
- Implement rate limiting on frontend (in addition to backend)

---

## Support

For API documentation and testing:
- **Swagger UI:** `https://api.yourapp.com/docs`
- **ReDoc:** `https://api.yourapp.com/redoc`

For questions or issues, contact the backend team.

