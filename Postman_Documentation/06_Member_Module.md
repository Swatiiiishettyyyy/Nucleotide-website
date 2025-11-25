# Postman Testing Documentation - Member Module

## Base URL
```
http://localhost:8000/member
```

## Overview
This module handles member management. Members are people who will undergo DNA testing. Users can save members and view their member list. Members are required for cart operations (linked to products).

---

## Endpoint 1: Save Member

### Details
- **Method:** `POST`
- **Endpoint:** `/member/save`
- **Description:** Save or update a member. Members are linked to products when adding to cart.

### Headers
```
Content-Type: application/json
Authorization: Bearer <access_token>
```

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| category_id | integer | No | Category ID (defaults to Genetic Testing when omitted) | 1 |
| plan_type | string | No | Plan type: single, couple, or family | "single" |

### Request Body - New Member
```json
{
  "member_id": 0,
  "name": "John Doe",
  "relation": "self",
  "age": 30,
  "gender": "M",
  "dob": "1995-07-15",
  "mobile": "9876543210"
}
```

### Request Body - Update Existing Member
```json
{
  "member_id": 1,
  "name": "John Doe Updated",
  "relation": "self",
  "age": 31,
  "gender": "M",
  "dob": "1994-05-10",
  "mobile": "9876543211"
}
```

### Request Body - Minimal (Only Required Fields)
```json
{
  "member_id": 0,
  "name": "Jane Doe",
  "relation": "spouse"
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| member_id | integer | Yes | Member ID (0 for new, existing ID for update) | 0 or 1 |
| name | string | Yes | Member's full name | "John Doe" |
| relation | string | Yes | Relation to user (self, spouse, child, parent, etc.) | "self" |
| age | integer | No | Member's age (0-150) | 30 |
| gender | string | No | Gender: M, F, MALE, FEMALE, OTHER | "M" |
| dob | date (YYYY-MM-DD) | No | Date of birth. Cannot be in the future. | "1995-07-15" |
| mobile | string | No | Member's mobile number (10 digits) | "9876543210" |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Member saved successfully."
}
```

### Error Responses

#### 422 Unprocessable Entity - Invalid Age
```json
{
  "status": "error",
  "message": "Request validation failed.",
  "details": [
    {
      "source": "body",
      "field": "age",
      "message": "Age must be between 0 and 150",
      "type": "value_error"
    }
  ]
}
```

#### 422 Unprocessable Entity - Invalid Gender
```json
{
  "status": "error",
  "message": "Request validation failed.",
  "details": [
    {
      "source": "body",
      "field": "gender",
      "message": "Gender must be M, F, or Other",
      "type": "value_error"
    }
  ]
}
```

#### 422 Unprocessable Entity - Invalid Mobile
```json
{
  "status": "error",
  "message": "Request validation failed.",
  "details": [
    {
      "source": "body",
      "field": "mobile",
      "message": "Mobile number must be 10 digits",
      "type": "value_error"
    }
  ]
}
```

#### 422 Unprocessable Entity - Member Already Exists in Category
```json
{
  "detail": "Member 'John Doe' with relation 'self' already exists in the 'Genetic Testing' category."
}
```

#### 422 Unprocessable Entity - Member Already Linked to Another Plan
```json
{
  "detail": "Member 'Jane Doe' is already associated with your 'family' plan in the 'Genetic Testing' category. Remove them before assigning to another plan."
}
```

#### 404 Not Found - Member Not Found (for updates)
```json
{
  "detail": "Member not found for editing"
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
2. Set URL to: `http://localhost:8000/member/save?category_id=1&plan_type=single`
   - Query parameters are optional (omit `category_id` for the default category)
3. Set Headers:
   - `Content-Type: application/json`
   - `Authorization: Bearer <your_access_token>`
4. In Body tab, select "raw" and "JSON"
5. For new member, use `member_id: 0`
6. For updating, use existing `member_id`
7. Paste the request body JSON
8. Click "Send"
9. Save `member_id` from response (if available) or use "Get Member List" to get IDs

### Prerequisites
- Valid access token (from Auth module)

### Notes
- Use `member_id: 0` to create a new member
- Use existing `member_id` to update a member
- Relation can be: self, spouse, child, parent, sibling, etc.
- Gender accepts: M, F, MALE, FEMALE, OTHER (case-insensitive)
- Mobile must be exactly 10 digits
- Members are required before adding products to cart
- `dob` is optional but recommended; it must be a valid past date
- Members are stored per category. Use `category_id` to ensure a member is not duplicated within the same category.

---

## Endpoint 2: Get Member List

### Details
- **Method:** `GET`
- **Endpoint:** `/member/list`
- **Description:** Get list of all members for the current user. Can be filtered by category and plan_type.

### Headers
```
Authorization: Bearer <access_token>
```

### Query Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| category_id | integer | No | Filter by category | 1 |
| plan_type | string | No | Filter by plan type | "single" |

### Request Body
```
(No body required)
```

### Success Response (200 OK) - With Members
```json
{
  "status": "success",
  "message": "Member list fetched successfully.",
  "data": [
    {
      "member_id": 1,
      "name": "John Doe",
      "relation": "self",
      "age": 30,
      "gender": "M",
      "dob": "1995-07-15",
      "mobile": "9876543210"
    },
    {
      "member_id": 2,
      "name": "Jane Doe",
      "relation": "spouse",
      "age": 28,
      "gender": "F",
      "dob": "1997-03-02",
      "mobile": "9876543211"
    },
    {
      "member_id": 3,
      "name": "Child Doe",
      "relation": "child",
      "age": 5,
      "gender": "M",
      "dob": null,
      "mobile": null
    }
  ]
}
```

