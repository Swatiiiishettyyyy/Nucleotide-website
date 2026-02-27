# Update Order Status (Post–Confirmation to Report Ready)

This document describes how to update an order’s status **after order confirmation**: from scheduling through to report ready. Use the same endpoint for every step in this pipeline.

## Endpoint

| Method | Path |
|--------|------|
| **PUT** | `/orders/{order_number}/status` |

Replace `{order_number}` with the order number (e.g. `ORD-2024-001234`).

## Authentication

| Header | Value |
|--------|--------|
| **X-Order-Status-Password** | `4567` (or your configured value) |

---

## Status flow (after order confirmation)

After payment is confirmed (`CONFIRMED`), the order moves through these stages until the report is ready:

| Order | Status | Description |
|-------|--------|-------------|
| 1 | `SCHEDULED` | Sample collection scheduled; technician details set |
| 2 | `SCHEDULE_CONFIRMED_BY_LAB` | Lab has confirmed the schedule |
| 3 | `SAMPLE_COLLECTED` | Sample collected from customer |
| 4 | `SAMPLE_RECEIVED_BY_LAB` | Lab has received the sample |
| 5 | `TESTING_IN_PROGRESS` | Testing is in progress |
| 6 | `REPORT_READY` | Report is ready for the customer |

---

## JSON examples by status

Use the same request shape for all updates; only `status` (and optional technician/scheduling fields) change.

### 1. SCHEDULED

Requires scheduling/technician info.

```json
{
  "status": "SCHEDULED",
  "notes": "Sample collection scheduled",
  "scheduled_date": "2025-03-01T10:00:00",
  "technician_name": "John Doe",
  "technician_contact": "+919876543210",
  "changed_by": "lab_admin"
}
```

### 2. SCHEDULE_CONFIRMED_BY_LAB

```json
{
  "status": "SCHEDULE_CONFIRMED_BY_LAB",
  "notes": "Lab confirmed the schedule",
  "changed_by": "lab_admin"
}
```

### 3. SAMPLE_COLLECTED

```json
{
  "status": "SAMPLE_COLLECTED",
  "notes": "Sample collected from customer",
  "technician_name": "John Doe",
  "technician_contact": "+919876543210",
  "changed_by": "technician"
}
```

### 4. SAMPLE_RECEIVED_BY_LAB

```json
{
  "status": "SAMPLE_RECEIVED_BY_LAB",
  "notes": "Sample received at lab",
  "changed_by": "lab_admin"
}
```

### 5. TESTING_IN_PROGRESS

```json
{
  "status": "TESTING_IN_PROGRESS",
  "notes": "Testing in progress",
  "changed_by": "lab_admin"
}
```

### 6. REPORT_READY (final stage)

```json
{
  "status": "REPORT_READY",
  "notes": "Report generated and ready for customer",
  "changed_by": "lab_admin"
}
```

---

## Optional request fields

| Field | When to use |
|-------|---------------------|
| **order_item_id** | Update only one order item; omit to update whole order. |
| **address_id** | Update all items for one address; omit to update all items. |
| **scheduled_date** | For `SCHEDULED` (ISO datetime string). |
| **technician_name** | For `SCHEDULED`, `SCHEDULE_CONFIRMED_BY_LAB`, `SAMPLE_COLLECTED`. |
| **technician_contact** | For `SCHEDULED`, `SCHEDULE_CONFIRMED_BY_LAB`, `SAMPLE_COLLECTED`. |
| **notes** | Optional text for the status change. |
| **changed_by** | Who made the change; defaults to `"system"` if omitted. |

### Order-item level update example

To update **only one order item** (for example, order item `271` in order `ORD-2024-001234`):

```json
{
  "status": "REPORT_READY",
  "order_item_id": 271,
  "notes": "Report ready for this item",
  "changed_by": "lab_admin"
}
```

This leaves other items in the order unchanged; the order-level status is then synced based on all items.

---

## Minimal JSON (any status)

For statuses that don’t need technician or scheduling details:

```json
{
  "status": "REPORT_READY"
}
```

Valid `status` values for this pipeline (case-sensitive, uppercase):

- `SCHEDULED`
- `SCHEDULE_CONFIRMED_BY_LAB`
- `SAMPLE_COLLECTED`
- `SAMPLE_RECEIVED_BY_LAB`
- `TESTING_IN_PROGRESS`
- `REPORT_READY`

---

## Example: cURL (update to REPORT_READY)

```bash
curl -X PUT "https://your-api-host/orders/ORD-2024-001234/status" \
  -H "Content-Type: application/json" \
  -H "X-Order-Status-Password: 4567" \
  -d '{"status": "REPORT_READY", "notes": "Report ready", "changed_by": "lab_admin"}'
```

---

## Response

- **200** – Status updated.
- **400** – Invalid `status` or validation error.
- **401** – Missing or wrong `X-Order-Status-Password`.
- **404** – Order or order item not found.
