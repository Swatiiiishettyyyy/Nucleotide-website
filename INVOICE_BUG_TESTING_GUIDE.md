# Custom PDF Invoice Testing Guide

Razorpay-hosted invoice creation has been removed. Orders still use Razorpay for payment, but invoice generation now comes from the local PDF module under `invoice generation`.

## What To Verify

### 1. Confirm the order is paid

Use an order that has:

- `order_status = CONFIRMED`
- a completed payment row
- a user email address
- persisted order items

### 2. Trigger the custom invoice email test endpoint

```bash
USER_TOKEN="user_jwt_token"
ORDER_ID=123

curl -X POST "http://localhost:8030/orders/test-invoice-email/$ORDER_ID" \
  -H "Authorization: Bearer $USER_TOKEN"
```

Expected response:

```json
{
  "status": "success",
  "message": "Invoice email sent successfully",
  "invoice_number": "INV-ORDER_NUMBER"
}
```

### 3. Check logs

Look for:

```text
Custom branded PDF invoice sent
```

If it fails, check for:

- missing service account file
- missing logo file
- missing user email
- missing order items
- Gmail API/service-account permission errors

### 4. Confirm the module path

The backend imports:

```text
Nucleotide-website/invoice generation/nucleotide_invoice_sender_wo_file.py
```

The invoice payload is built in:

```text
Nucleotide-website/Orders_module/Order_crud.py
```

The invoice number is now generated internally as:

```text
INV-{order_number}
```