### Success Response (200 OK) - Empty List
```json
{
  "status": "success",
  "message": "Member list fetched successfully.",
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
2. Set URL to: `http://localhost:8000/member/list`
   - Optionally add query parameters: `?category_id=1&plan_type=single`
3. Set Headers:
   - `Authorization: Bearer <your_access_token>`
4. Click "Send"
5. Verify the response contains all your saved members

### Prerequisites
- Valid access token

### Notes
- Returns all members saved by the current user
- Returns empty array if no members exist
- Can be filtered by category (using `category_id`) and plan_type using query parameters
- Members are returned in the order they were created

---

## Complete Testing Flow

### Step-by-Step Member Testing

1. **Save New Member - Self**
   - Request: `POST /member/save?category_id=1&plan_type=single`
   - Body:
     ```json
     {
       "member_id": 0,
       "name": "John Doe",
       "relation": "self",
        "age": 30,
        "gender": "M",
        "dob": "1995-07-15",
        "mobile": "9876543210"
     }
     ```
   - Save: member_id from response (or get from list)

2. **Save New Member - Spouse (for Couple Plan)**
   - Request: `POST /member/save?category_id=1&plan_type=couple`
   - Body:
     ```json
     {
       "member_id": 0,
       "name": "Jane Doe",
       "relation": "spouse",
        "age": 28,
        "gender": "F",
        "dob": "1997-03-02",
        "mobile": "9876543211"
     }
     ```

3. **Save New Member - Child 1 (for Family Plan)**
   - Request: `POST /member/save?category_id=1&plan_type=family`
   - Body:
     ```json
     {
       "member_id": 0,
       "name": "Child One",
       "relation": "child",
        "age": 8,
        "gender": "M",
        "dob": "2017-11-01"
     }
     ```

4. **Save New Member - Child 2 (for Family Plan)**
   - Request: `POST /member/save?category_id=1&plan_type=family`
   - Body:
     ```json
     {
       "member_id": 0,
       "name": "Child Two",
       "relation": "child",
        "age": 5,
        "gender": "F",
        "dob": "2020-08-21"
     }
     ```

5. **Get Member List - All**
   - Request: `GET /member/list`
   - Verify: All 4 members are in the list

6. **Get Member List - Filtered by Plan Type**
   - Request: `GET /member/list?plan_type=single`
   - Verify: Only single plan members are returned

7. **Update Member**
   - Request: `POST /member/save`
   - Body: Use member_id from step 1 with updated fields
   - Verify: Member is updated

8. **Get Member List**
   - Request: `GET /member/list`
   - Verify: Updated member reflects changes

9. **Test Error - Invalid Age**
   - Request: `POST /member/save`
   - Body: Use age > 150 or < 0
   - Verify: 400 error with validation message

10. **Test Error - Invalid Mobile**
    - Request: `POST /member/save`
    - Body: Use mobile with != 10 digits
    - Verify: 400 error with validation message

---

## Member Requirements for Cart

> **Important:** The same member cannot be added to multiple products that belong to the *same category*. If you need to switch plans within a category, remove the older cart/order association first.

### Single Plan Product
- Requires: 1 member
- Example: `member_ids: [1]`

### Couple Plan Product
- Requires: 2 members
- Example: `member_ids: [1, 2]`

### Family Plan Product
- Requires: 4 members
- Example: `member_ids: [1, 2, 3, 4]`

### Recommended Member Setup for Testing

1. **For Single Plan Testing:**
   - Create 1 member (self)

2. **For Couple Plan Testing:**
   - Create 2 members (self, spouse)

3. **For Family Plan Testing:**
   - Create 4 members (self, spouse, child1, child2)

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
access_token: (set after verify-otp)
member_id_1: (set after creating member)
member_id_2: (set after creating member)
member_id_3: (set after creating member)
member_id_4: (set after creating member)
```

### Example URLs
```
{{base_url}}/member/save?category_id=1
{{base_url}}/member/list?plan_type=single
```

### Setting Variables in Postman Tests

Add this to "Tests" tab in "Get Member List" request:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    if (jsonData.data && jsonData.data.length > 0) {
        jsonData.data.forEach((member, index) => {
            pm.environment.set(`member_id_${index + 1}`, member.member_id);
        });
    }
}
```

---

## Common Issues and Solutions

### Issue: "Member not found for editing"
- **Solution:** Use `member_id: 0` for new members. For updates, ensure the member_id exists and belongs to you.

### Issue: "Age must be between 0 and 150"
- **Solution:** Ensure age is a valid number between 0 and 150.

### Issue: "Gender must be M, F, or Other"
- **Solution:** Use one of: M, F, MALE, FEMALE, OTHER (case-insensitive).

### Issue: "Mobile number must be 10 digits"
- **Solution:** Ensure mobile number is exactly 10 digits (e.g., "9876543210").

### Issue: "One or more members not found" (in Cart)
- **Solution:** Ensure you've created the required members before adding products to cart. Use "Get Member List" to verify member IDs.

### Issue: "Couple plan requires exactly 2 members"
- **Solution:** Ensure you provide exactly 2 member_ids when adding couple plan products to cart.

