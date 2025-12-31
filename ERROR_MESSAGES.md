# System Error Messages

This document contains all user-facing error messages returned by the API endpoints across the entire system.

---

## Authentication & Authorization

### Token/Session Errors
- `"Invalid or expired access token: {error}"` (401)
- `"Token does not contain user info"` (403)
- `"Session not found"` (401)
- `"Session has been logged out"` (401)
- `"Invalid session"` (401)
- `"Invalid user ID format in token"` (400)
- `"User not found"` (404)
- `"User account is inactive"` (403)
- `"Token expired"` (401)
- `"Invalid token"` (401)
- `"Session is inactive"` (401)
- `"Member not found or doesn't belong to you"` (404)
- `"Error generating access token"` (500)

---

## OTP Module

### OTP Verification Errors
- `"OTP expired or not found"` (400)
- `"Invalid OTP. Please try again."` (400)
- `"Database error: Unable to get or create user. {error}"` (500)
- `"Database error: Unable to create session. {error}"` (500)
- `"Error generating access token. {error}"` (500)
- `"An unexpected error occurred during verification: {error}"` (500)

---

## Phone Change Module

### Old Number Verification
- `"User not found"` (400)
- `"Phone number does not match your current number"` (400)
- `"Maximum 10 phone change requests per day. Please try again tomorrow."` (400)
- `"No active phone change request found. Please start the process again."` (400)
- `"Account locked. Please try again in {seconds} seconds."` (400)
- `"Request is {status}. Please start a new phone change process."` (400)
- `"Invalid request status: {status}. Please start a new phone change process."` (400)
- `"Maximum 3 attempts exceeded. Please try again in 15 minutes."` (400)
- `"OTP has expired. Please request a new one."` (400)
- `"Invalid OTP. {remaining} attempts remaining."` (400)

### New Number Verification
- `"Invalid or expired session token"` (400)
- `"Session expired. Please start the process again."` (400)
- `"New number cannot be the same as current number"` (400)
- `"This phone number is already registered"` (400)
- `"New phone number not set"` (400)
- `"Maximum 3 attempts exceeded. Please try again in 15 minutes."` (400)
- `"OTP has expired. Please request a new one."` (400)
- `"Invalid OTP. {remaining} attempts remaining."` (400)
- `"User not found"` (400)
- `"This phone number is already registered"` (400 - during final update)
- `"Failed to complete phone number change"` (500)

### Cancel Phone Change
- `"Invalid or expired session token"` (400)
- `"Request not found"` (404)

---

## Consent Module

### General Consent Errors
- `"No member profile selected. Please select a member profile first."` (400)
- `"Product ID 11 requires partner consent. Please use /consent/partner-request endpoint."` (400)
- `"Consent product with ID {product_id} not found"` (404)
- `"Error recording consent: {error}"` (500)
- `"Error retrieving manage consent data: {error}"` (500)
- `"Error updating manage consent: {error}"` (500)

### Partner Consent Errors
- `"Partner mobile cannot be the same as your mobile number"` (400)
- `"Partner must be a registered user or a member under your account"` (400)
- `"Partner consent is only for product_id 11"` (400)
- `"Request ID is missing"` (400)
- `"Failed to store OTP"` (500)
- `"Request not found"` (404)
- `"Partner mobile does not match"` (400)
- `"Cannot verify OTP. Request status is {status}"` (400)
- `"Request has expired"` (400)
- `"OTP has expired"` (400)
- `"Failed to verify OTP"` (500)
- `"OTP not found or expired"` (400)
- `"Maximum OTP verification attempts reached. Request expired."` (400)
- `"Invalid OTP. {remaining} attempt(s) remaining."` (400)
- `"Only the requester can resend OTP"` (403)
- `"Cannot resend OTP. Partner has already verified OTP and consent has been granted."` (400)
- `"Cannot resend OTP. Partner has already verified OTP."` (400)
- `"Maximum OTP resend attempts reached. Please wait for request to expire and create a new request."` (400)
- `"Only the requester can cancel the request"` (403)
- `"Cannot cancel request. Partner has already given consent."` (400)
- `"Request has already been revoked by partner."` (400)
- `"Error initiating partner consent request: {error}"` (500)
- `"Error verifying OTP: {error}"` (500)
- `"Error resending OTP: {error}"` (500)
- `"Error cancelling request: {error}"` (500)
- `"Error retrieving request status: {error}"` (500)
- `"Active request exists for a different partner. Please cancel the existing request first."` (400)
- `"Please wait 10 minutes before creating a new request."` (400)
- `"Maximum daily request attempts reached. Please try again tomorrow."` (400)

---

## Member Module

### Member Management Errors
- `"Failed to create member"` (404)
- `"Member not found or does not belong to you"` (404)
- `"Invalid age format. Must be a number."` (422)
- `"Invalid date format for dob. Use YYYY-MM-DD format."` (422)
- `"Invalid JSON body: {error}"` (422)
- `"Error generating access token"` (500)

---

## Address Module

### Address Management Errors
- `"Address not found for editing"` (404)
- `"Address not found or does not belong to you"` (404)
- `"Address not found"` (404)

---

## Cart Module

### Cart Operation Errors
- `"Product not found"` (404)
- `"Address(es) {ids} not found or do not belong to you."` (422)
- `"One or more member IDs not found for this user."` (422)
- `"Members already associated with another product in '{category}' category."` (422)
- `"This product with the same members is already in your cart."` (422)
- `"Single plan requires exactly 1 member, got {count}."` (422)
- `"Couple plan requires exactly 2 members, got {count}."` (422)
- `"Family plan requires 3-4 members (3 mandatory + 1 optional), got {count}."` (422)
- `"Error adding items to cart: {error}"` (500)
- `"No cart items were created. This should not happen."` (500)
- `"Error adding to cart: {error}"` (500)
- `"Cart item not found"` (404)
- `"Cart item not found or already deleted"` (404)
- `"Error applying coupon: {error}"` (500)
- `"Error removing coupon: {error}"` (500)
- `"Error listing coupons: {error}"` (500)
- `"Error creating coupon: {error}"` (500)

---

## Orders Module

### Order Creation Errors
- `"Cart item has been removed. Your cart may have been cleared. Please refresh your cart and try again."` (400)
- `"Cart is empty. Add items to cart before creating order."` (400)
- `"Cart items must have valid address IDs"` (422)
- `"Address ID {id} not found or does not belong to you"` (404)
- `"{error}"` (422 - validation errors)

---

## Product Module

### Product Errors
- `"Product not found"` (404)

---

## Google Meet API

### Booking Errors
- `"Failed to save booking to database"` (500)
- `"Failed to book appointment: {error}"` (500)
- `"Failed to connect calendar. Please try again."` (500)

---

## Request Validation Errors

### FastAPI Validation
- `"Request validation failed."` (422)
- `"Validation failed."` (422)

---

## Notes

- All error messages are returned in the `detail` field of HTTPException responses
- Status codes are indicated in parentheses
- Dynamic values are shown in `{curly braces}`
- Some errors include remaining attempts or time information
- All errors are logged for audit purposes

