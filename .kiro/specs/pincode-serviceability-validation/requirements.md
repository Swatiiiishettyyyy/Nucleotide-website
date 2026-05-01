# Requirements Document

## Introduction

This feature adds pincode-level serviceability validation to the address add and edit flow. Currently, the system validates the city name against a static Excel file (`Locations.xlsx`). This feature extends that validation to also check the submitted pincode against the `service_locations` database table. If the pincode is not found in `service_locations`, the request is rejected with the same error style as the existing city serviceability check.

## Glossary

- **Address_API**: The FastAPI endpoints in `Address_module/Address_router.py` that handle address creation and editing.
- **Address_CRUD**: The data-access layer in `Address_module/Address_crud.py` responsible for persisting and validating addresses.
- **Pincode_Validator**: The new component responsible for querying the `service_locations` table to determine whether a given pincode is serviceable.
- **service_locations**: A database table with columns `id`, `location`, `pincode`, and `city_id` (FK to `serviceable_locations.id`) that defines which pincodes are eligible for service.
- **serviceable_locations**: The existing reference table that `service_locations.city_id` points to.
- **postal_code**: The 6-digit Indian pincode submitted by the user as part of an address request.

## Requirements

### Requirement 1: Pincode Serviceability Check on Address Creation

**User Story:** As a user, I want to be told immediately if my pincode is not serviceable when I add a new address, so that I don't proceed with an unserviceable location.

#### Acceptance Criteria

1. WHEN a POST request is made to `/address/save` with a `postal_code` value, THE Address_CRUD SHALL query the `service_locations` table to check whether the `postal_code` exists.
2. IF the `postal_code` is not found in the `service_locations` table, THEN THE Address_CRUD SHALL raise an HTTP 422 error with the detail message `"Sample cannot be collected in your location. Please choose a different location."`.
3. WHEN the `postal_code` is found in the `service_locations` table, THE Address_CRUD SHALL proceed with the existing city serviceability check and subsequent address persistence.
4. THE Pincode_Validator SHALL perform a case-insensitive, whitespace-trimmed exact match on the `pincode` column of `service_locations`.

### Requirement 2: Pincode Serviceability Check on Address Edit

**User Story:** As a user, I want to be told immediately if a pincode I change my address to is not serviceable, so that I cannot save an unserviceable address.

#### Acceptance Criteria

1. WHEN a PUT request is made to `/address/edit/{address_id}` and the resolved `postal_code` (after autofill) is determined, THE Address_CRUD SHALL query the `service_locations` table to check whether the `postal_code` exists.
2. IF the resolved `postal_code` is not found in the `service_locations` table, THEN THE Address_CRUD SHALL raise an HTTP 422 error with the detail message `"Sample cannot be collected in your location. Please choose a different location."`.
3. WHEN the resolved `postal_code` is found in the `service_locations` table, THE Address_CRUD SHALL proceed with the existing city serviceability check and subsequent address persistence.

### Requirement 3: Pincode Validator Component

**User Story:** As a developer, I want a dedicated, reusable function to check pincode serviceability against the database, so that the validation logic is not duplicated across the codebase.

#### Acceptance Criteria

1. THE Pincode_Validator SHALL expose a function `is_serviceable_pincode(db: Session, pincode: str) -> bool` that returns `True` if the pincode exists in `service_locations` and `False` otherwise.
2. WHEN `is_serviceable_pincode` is called with a `pincode` that contains leading or trailing whitespace, THE Pincode_Validator SHALL strip the whitespace before querying.
3. WHEN `is_serviceable_pincode` is called with an empty string or a `None` value, THE Pincode_Validator SHALL return `False` without querying the database.
4. THE Pincode_Validator SHALL perform the lookup using a SQLAlchemy `Session` passed as a parameter, consistent with the existing dependency-injection pattern in the project.

### Requirement 4: Validation Ordering

**User Story:** As a developer, I want pincode validation to run before city validation, so that the user receives the most specific error first.

#### Acceptance Criteria

1. WHEN both pincode and city validations would fail, THE Address_CRUD SHALL raise the pincode serviceability error before the city serviceability error.
2. THE Address_CRUD SHALL perform pincode validation after confirming that `city` and `state` fields are non-empty, and before calling `is_serviceable_location`.

### Requirement 5: Error Response Consistency

**User Story:** As a frontend developer, I want the pincode serviceability error to have the same HTTP status code and message format as the city serviceability error, so that I can handle both errors with the same client-side logic.

#### Acceptance Criteria

1. THE Address_API SHALL return HTTP status code `422` for a non-serviceable pincode.
2. THE Address_API SHALL return the detail string `"Sample cannot be collected in your location. Please choose a different location."` for a non-serviceable pincode, identical to the city serviceability error message.
3. THE Address_API SHALL NOT expose internal database details (table names, column names, or query results) in the error response.
