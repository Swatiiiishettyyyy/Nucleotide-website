# User-Friendly Error Messages

This document contains all user-facing error messages rewritten in simple, easy-to-understand language for non-technical users.

---

## Login & Account Access

### Login Issues
- **"Your login session has expired. Please log in again."** (401)
- **"We couldn't verify your account. Please log in again."** (401)
- **"You have been logged out. Please log in again."** (401)
- **"Your account information is missing. Please log in again."** (403)
- **"Your account has been deactivated. Please contact support."** (403)
- **"We couldn't find your account. Please try logging in again."** (404)
- **"Something went wrong while logging you in. Please try again."** (500)
- **"We couldn't find the profile you selected. Please select a different profile."** (404)

---

## OTP (One-Time Password) Verification

### OTP Issues
- **"The OTP code has expired. Please request a new one."** (400)
- **"The OTP code you entered is incorrect. Please try again."** (400)
- **"We're having trouble processing your request. Please try again in a few moments."** (500)
- **"Something went wrong while verifying your OTP. Please try again."** (500)

### OTP Success Messages
- **"OTP sent successfully."** (200)
- **"OTP verified successfully."** (200)

---

## Phone Number Change

### Step 1: Verifying Your Current Phone Number
- **"The phone number you entered doesn't match your current number. Please check and try again."** (400)
- **"You've reached the daily limit for phone number changes. Please try again tomorrow."** (400)
- **"We couldn't find your phone change request. Please start the process again."** (400)
- **"Your account is temporarily locked. Please try again in a few minutes."** (400)
- **"Your previous request has expired. Please start again."** (400)
- **"You've entered the wrong OTP code too many times. Please wait 15 minutes and try again."** (400)
- **"The OTP code has expired. Please request a new one."** (400)
- **"The OTP code you entered is incorrect. You have {remaining} more attempts."** (400)

### Step 2: Verifying Your New Phone Number
- **"Your verification session has expired. Please start again."** (400)
- **"Your new phone number cannot be the same as your current number."** (400)
- **"This phone number is already registered with another account."** (400)
- **"We couldn't find your verification session. Please start the process again."** (400)
- **"You've entered the wrong OTP code too many times. Please wait 15 minutes and try again."** (400)
- **"The OTP code has expired. Please request a new one."** (400)
- **"The OTP code you entered is incorrect. You have {remaining} more attempts."** (400)
- **"We couldn't complete your phone number change. Please try again."** (500)

### Canceling Phone Number Change
- **"We couldn't find your phone change request"** (404)

### Phone Number Change Success Messages
- **"OTP sent successfully to your current phone number."** (200)
- **"Current phone number verified successfully."** (200)
- **"OTP sent successfully to your new phone number."** (200)
- **"Phone number changed successfully."** (200)
- **"Phone change process cancelled successfully."** (200)

---

## Consent Management

### General Consent Issues
- **"Please select a family member profile first."** (400)
- **"This product requires partner consent. Please use the partner consent option."** (400)
- **"We couldn't find this product. Please try again."** (404)
- **"Something went wrong while saving your consent. Please try again."** (500)
- **"Something went wrong while loading your consent settings. Please try again."** (500)
- **"Something went wrong while updating your consent. Please try again."** (500)

### Partner Consent (Child Simulator)
- **"You cannot use your own phone number as the partner's number."** (400)
- **"The partner must be a registered user or added as a family member in your account."** (400)
- **"Partner consent is only available for the Child Simulator product."** (400)
- **"We couldn't find your consent request. Please try again."** (404)
- **"The partner's phone number doesn't match. Please check and try again."** (400)
- **"This request has expired. Please create a new request."** (400)
- **"The OTP code has expired. Please request a new one."** (400)
- **"Something went wrong while verifying the OTP. Please try again."** (500)
- **"The OTP code is missing or has expired. Please request a new one."** (400)
- **"You've entered the wrong OTP code too many times. This request has expired."** (400)
- **"The OTP code you entered is incorrect. You have {remaining} more attempt(s)."** (400)
- **"Only the person who created the request can resend the OTP."** (403)
- **"Cannot resend OTP. The partner has already verified and given consent."** (400)
- **"Cannot resend OTP. The partner has already verified the OTP."** (400)
- **"You've reached the maximum number of OTP resends. Please wait for the request to expire and try again."** (400)
- **"Only the person who created the request can cancel it."** (403)
- **"Cannot cancel this request. The partner has already given consent."** (400)
- **"This request has already been cancelled by the partner."** (400)
- **"Something went wrong while creating the partner consent request. Please try again."** (500)
- **"Something went wrong while verifying the OTP. Please try again."** (500)
- **"Something went wrong while resending the OTP. Please try again."** (500)
- **"Something went wrong while canceling the request. Please try again."** (500)
- **"Something went wrong while checking the request status. Please try again."** (500)
- **"You already have an active request for a different partner. Cancel the existing request first."** (400)
- **"Please wait 10 minutes before creating a new request."** (400)
- **"You've reached the daily limit for partner consent requests. Please try again tomorrow."** (400)

---

## Family Member Management

