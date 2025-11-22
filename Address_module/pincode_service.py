"""
Pincode service for auto-generating city and state from pincode.
Uses free postalpincode.in API with Redis caching for performance.
"""
import logging
import requests
from typing import Optional, Tuple
from dotenv import load_dotenv
import os

load_dotenv()

logger = logging.getLogger(__name__)

# API Configuration
PINCODE_API_URL = "https://api.postalpincode.in/pincode"
CACHE_TTL_SECONDS = int(os.getenv("PINCODE_CACHE_TTL", 86400))  # 24 hours default

# Try to get Redis client (if available)
_redis_client = None
try:
    from Login_module.OTP import otp_manager
    _redis_client = otp_manager._redis_client
    logger.info("Redis available for pincode caching")
except Exception as e:
    logger.warning(f"Redis not available for pincode caching: {e}")


def _get_from_cache(pincode: str) -> Optional[Tuple[str, str]]:
    """Get city/state from Redis cache"""
    if not _redis_client:
        return None
    
    try:
        cache_key = f"pincode:{pincode}"
        cached = _redis_client.get(cache_key)
        if cached:
            # Cache format: "city|state"
            city, state = cached.split("|")
            logger.debug(f"Pincode {pincode} found in cache")
            return city, state
    except Exception as e:
        logger.warning(f"Error reading from cache: {e}")
    
    return None


def _save_to_cache(pincode: str, city: str, state: str):
    """Save city/state to Redis cache"""
    if not _redis_client:
        return
    
    try:
        cache_key = f"pincode:{pincode}"
        cache_value = f"{city}|{state}"
        _redis_client.set(cache_key, cache_value, ex=CACHE_TTL_SECONDS)
        logger.debug(f"Cached pincode {pincode}: {city}, {state}")
    except Exception as e:
        logger.warning(f"Error saving to cache: {e}")


def get_city_state_from_pincode(pincode: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Get city and state from pincode using free postalpincode.in API.
    Uses Redis caching to reduce API calls.
    Returns (city, state) tuple. Returns (None, None) if not found.
    """
    if not pincode:
        return None, None
    
    # Clean pincode (remove spaces, ensure 6 digits)
    pincode = pincode.strip().replace(" ", "")
    
    if len(pincode) != 6 or not pincode.isdigit():
        logger.warning(f"Invalid pincode format: {pincode}")
        return None, None
    
    # Check cache first
    cached_result = _get_from_cache(pincode)
    if cached_result:
        return cached_result
    
    # Call API
    try:
        response = requests.get(f"{PINCODE_API_URL}/{pincode}", timeout=5)
        response.raise_for_status()
        
        data = response.json()
        
        # API returns array with PostOffice objects
        if data and len(data) > 0 and data[0].get("Status") == "Success":
            post_offices = data[0].get("PostOffice", [])
            
            if post_offices and len(post_offices) > 0:
                # Use first post office data
                first_po = post_offices[0]
                city = first_po.get("District", "").strip()
                state = first_po.get("State", "").strip()
                
                # Some APIs return "Division" or "Block" as city
                if not city:
                    city = first_po.get("Division", "").strip()
                if not city:
                    city = first_po.get("Block", "").strip()
                
                if city and state:
                    # Cache the result
                    _save_to_cache(pincode, city, state)
                    logger.info(f"Pincode {pincode} resolved: {city}, {state}")
                    return city, state
                else:
                    logger.warning(f"Pincode {pincode} API returned incomplete data: {data}")
            else:
                logger.warning(f"Pincode {pincode} not found in API response")
        else:
            error_msg = data[0].get("Message", "Unknown error") if data else "No data"
            logger.warning(f"Pincode API error for {pincode}: {error_msg}")
    
    except requests.exceptions.Timeout:
        logger.error(f"Pincode API timeout for {pincode}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Pincode API request failed for {pincode}: {e}")
    except Exception as e:
        logger.error(f"Unexpected error fetching pincode {pincode}: {e}", exc_info=True)
    
    # Return None if API call failed
    return None, None


def validate_and_auto_fill_address(pincode: str, city: Optional[str] = None, state: Optional[str] = None) -> Tuple[Optional[str], Optional[str]]:
    """
    Validate pincode and auto-fill city/state if not provided.
    If city/state are already provided, they take precedence.
    Returns (city, state) - both can be None if pincode lookup fails.
    """
    if city and state:
        # Already provided, return as-is
        return city, state
    
    # Try to get from pincode
    auto_city, auto_state = get_city_state_from_pincode(pincode)
    
    # Use provided values if available, otherwise use auto-filled
    final_city = city or auto_city
    final_state = state or auto_state
    
    # If still None, log warning but don't fail - allow manual entry
    if not final_city or not final_state:
        logger.warning(f"Could not auto-fill city/state for pincode {pincode}. User may need to enter manually.")
    
    return final_city, final_state

