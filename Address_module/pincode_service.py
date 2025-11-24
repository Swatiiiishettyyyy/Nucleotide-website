"""
Pincode service for auto-generating city and state from pincode.
Uses free postalpincode.in API with Redis caching for performance.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# API Configuration
PINCODE_API_URL = "https://api.postalpincode.in/pincode"
PINCODE_FALLBACK_API_URL = "https://postalpincode.in/api/pincode"
CACHE_TTL_SECONDS = int(os.getenv("PINCODE_CACHE_TTL", 86400))  # 24 hours default
PINCODE_REQUEST_HEADERS = {
    "User-Agent": os.getenv("PINCODE_USER_AGENT", "NucleotidePincodeService/1.0"),
    "Accept": "application/json",
}
PINCODE_SOURCES = (
    ("primary", PINCODE_API_URL),
    ("fallback", PINCODE_FALLBACK_API_URL),
)

# Try to get Redis client (if available)
_redis_client = None
try:
    from Login_module.OTP import otp_manager
    _redis_client = otp_manager._redis_client
    logger.info("Redis available for pincode caching")
except Exception as e:
    logger.warning(f"Redis not available for pincode caching: {e}")


def _get_from_cache(pincode: str) -> Optional[Dict[str, Any]]:
    """Get city/state/localities from Redis cache"""
    if not _redis_client:
        return None
    
    try:
        cache_key = f"pincode:{pincode}"
        cached = _redis_client.get(cache_key)
        if cached:
            try:
                data = json.loads(cached)
                logger.debug(f"Pincode {pincode} found in cache")
                return data
            except json.JSONDecodeError:
                # Backward compatibility for legacy "city|state" cache format
                parts = cached.split("|")
                if len(parts) >= 2:
                    logger.debug(f"Pincode {pincode} found in legacy cache format")
                    return {
                        "city": parts[0],
                        "state": parts[1],
                        "localities": []
                    }
    except Exception as e:
        logger.warning(f"Error reading from cache: {e}")
    
    return None


def _save_to_cache(pincode: str, city: str, state: str, localities: List[Dict[str, Any]]):
    """Save city/state/localities to Redis cache"""
    if not _redis_client:
        return
    
    try:
        cache_key = f"pincode:{pincode}"
        cache_value = json.dumps({
            "city": city,
            "state": state,
            "localities": localities
        })
        _redis_client.set(cache_key, cache_value, ex=CACHE_TTL_SECONDS)
        logger.debug(f"Cached pincode {pincode}: {city}, {state}")
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")


def _fetch_pincode_payload(base_url: str, pincode: str) -> Any:
    response = requests.get(
        f"{base_url}/{pincode}",
        timeout=6,
        headers=PINCODE_REQUEST_HEADERS,
    )
    response.raise_for_status()
    return response.json()


def _extract_city_state_from_post_office(post_office: Dict[str, Any]) -> Tuple[Optional[str], Optional[str]]:
    city_fields = ["District", "Division", "Taluk", "Block", "Region", "Name"]
    state_fields = ["State", "Circle", "Region"]

    city = None
    for field in city_fields:
        value = (post_office.get(field) or "").strip()
        if value:
            city = value
            break

    state = None
    for field in state_fields:
        value = (post_office.get(field) or "").strip()
        if value:
            state = value
            break

    return city, state


def _parse_pincode_response(payload: Any) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """Handle responses from api.postalpincode.in and postalpincode.in."""
    if not payload:
        return None, None, []

    entries: List[Dict[str, Any]]
    if isinstance(payload, list):
        entries = [entry for entry in payload if isinstance(entry, dict)]
    elif isinstance(payload, dict):
        entries = [payload]
    else:
        return None, None, []

    localities: List[Dict[str, Any]] = []
    resolved_city: Optional[str] = None
    resolved_state: Optional[str] = None
    for entry in entries:
        status = (entry.get("Status") or entry.get("status") or "").lower()
        if status != "success":
            continue
        post_offices = entry.get("PostOffice") or entry.get("postOffice") or []
        for po in post_offices:
            city, state = _extract_city_state_from_post_office(po)
            locality_name = (po.get("Name") or city or "").strip()
            locality_info = {
                "name": locality_name,
                "branch_type": (po.get("BranchType") or "").strip(),
                "delivery_status": (po.get("DeliveryStatus") or "").strip(),
                "district": (po.get("District") or "").strip(),
                "state": (po.get("State") or "").strip(),
                "pincode": (po.get("Pincode") or "").strip(),
            }
            if locality_name:
                localities.append(locality_info)
            if city and state:
                resolved_city = resolved_city or city
                resolved_state = resolved_state or state

    return resolved_city, resolved_state, localities


def get_pincode_details(pincode: str) -> Tuple[Optional[str], Optional[str], List[Dict[str, Any]]]:
    """
    Get city, state, and locality list for a pincode using postalpincode APIs.
    """
    if not pincode:
        return None, None, []
    
    # Clean pincode (remove spaces, ensure 6 digits)
    pincode = pincode.strip().replace(" ", "")
    
    if len(pincode) != 6 or not pincode.isdigit():
        logger.warning(f"Invalid pincode format: {pincode}")
        return None, None, []
    
    # Check cache first
    cached_result = _get_from_cache(pincode)
    if cached_result and cached_result.get("localities"):
        return (
            cached_result.get("city"),
            cached_result.get("state"),
            cached_result.get("localities", [])
        )
    
    # Call API(s)
    last_error = None
    for source_name, base_url in PINCODE_SOURCES:
        try:
            payload = _fetch_pincode_payload(base_url, pincode)
            city, state, localities = _parse_pincode_response(payload)
            if city and state:
                _save_to_cache(pincode, city, state, localities)
                logger.info(f"Pincode {pincode} resolved via {source_name}: {city}, {state}")
                return city, state, localities
            logger.warning(
                f"Pincode {pincode} response from {source_name} missing city/state. Payload excerpt: {str(payload)[:200]}"
            )
        except requests.exceptions.Timeout:
            last_error = "timeout"
            logger.error(f"Pincode API timeout for {pincode} using {source_name}")
        except requests.exceptions.RequestException as e:
            last_error = str(e)
            logger.error(f"Pincode API request failed for {pincode} using {source_name}: {e}")
        except Exception as e:
            last_error = str(e)
            logger.error(f"Unexpected error fetching pincode {pincode} via {source_name}: {e}", exc_info=True)
    
    if last_error:
        logger.error(f"All pincode lookups failed for {pincode}. Last error: {last_error}")
    
    # Return None if API call failed
    return None, None, []


def get_city_state_from_pincode(pincode: str) -> Tuple[Optional[str], Optional[str]]:
    """Backward-compatible helper to fetch only city/state."""
    city, state, _ = get_pincode_details(pincode)
    return city, state


def validate_and_auto_fill_address(
    pincode: str,
    city: Optional[str] = None,
    state: Optional[str] = None,
    locality: Optional[str] = None
) -> Tuple[Optional[str], Optional[str], Optional[str], List[Dict[str, Any]]]:
    """
    Validate pincode and auto-fill city/state if not provided.
    If city/state are already provided, they take precedence.
    Returns (city, state, locality, locality_options).
    """
    if city and state and locality:
        # Already provided, return as-is
        return city, state, locality, []
    
    # Try to get from pincode
    auto_city, auto_state, locality_options = get_pincode_details(pincode)
    auto_locality = locality or (locality_options[0]["name"] if locality_options else None)
    
    # Use provided values if available, otherwise use auto-filled
    final_city = city or auto_city
    final_state = state or auto_state
    final_locality = locality or auto_locality
    
    # If still None, log warning but don't fail - allow manual entry
    if not final_city or not final_state:
        logger.warning(f"Could not auto-fill city/state for pincode {pincode}. User may need to enter manually.")
    
    return final_city, final_state, final_locality, locality_options