### Member Profile Issues
- **"We couldn't create the family member profile. Please try again."** (404)
- **"We couldn't find this family member profile, or it doesn't belong to your account."** (404)
- **"Please enter a valid age (numbers only)."** (422)
- **"Please enter the date of birth in the format: YYYY-MM-DD (for example: 1990-01-15)."** (422)
- **"The information you provided is not in the correct format. Please check and try again."** (422)
- **"Cannot edit '{member_name}' right now. This member is in your cart for {product_names}. Remove from cart first."** (422)
- **"'{member_name}' with relation '{relation}' already exists in the '{category_name}' category. This member is already there."** (422) - *When trying to add duplicate member with same name and relation*
- **"Something went wrong while processing your request. Please try again."** (500)

### Member Success Messages
- **"Family member saved successfully."** (200)
- **"Family member updated successfully."** (200)
- **"Family member deleted successfully."** (200)

---

## Address Management

### Address Issues
- **"We couldn't find the address you're trying to edit."** (404)
- **"We couldn't find this address, or it doesn't belong to your account."** (404)
- **"We couldn't find this address."** (404)
- **"Cannot edit this address right now. It's being used in your cart for {product_names}. Remove from cart first."** (422)
- **"Sample cannot be collected in your location. Please choose a different location."** (422) - *When city is not in serviceable locations list*

### Address Success Messages
- **"Address saved successfully."** (200)
- **"Address updated successfully."** (200)
- **"Address deleted successfully."** (200)

---

## Shopping Cart

### Cart Issues
- **"We couldn't find this product."** (404)
- **"One or more addresses you selected are not found or don't belong to your account."** (422)
- **"One or more family members you selected are not found in your account."** (422)
- **"You cannot add the same family member twice for this product. Each member can only be added once."** (422)
- **"'{member_name}' is already added to another product in '{category_name}'. This member is already there. Remove from the other product first or choose a different member."** (422) - *When a single member conflicts with another product in the same category*
- **"These members ({member_names}) are already added to another product in '{category_name}'. These members are already there. Remove from the other product first or choose different members."** (422) - *When multiple members conflict with another product in the same category*
- **"This product with the same family members is already in your cart."** (422)
- **"Single plan requires exactly 1 family member. You selected {count}."** (422)
- **"Couple plan requires exactly 2 family members. You selected {count}."** (422)
- **"Family plan requires 3 to 4 family members (3 required + 1 optional). You selected {count}."** (422)
- **"Something went wrong while adding items to your cart. Please try again."** (500)
- **"We couldn't add items to your cart. Please try again."** (500)
- **"We couldn't find this item in your cart."** (404)
- **"This item has already been removed from your cart."** (404)
- **"We couldn't find this item in your cart to update."** (404) - *When trying to update a cart item*
- **"Something went wrong while updating your cart item. Please try again."** (500) - *When cart update fails*
- **"Something went wrong while applying the coupon. Please try again."** (500)
- **"Something went wrong while removing the coupon. Please try again."** (500)
- **"Something went wrong while loading available coupons. Please try again."** (500)
- **"Something went wrong while creating the coupon. Please try again."** (500)

### Cart Success Messages
- **"Product added to cart successfully."** (200)
- **"Cart item updated successfully."** (200) - *When updating cart item quantity*
- **"Cart item removed successfully."** (200) - *When deleting cart item*
- **"Cart cleared successfully."** (200)

---

## Order Placement

### Order Issues
- **"This item has been removed from your cart. Please refresh and try again."** (400)
- **"Your cart is empty. Please add items to your cart before placing an order."** (400)
- **"Your cart items need valid addresses. Please check your addresses and try again."** (422)
- **"We couldn't find this address, or it doesn't belong to your account."** (404)
- **"Please check the information you entered and try again."** (422)

---

## Products

### Product Issues
- **"We couldn't find this product."** (404)

---

## Appointment Booking

### Booking Issues
- **"We couldn't save your appointment. Please try again."** (500)
- **"We couldn't book your appointment. Please try again."** (500)
- **"We couldn't connect to your calendar. Please try again."** (500)

---

## Form Validation Errors

### Input Validation
- **"Please check the information you entered. Some fields are missing or incorrect."** (422)
- **"The information you provided is not valid. Please check and try again."** (422)

---

## General Guidelines for User-Friendly Messages

### Principles Used:
1. **Avoid Technical Terms**: Replaced "token", "session", "request_id", "database" with plain language
2. **Clear Action Steps**: Tell users what they can do to fix the issue
3. **Friendly Tone**: Use "we" and "you" to make it conversational
4. **Specific Guidance**: Include what went wrong and how to fix it
5. **Time Information**: Convert seconds to minutes/hours where helpful
6. **Remaining Attempts**: Show how many tries are left
7. **No Jargon**: Avoid terms like "HTTP", "status code", "endpoint", etc.

### Message Format:
- Start with what happened (problem)
- Explain why it happened (if helpful)
- Tell them what to do next (solution)
- Be empathetic and helpful
- Keep messages short (under 120 characters for frontend display)

---

## Implementation Notes

When implementing these messages:
- Replace technical error messages with these user-friendly versions
- Keep the same HTTP status codes
- Maintain dynamic values like `{remaining}`, `{count}`, `{member_name}`, `{product_names}`, etc.
- Test that all error scenarios are covered
- Ensure messages are consistent across the application
- Messages are optimized for frontend display (concise and clear)
- Success messages (200 status) should be positive and confirm the action completed

