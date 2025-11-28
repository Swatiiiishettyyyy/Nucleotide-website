# Postman Testing Documentation - Product Module

## Base URL
```
http://localhost:8000/products
```

## Overview
This module handles product management. It includes endpoints to add products, view all products, and get product details.

---

## Endpoint 1: Add Product

### Details
- **Method:** `POST`
- **Endpoint:** `/products/addProduct`
- **Description:** Create a new product in the system.

### Headers
```
Content-Type: application/json
```

### Request Body
```json
{
  "Name": "DNA Test Kit - Single",
  "ShortDescription": "Starter plan for one member",
  "Description": "Complete DNA testing kit for single person",
  "Price": 5000.00,
  "SpecialPrice": 4500.00,
  "Discount": "10%",
  "Images": [
    "https://example.com/image1.jpg",
    "https://example.com/image2.jpg"
  ],
  "plan_type": "single",
  "max_members": 1,
  "category_id": 1
}
```

### Request Body Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| Name | string | **Yes** | Product name (1-200 characters) | "DNA Test Kit - Single" |
| Price | float | **Yes** | Original price (must be > 0) | 5000.00 |
| SpecialPrice | float | **Yes** | Discounted price (must be > 0) | 4500.00 |
| ShortDescription | string | **Yes** | Short description (1-500 characters) | "Starter plan for one member" |
| Description | string | **Yes** | Long form description (max 2000 characters) | "Complete DNA testing kit" |
| Discount | string | **Yes** | Display badge (eg. 10%, max 50 characters) | "10%" |
| Images | array[string] | **Yes** | List of product image URLs (at least 1 image required) | ["url1","url2"] |
| plan_type | string | **Yes** | Plan type: single/couple/family | "single" |
| max_members | integer | **Yes** | Maximum members allowed (1-4) | 1 |
| category_id | integer | **Yes** | Category ID (must be > 0) | 1 |

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Product created successfully.",
  "data": {
    "ProductId": 1,
    "Name": "DNA Test Kit - Single",
    "ShortDescription": "Starter plan for one member",
    "Description": "Complete DNA testing kit for single person",
    "Price": 5000.0,
    "SpecialPrice": 4500.0,
    "Discount": "10%",
    "Images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg"
    ],
    "plan_type": "single",
    "max_members": 1,
    "category": {
      "id": 1,
      "name": "Genetic Testing"
    }
  }
}
```

### Error Responses

#### 400 Bad Request - Validation Error
```json
{
  "detail": [
    {
      "loc": ["body", "Name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

### Testing Steps
1. Create a new POST request in Postman
2. Set URL to: `http://localhost:8000/products/addProduct`
3. Set Headers: `Content-Type: application/json`
4. In Body tab, select "raw" and "JSON"
5. Paste the request body JSON
6. Click "Send"
7. Save the `ProductId` from response for other endpoints

### Prerequisites
- None (public endpoint, but typically admin-only in production)

### Notes
- `plan_type` must be one of: "single", "couple", "family"
- `SpecialPrice` should be less than or equal to `Price`
- `Images` accepts an array of URLs (send `[]` when not available)
- Omit `category_id` to auto-use the default **Genetic Testing** category
- Use `/categories` to create/manage additional categories before assigning them to products
- Business rule: a member cannot subscribe to multiple products that belong to the same category (validated at cart level)

---

## Endpoint 2: View All Products

### Details
- **Method:** `GET`
- **Endpoint:** `/products/viewProduct`
- **Description:** Get list of all products in the system.

### Headers
```
(No headers required)
```

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Product list fetched successfully.",
  "data": [
    {
      "ProductId": 1,
      "Name": "DNA Test Kit - Single",
      "ShortDescription": "Starter plan for one member",
      "Description": "Complete DNA testing kit for single person",
      "Price": 5000.00,
      "SpecialPrice": 4500.00,
      "Discount": "10%",
      "Images": [
        "https://example.com/image1.jpg"
      ],
      "plan_type": "single",
      "max_members": 1,
      "category": {
        "id": 1,
        "name": "Genetic Testing"
      }
    },
    {
      "ProductId": 2,
      "Name": "DNA Test Kit - Couple",
      "ShortDescription": "Plan for two members",
      "Description": "Complete DNA testing kit for couple",
      "Price": 9000.00,
      "SpecialPrice": 8000.00,
      "Discount": null,
      "Images": [
        "https://example.com/image2.jpg"
      ],
      "plan_type": "couple",
      "max_members": 2,
      "category": {
        "id": 1,
        "name": "Genetic Testing"
      }
    }
  ]
}
```

### Error Responses
No specific error responses (returns empty array if no products exist)

### Testing Steps
1. Create a new GET request in Postman
2. Set URL to: `http://localhost:8000/products/viewProduct`
3. Click "Send"
4. Verify the response contains list of products

### Prerequisites
- None (public endpoint)

### Notes
- Returns all products in the system
- Empty array if no products exist
- Products are returned in the order they were created

---

## Endpoint 3: Get Product Detail

### Details
- **Method:** `GET`
- **Endpoint:** `/products/detail/{ProductId}`
- **Description:** Get detailed information about a specific product by ID.

### Headers
```
(No headers required)
```

### Path Parameters
| Parameter | Type | Required | Description | Example |
|-----------|------|----------|-------------|---------|
| ProductId | integer | Yes | Product ID | 1 |

### Request Body
```
(No body required)
```

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Product fetched successfully.",
  "data": {
    "ProductId": 1,
    "Name": "DNA Test Kit - Single",
    "ShortDescription": "Starter plan for one member",
    "Description": "Complete DNA testing kit for single person",
    "Price": 5000.00,
    "SpecialPrice": 4500.00,
    "Discount": "10%",
    "Images": [
      "https://example.com/image1.jpg",
      "https://example.com/image2.jpg"
    ],
    "plan_type": "single",
    "max_members": 1,
    "category": {
      "id": 1,
      "name": "Genetic Testing"
    }
  }
}
```

### Error Responses

#### 404 Not Found - Product Not Found
```json
{
  "detail": "Product not found"
}
```

### Testing Steps
1. Create a new GET request in Postman
2. Set URL to: `http://localhost:8000/products/detail/1`
   - Replace `1` with the actual ProductId you want to view
3. Click "Send"
4. Verify the response contains the product details

### Prerequisites
- Valid ProductId (you can get this from "View All Products" endpoint)

### Notes
- ProductId must exist in the system
- Returns 404 if product not found

---

## Endpoint 4: List Categories

### Details
- **Method:** `GET`
- **Endpoint:** `/categories`
- **Description:** Fetch all product categories (defaults include "Genetic Testing").

### Success Response (200 OK)
```json
{
  "status": "success",
  "message": "Category list fetched successfully.",
  "data": [
    {
      "id": 1,
      "name": "Genetic Testing"
    },
    {
      "id": 2,
      "name": "Wellness"
    }
  ]
}
```

### Notes
- Use this endpoint before creating products to discover valid `category_id` values.
- The default category is auto-created if it does not exist.

---

## Endpoint 5: Create Category

### Details
- **Method:** `POST`
- **Endpoint:** `/categories`
- **Description:** Add a new category that products can be mapped to.

### Request Body
```json
{
  "name": "Wellness"
}
```

### Success Response (201 Created)
```json
{
  "status": "success",
  "message": "Category created successfully.",
  "data": {
    "id": 2,
    "name": "Wellness"
  }
}
```

### Error Responses
- `409 Conflict` if the category name already exists (case-insensitive).
- `400 Bad Request` when the name is empty/blank.

### Notes
- Names are stored exactly as sent; keep a consistent casing convention.
- After creating a new category, pass its `id` as `category_id` while creating products.

---

## Complete Testing Flow

### Step-by-Step Product Testing

1. **Add Product - Single Plan**
   - Request: `POST /products/addProduct`
   - Body: 
     ```json
     {
       "Name": "DNA Test Kit - Single",
       "ShortDescription": "Starter plan for one member",
       "Description": "Single person DNA test",
       "Price": 5000.00,
       "SpecialPrice": 4500.00,
       "plan_type": "single",
       "category_id": 1
     }
     ```
   - Save: ProductId from response

2. **Add Product - Couple Plan**
   - Request: `POST /products/addProduct`
   - Body:
     ```json
     {
       "Name": "DNA Test Kit - Couple",
       "ShortDescription": "Plan for two members",
       "Description": "Couple DNA test",
       "Price": 9000.00,
       "SpecialPrice": 8000.00,
       "plan_type": "couple",
       "category_id": 1
     }
     ```
   - Save: ProductId from response

3. **Add Product - Family Plan**
   - Request: `POST /products/addProduct`
   - Body:
     ```json
     {
       "Name": "DNA Test Kit - Family",
       "ShortDescription": "Plan for four members",
       "Description": "Family DNA test (4 members)",
       "Price": 15000.00,
       "SpecialPrice": 13000.00,
        "plan_type": "family",
        "category_id": 1
     }
     ```
   - Save: ProductId from response

4. **View All Products**
   - Request: `GET /products/viewProduct`
   - Verify: All three products are in the list

5. **Get Product Detail - Single**
   - Request: `GET /products/detail/{ProductId}` (use ProductId from step 1)
   - Verify: Product details match what was created

6. **Get Product Detail - Couple**
   - Request: `GET /products/detail/{ProductId}` (use ProductId from step 2)
   - Verify: Product details match what was created

7. **Get Product Detail - Family**
   - Request: `GET /products/detail/{ProductId}` (use ProductId from step 3)
   - Verify: Product details match what was created

8. **Test Error - Product Not Found**
   - Request: `GET /products/detail/99999`
   - Verify: 404 error with "Product not found" message

---

## Environment Variables for Postman

Use these variables in your Postman environment:

```
base_url: http://localhost:8000
product_id_single: (set after adding single product)
product_id_couple: (set after adding couple product)
product_id_family: (set after adding family product)
```

### Example URLs
```
{{base_url}}/products/viewProduct
{{base_url}}/products/detail/{{product_id_single}}
```

### Setting Variables in Postman Tests

Add this to "Tests" tab in "Add Product" request:
```javascript
if (pm.response.code === 200) {
    var jsonData = pm.response.json();
    var planType = jsonData.data.plan_type;
    if (planType === "single") {
        pm.environment.set("product_id_single", jsonData.data.ProductId);
    } else if (planType === "couple") {
        pm.environment.set("product_id_couple", jsonData.data.ProductId);
    } else if (planType === "family") {
        pm.environment.set("product_id_family", jsonData.data.ProductId);
    }
}
```

---

## Common Issues and Solutions

### Issue: "Product not found"
- **Solution:** Ensure the ProductId exists. Use "View All Products" to get valid ProductIds.

### Issue: "field required" error
- **Solution:** Ensure all required fields (Name, Price, SpecialPrice, plan_type) are provided in the request body.

### Issue: Invalid plan_type
- **Solution:** plan_type must be exactly one of: "single", "couple", or "family" (case-sensitive).

### Issue: SpecialPrice validation
- **Solution:** SpecialPrice should be less than or equal to Price. If SpecialPrice > Price, it may cause issues in cart calculations.

### Issue: Category not found
- **Solution:** Use `GET /categories` to fetch the latest IDs or omit `category_id` to fallback to the default Genetic Testing category.

