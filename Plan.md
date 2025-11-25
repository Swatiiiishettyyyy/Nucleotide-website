## Task: Improve 422 Responses & Cart Duplicate Messaging

### Goals
1. Standardize 422 (validation) responses across all FastAPI modules:
   - Return HTTP 422 when request validation fails.
   - Provide clear, human-readable reasons in the response body.
2. Enhance cart duplicate-member checks so the API explicitly states which member is duplicated and which plan/category they're already associated with.

### Steps
1. **Centralized 422 Handler**
   - Add a FastAPI exception handler (likely in `main.py`) for `RequestValidationError` and `ValidationError`.
   - Format responses as `{"status": "error", "message": "...", "details": [...]}` and ensure HTTP status code 422 is preserved.
   - Include source (body/query/path), field name, and human-readable message for each validation issue.

2. **Uniform Validation Usage**
   - Review key routers (Member, Address, Cart, Orders, Profile, Auth/OTP, etc.) to ensure manual validation errors also raise HTTP 422 (instead of 400) when the issue is with user input.
   - Replace generic `"detail": "Invalid request"` errors with specifics.

3. **Cart Duplicate Messaging**
   - In `Cart_router.add_to_cart`, when checking existing cart items within the same category:
     - Gather the conflicting members (id, name, current product/plan type).
     - Raise HTTP 422 with detail spelling out each conflict, e.g., `"Member Jane Doe (ID 7) already in product 'Genome Duo' (plan: couple)."`.
     - Ensure address/member mismatch errors also use 422 with descriptive detail.

4. **Docs**
   - Update Postman documentation (Cart + Orders modules) to mention the enhanced error messages and show sample 422 responses.

5. **Testing**
   - Exercise representative endpoints (member save, cart add, order create) with invalid payloads to confirm the new 422 structure.
   - Validate duplicate-member scenario returns the new message.

## Task: Support per-member addresses & flexible family counts in cart

### Steps
1. **Schema adjustments (`Cart_module/Cart_schema.py`)**
   - Replace the single `address_id` field with support for either one shared address or an array of addresses (one per member). Normalize to a `address_ids` list via validators/root validator.
   - Update `member_ids` validation so family plans can send 3 (mandatory) or 4 (with optional slot), while single/couple keep strict counts.

2. **Cart add logic (`Cart_module/Cart_router.py`)**
   - Validate that every supplied address belongs to the current user and that the length matches allowed patterns (1 shared or len == member count).
   - Map each member to its chosen address when creating individual `CartItem` rows; update duplicate-check logic to consider member sets regardless of addresses.
   - Return the per-member address map in the response payload to confirm the associations.

3. **Cart view/update output (`Cart_module/Cart_router.py`)**
   - When grouping items in `/cart/view`, include an `addresses` section (e.g., `{member_id: address_id}`) so clients can display delivery info per member.
   - Ensure update/delete/clear logic continues to operate on group IDs without assuming a single address.

4. **Docs (`Postman_Documentation/04_Cart_Module.md` & related sections)**
   - Document the new request format (showing both shared and per-member address examples) and clarify that family plans accept 3 mandatory + 1 optional member with same/different addresses.
   - Update notes/error examples to reflect the flexible validation rules.


