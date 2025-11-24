# Postman Testing Documentation - Address Module

## Base URL
```
http://localhost:8000/address
```

## Overview
This module handles user address management. Users can save addresses, view their address list, and delete addresses. Addresses are required for cart operations and orders.

---

## Endpoint 1: Save Address

### Details
- **Method:** `POST`
- **Endpoint:** `/address/save`
- **Description:** Save or update an address. City and state are auto-filled from pincode if not provided.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Request Body - New Address
```json
{
  "address_id": 0,
  "address_label": "Home",
  "street_address": "123 Main Street",
  "landmark": "Near Park",
  "locality": "Lower Parel",
  "city": "Mumbai",
  "state": "Maharashtra",
  "postal_code": "400001",
  "country": "India",
  "save_for_future": true
}
```

### Request Body - Update Existing Address
```json
{
  "address_id": 1,
  "address_label": "Office",
  "street_address": "456 Business Park",
  "landmark": "Building A",
  "locality": "Connaught Place",
  "city": "Delhi",
  "state": "Delhi",
  "postal_code": "110001",
  "country": "India",
  "save_for_future": true
}
```

### Request Body - Auto-fill City/State from Pincode
```json
{
  "address_id": 0,
  "address_label": "Home",
  "street_address": "789 Residential Area",
  "landmark": null,
  "locality": null,
  "city": null,
  "state": null,
  "postal_code": "400001",
  "country": "India",
  "save_for_future": true
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| address_id | integer | Yes | Address ID (0 for new, existing ID for update) | 0 or 1 |
| address_label | string | Yes | Label for address (Home, Office, etc.) | "Home" |
| street_address | string | Yes | Street address | "123 Main Street" |
| landmark | string | No | Nearby landmark | "Near Park" |
| locality | string | No | Specific area/region (auto-filled; pick from pincode options) | "Whitefield" |
| city | string | No | City (auto-filled from pincode if not provided) | "Mumbai" |
| state | string | No | State (auto-filled from pincode if not provided) | "Maharashtra" |
| postal_code | string | Yes | 6-digit pincode | "400001" |
| country | string | No | Country (default: "India") | "India" |
| save_for_future | boolean | No | Save address for future use (default: true) | true |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Address saved successfully.",
  "data": {
    "address_id": 1,
    "user_id": 1,
    "address_label": "Home",
    "street_address": "123 Main Street",
    "landmark": "Near Park",
    "locality": "Lower Parel",
    "city": "Mumbai",
    "state": "Maharashtra",
    "postal_code": "400001",
    "country": "India",
    "save_for_future": true
  },
  "locality_options": [
    {
      "name": "Lower Parel",
      "branch_type": "Sub Office",
      "delivery_status": "Delivery"
    },
    {
      "name": "Worli",
      "branch_type": "Sub Office",
      "delivery_status": "Delivery"
    }
  ]
}
```

### Error Responses

#### 400 Bad Request - Invalid Pincode
```json
{
  "detail": [
    {
      "loc": ["body", "postal_code"],
      "msg": "Postal code must be 6 digits",
      "type": "value_error"
    }
  ]
}
```

#### 404 Not Found - Address Not Found (for updates)
```json
{
  "detail": "Address not found for editing"
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
2. Set URL to: `http://localhost:8000/address/save`
3. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
4. In Body tab, select "raw" and "JSON"
5. For new address, use `address_id: 0`
6. For updating, use existing `address_id`
7. Paste the request body JSON
8. Click "Send"
9. Save `address_id` from response for cart/order operations

### Prerequisites
- Valid access token (from Auth module)

### Notes
- Use `address_id: 0` to create a new address
- Use existing `address_id` to update an address
- City, state, and locality are auto-filled from pincode if not provided. The save response includes `locality_options` so you can prompt the user to pick the exact area (e.g., Whitefield, Koramangala, etc.)
- Pincode must be exactly 6 digits
- Address is required before adding items to cart

---

## Endpoint 2: Get Address List

### Details
- **Method:** `GET`
- **Endpoint:** `/address/list`
- **Description:** Get all addresses saved by the current user.

### Headers
```
Authorization: Bearer <access_token>
```

### Request Body
```
(No body required)
```

### Success Response (200 OK) - With Addresses
```json
{
  "status": "success",
  "message": "Address list fetched successfully.",
  "data": [
    {
      "address_id": 1,
      "user_id": 1,
      "address_label": "Home",
      "street_address": "123 Main Street",
      "landmark": "Near Park",
      "locality": "Lower Parel",
      "city": "Mumbai",
      "state": "Maharashtra",
      "postal_code": "400001",
      "country": "India",
      "save_for_future": true
    },
    {
      "address_id": 2,
      "user_id": 1,
      "address_label": "Office",
      "street_address": "456 Business Park",
      "landmark": "Building A",
      "locality": "Connaught Place",
      "city": "Delhi",
      "state": "Delhi",
      "postal_code": "110001",
      "country": "India",
      "save_for_future": true
    }
  ]
}
```

### Success Response (200 OK) - Empty List
```json
{
  "status": "success",
  "message": "Address list fetched successfully.",
  "data": []
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
2. Set URL to: `http://localhost:8000/address/list`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains all your saved addresses

### Prerequisites
- Valid access token

### Notes
- Returns all addresses saved by the current user
- Returns empty array if no addresses exist
- Addresses are returned in the order they were created

---

## Endpoint 3: Lookup Pincode Details

