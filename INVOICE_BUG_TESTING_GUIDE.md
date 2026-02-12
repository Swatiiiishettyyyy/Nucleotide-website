# Razorpay Invoice Bug - Manual Testing Guide

## Quick Summary
The invoice API returns nothing because errors are being silently suppressed. This guide helps identify the root cause.

---

## Pre-Implementation Testing (Diagnose Root Cause)

### 1. Check Application Logs
**What to do:**
```bash
# Search for existing invoice errors
grep -r "CRITICAL: Error creating Razorpay invoice" /path/to/logs/
# OR check your logging system for this pattern
```

**What to look for:**
- Stack traces showing `BadRequestError` or `ServerError`
- Error messages like "invoice feature not enabled" or "permission denied"
- Any mention of customer_id issues

**Why:** This reveals the exact Razorpay API error being suppressed

---

### 2. Verify Razorpay Dashboard Settings
**What to do:**
1. Login to [Razorpay Dashboard](https://dashboard.razorpay.com)
2. Go to **Settings → API Keys**
3. Check the API key being used (matches `RAZORPAY_KEY_ID` in env)
4. Go to **Settings → Invoices**

**What to look for:**
- ✅ Invoice feature is **activated**
- ✅ API key has **invoice creation permissions**
- ✅ Test mode vs Production mode matches your environment

**Why:** Most common cause is missing permissions or disabled feature

---

### 3. Test Razorpay API Directly (Postman/cURL)
**What to do:**
```bash
# Get auth from Razorpay credentials
KEY_ID="your_razorpay_key_id"
KEY_SECRET="your_razorpay_key_secret"

# Step 1: Create test customer
curl -X POST https://api.razorpay.com/v1/customers \
  -u "$KEY_ID:$KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Test Customer",
    "email": "test@example.com"
  }'
# Note the customer_id from response

# Step 2: Create test invoice
curl -X POST https://api.razorpay.com/v1/invoices \
  -u "$KEY_ID:$KEY_SECRET" \
  -H "Content-Type: application/json" \
  -d '{
    "type": "invoice",
    "customer_id": "CUSTOMER_ID_FROM_STEP_1",
    "currency": "INR",
    "line_items": [{
      "name": "Test Item",
      "amount": 100,
      "currency": "INR",
      "quantity": 1
    }]
  }'
```

**What to look for:**
- ✅ **Success (200):** Invoice created with `id`, `status`, `short_url`
- ❌ **Error 400:** Check error message - likely permissions or feature not enabled
- ❌ **Error 401:** API credentials are wrong

**Why:** Confirms if the issue is with Razorpay config or application code

---

## Post-Implementation Testing (After Fix Deployed)

### 4. Test Diagnostic Endpoint
**What to do:**
```bash
# Get admin token first (login as admin user)
ADMIN_TOKEN="your_admin_jwt_token"

# Call diagnostic endpoint
curl -X GET http://localhost:8030/orders/debug/razorpay-invoice-test \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

**What to look for:**
- ✅ `"status": "success"` with test_invoice_id
- ❌ `"status": "error"` with `possible_causes` array

**Why:** New endpoint that tests invoice API with minimal payload

---

### 5. Create Test Order and Check Invoice Fields
**What to do:**
1. Place a new order via the app (small amount, ₹10)
2. Complete payment using Razorpay test card
3. Wait for webhook to fire (confirm order is CONFIRMED)
4. Query the order via API or database

**Database Query:**
```sql
SELECT
  id,
  order_number,
  order_status,
  razorpay_invoice_id,
  razorpay_invoice_number,
  razorpay_invoice_url,
  razorpay_invoice_status
FROM orders
WHERE order_number = 'YOUR_TEST_ORDER_NUMBER';
```

**What to look for:**
- ✅ **Success:** `razorpay_invoice_id` is NOT NULL, has value like `inv_xxxxx`
- ✅ **Success:** `razorpay_invoice_url` contains short URL
- ❌ **Failure:** All invoice fields are NULL (check logs for error details)

**Why:** Verifies end-to-end flow works after webhook

---

### 6. Check Enhanced Logs
**What to do:**
```bash
# Check logs during order creation
tail -f /path/to/app/logs | grep -i invoice
```

**What to look for (new log entries):**
```
INFO: Creating Razorpay invoice for order ORD-123 with customer_id=cust_xxx, amount=100
DEBUG: Invoice payload: {'type': 'invoice', 'customer_id': ...}
INFO: Razorpay invoice created: inv_xxx for order ORD-123
```

**Or if error:**
```
ERROR: Razorpay invoice bad request: ...
ERROR: Possible causes: Invalid customer_id, invoice feature not enabled, or API key lacks permissions
CRITICAL: Invoice creation failed: ... for order ORD-123
```

**Why:** New detailed logging reveals exact failure point

---

### 7. Test Manual Retry Endpoint (If Order Failed)
**What to do:**
```bash
# Find an order with NULL invoice fields
ORDER_ID=123  # Replace with actual order ID
USER_TOKEN="user_jwt_token"

curl -X POST http://localhost:8030/orders/$ORDER_ID/retry-invoice \
  -H "Authorization: Bearer $USER_TOKEN"
```

**What to look for:**
- ✅ `"status": "success"` with invoice_id and invoice_url
- ❌ Error response with specific reason

**Why:** New endpoint allows fixing failed invoices after Razorpay config is corrected

---

### 8. Verify Invoice in Razorpay Dashboard
**What to do:**
1. Login to Razorpay Dashboard
2. Go to **Invoices** section
3. Search for order number or invoice ID

**What to look for:**
- ✅ Invoice appears with correct amount
- ✅ Status shows "issued" or "paid"
- ✅ Customer name/email populated

**Why:** Confirms invoice was actually created in Razorpay system

---

## Expected Results Summary

| Test | Before Fix | After Fix |
|------|------------|-----------|
| Check logs | No errors visible (or generic errors) | Specific Razorpay error with guidance |
| Invoice fields | NULL on confirmed orders | Populated with invoice_id, url, status |
| Diagnostic endpoint | N/A (doesn't exist) | Returns success or specific error cause |
| Manual retry | N/A (doesn't exist) | Can create invoice for failed orders |
| Razorpay dashboard | No invoices created | Invoices appear correctly |

---

## Common Issues & Solutions

**Issue:** All tests show "BadRequestError - invoice feature not enabled"
**Solution:** Enable invoice feature in Razorpay Dashboard → Settings → Invoices

**Issue:** "permission denied" or "unauthorized"
**Solution:** API key lacks permissions. Generate new key with invoice permissions.

**Issue:** Customer creation works, invoice fails
**Solution:** Likely account-level restriction. Contact Razorpay support.

**Issue:** Test mode works, production fails
**Solution:** Different API keys. Verify production key has invoice permissions.

---

## Quick Checklist

- [ ] Checked application logs for existing errors
- [ ] Verified Razorpay dashboard settings (feature enabled, permissions)
- [ ] Tested direct API calls with cURL/Postman
- [ ] Deployed code changes (no database migration needed)
- [ ] Restarted application
- [ ] Tested diagnostic endpoint
- [ ] Created test order and verified invoice fields populated
- [ ] Checked enhanced logs show detailed errors
- [ ] Verified invoice appears in Razorpay dashboard
- [ ] Tested manual retry endpoint on failed order

---

**Need Help?** Check the main plan file for detailed technical context.
