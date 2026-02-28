# Gene Report Status in the Members Module

This document describes how **gene report status** and related order fields are computed and exposed in the Members module.

---

## Overview

For each member profile, the Members API exposes:

| Field | Description |
|-------|-------------|
| `gene_report_order_no` | Order number of the member’s **most recent** order whose status is **REPORT_READY**. `null` if none. |
| `gene_report_status`   | Order status of that order (typically `"REPORT_READY"`). `null` if no report-ready order. |
| `latest_order_no`      | Order number of the member’s **most recent** order (any status). |
| `latest_order_status`  | Order status of that order. |
| `has_taken_genetic_test` | Whether the member is marked as having taken a genetic test (from `GeneticTestParticipant`). |

All of these are **computed at read time** from orders and genetic-test participant data; they are not stored on the `Member` model.

---

## How It Works

### 1. Central helper: `_member_order_and_flag_fields`

**Location:** `Member_module/Member_router.py`

```python
def _member_order_and_flag_fields(db: Session, member_id: int) -> dict
```

This function:

1. Calls **GeneticTest_module.GeneticTest_crud**:
   - `get_participant_by_member_id(db, member_id)` → used for `has_taken_genetic_test`
   - `get_latest_order_for_member(db, member_id)` → used for `latest_order_no`, `latest_order_status`
   - `get_latest_report_ready_order_for_member(db, member_id)` → used for `gene_report_order_no`, `gene_report_status`

2. Returns a dict:

   - `has_taken_genetic_test`: from participant record (or `False` if no participant)
   - `latest_order_no`, `latest_order_status`: from latest order (any status)
   - `gene_report_order_no`, `gene_report_status`: from latest **REPORT_READY** order

### 2. Gene report lookup: `get_latest_report_ready_order_for_member`

**Location:** `GeneticTest_module/GeneticTest_crud.py`

```python
def get_latest_report_ready_order_for_member(db: Session, member_id: int) -> Optional[dict]
```

- Finds the **most recent** order that:
  - Has at least one **OrderItem** with `member_id` equal to the given member.
  - Has **order-level** `order_status == OrderStatus.REPORT_READY`.
- Orders by `Order.created_at` DESC, then `Order.id` DESC; returns the first row.
- Returns a dict: `order_id`, `order_number`, `order_status` (or `None` if no such order).

So **gene report** = “latest order for this member that has reached REPORT_READY”.

### 3. Latest order (any status): `get_latest_order_for_member`

**Location:** `GeneticTest_module/GeneticTest_crud.py`

```python
def get_latest_order_for_member(db: Session, member_id: int) -> Optional[dict]
```

- Same join: `Order` ↔ `OrderItem` with `OrderItem.member_id == member_id`.
- No status filter; orders by `Order.created_at` DESC, `Order.id` DESC.
- Returns `order_id`, `order_number`, `order_status` for that order (or `None`).

---

## Where These Fields Are Used

`_member_order_and_flag_fields` is used whenever member profile or list data is built:

| Endpoint / flow | Usage |
|-----------------|--------|
| Create member (`POST /member/add`) | Response includes `gene_report_*` and `latest_order_*` for the new member. |
| Edit member (`PUT /member/edit/{member_id}`) | Response includes these fields for the edited member. |
| Member list (`GET /member/list`) | Each member in `data` includes `gene_report_order_no`, `gene_report_status`, `latest_order_no`, `latest_order_status`. |
| Current member (`GET /member/current`) | Current/default member response includes these fields. |
| Select member (`POST /member/select/{member_id}`) | Response includes these fields for the selected member. |
| Photo upload/delete responses | Response payload uses a profile structure that includes `gene_report_order_no`, `gene_report_status`. |

So any API that returns member profile or list data can expose gene report status.

---

## Response shape (schemas)

- **MemberData** (`Member_schema.py`):  
  `gene_report_order_no`, `gene_report_status`, `latest_order_no`, `latest_order_status` are optional strings (or `None`).

- **MemberProfileData**:  
  Same optional fields, used in photo upload/delete and similar profile payloads.

---

## Summary

- **Gene report status** = status of the member’s **latest order that has reached REPORT_READY**.
- **Gene report order number** = that order’s `order_number`.
- Both are derived from **Orders** (and OrderItems) via `get_latest_report_ready_order_for_member` and are not stored on the Member table.
- They are computed in `_member_order_and_flag_fields` and included in member create/edit, list, current, select, and profile (e.g. photo) responses.