### Details
- **Method:** `GET`
- **Endpoint:** `/address/pincode/{postal_code}`
- **Description:** Fetch city, state, and all available localities for a given 6-digit pincode.

### Headers
```
(No authentication required)
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| postal_code | string | Yes | 6-digit pincode | `560001` |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Pincode details fetched successfully.",
  "data": {
    "city": "Bangalore",
    "state": "Karnataka",
    "localities": [
      {
        "name": "Whitefield",
        "branch_type": "Sub Office",
        "delivery_status": "Delivery",
        "district": "Bangalore",
        "state": "Karnataka",
        "pincode": "560066"
      },
      {
        "name": "Koramangala",
        "branch_type": "Sub Office",
        "delivery_status": "Delivery",
        "district": "Bangalore",
        "state": "Karnataka",
        "pincode": "560034"
      }
    ]
  }
}
```

### Error Responses
- **400 Bad Request:** Postal code is not exactly 6 digits.
- **404 Not Found:** No city/state data found for the provided pincode.

### Notes
- Use this endpoint to populate a locality drop-down before saving an address.
- Responses are cached, so repeated lookups for the same pincode are fast.

---

## Endpoint 4: Delete Address

### Details
- **Method:** `DELETE`
- **Endpoint:** `/address/delete/{address_id}`
- **Description:** Delete an address. Prevents deletion if address is linked to cart items.

### Headers
```
Authorization: Bearer <access_token>
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| address_id | integer | Yes | Address ID to delete | 1 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Address deleted successfully."
}
```

### Error Responses

#### 404 Not Found - Address Not Found
```json
{
  "detail": "Address not found"
}
```

#### 400 Bad Request - Address Linked to Cart
```json
{
  "detail": "This address is linked to 2 item(s) in your cart. Please remove it from cart items before deleting."
}
```

#### 401 Unauthorized - Missing/Invalid Token
```json
{
  "detail": "Not authenticated"
}
```

### Testing Steps
1. Ensure you have an address (use "Save Address" or "Get Address List")
2. Ensure the address is not linked to any cart items
3. Create a new DELETE request in Postman
4. Set URL to: `http://localhost:8000/address/delete/1`
   - Replace `1` with your actual address_id
5. Set Headers:
   - `Authorization: Bearer <your_access_token>`
6. Click "Send"
7. Verify the address is deleted (use "Get Address List" to confirm)

### Prerequisites
- Valid access token
- Address must exist and belong to the user
- Address must not be linked to any cart items

### Notes
- Cannot delete address if it's linked to cart items
- Remove address from cart items first, then delete
- This action cannot be undone

---

## Complete Testing Flow

### Step-by-Step Address Testing

1. **Save New Address - Home**
   - Request: `POST /address/save`
   - Body: 
     ```json
     {
       "address_id": 0,
       "address_label": "Home",
       "street_address": "123 Main Street",
       "landmark": "Near Park",
       "postal_code": "400001",
       "country": "India",
       "save_for_future": true
     }
     ```
   - Save: address_id from response

2. **Save New Address - Office (Auto-fill City/State)**
   - Request: `POST /address/save`
   - Body:
     ```json
     {
       "address_id": 0,
       "address_label": "Office",
       "street_address": "456 Business Park",
       "postal_code": "110001",
       "country": "India",
       "save_for_future": true
     }
     ```
   - Verify: City and state are auto-filled from pincode
   - Save: address_id from response

3. **Get Address List**
   - Request: `GET /address/list`
   - Verify: Both addresses are in the list

4. **Update Address**
   - Request: `POST /address/save`
   - Body: Use address_id from step 1 with updated fields
   - Verify: Address is updated

5. **Get Address List**
   - Request: `GET /address/list`
   - Verify: Updated address reflects changes

6. **Delete Address (if not in cart)**
   - Request: `DELETE /address/delete/{address_id}`
   - Verify: Address is deleted

7. **Get Address List**
   - Request: `GET /address/list`
   - Verify: Deleted address is no longer in list

8. **Test Error - Invalid Pincode**
   - Request: `POST /address/save`
   - Body: Use invalid pincode (e.g., "12345")
   - Verify: 400 error with validation message

9. **Test Error - Delete Address Linked to Cart**
   - Add item to cart using an address
   - Request: `DELETE /address/delete/{address_id}`
   - Verify: 400 error with message about cart items

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
address_id: (set after creating address)
```

### Example URLs
```
{{base_url}}/address/save
{{base_url}}/address/list
{{base_url}}/address/delete/{{address_id}}
```

### Setting Variables in Postman Tests

Add this to "Tests" tab in "Save Address" request:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    pm.environment.set("address_id", jsonData.data.address_id);
}
```

---

## Common Issues and Solutions

### Issue: "Postal code must be 6 digits"
- **Solution:** Ensure pincode is exactly 6 digits (e.g., "400001", not "40001" or "4000012").

### Issue: "Address not found for editing"
- **Solution:** Use `address_id: 0` for new addresses. For updates, ensure the address_id exists and belongs to you.

### Issue: "This address is linked to X item(s) in your cart"
- **Solution:** Remove all cart items using this address first, then delete the address.

### Issue: "Address not found"
- **Solution:** Ensure the address_id exists and belongs to you. Use "Get Address List" to get valid address IDs.

### Issue: City/State not auto-filled
- **Solution:** Ensure the pincode is valid. Some pincodes may not have city/state data. You can manually provide city and state.

