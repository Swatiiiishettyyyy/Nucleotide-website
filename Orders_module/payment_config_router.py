"""
Public payment configuration for the frontend (Razorpay key id, active mode).
"""
import re

import requests
from fastapi import APIRouter, HTTPException, Query

from config import settings
from .razorpay_service import get_razorpay_public_config

router = APIRouter(prefix="/config", tags=["Config"])

GOOGLE_GEOCODE_BASE = "https://maps.googleapis.com/maps/api/geocode/json"


def _google_maps_key() -> str:
    token = settings.GOOGLE_MAPS_API_KEY or settings.VITE_GOOGLE_MAPS_API_KEY or ""
    return token.strip().strip("\"'")


def _component_text(components: list[dict], types: tuple[str, ...], *, short: bool = False) -> str:
    for wanted in types:
        for item in components:
            item_types = item.get("types")
            if isinstance(item_types, list) and wanted in item_types:
                key = "short_name" if short else "long_name"
                return str(item.get(key) or item.get("long_name") or "")
    return ""


def _postal_code(result: dict) -> str:
    components = result.get("address_components")
    if not isinstance(components, list):
        components = []

    from_component = re.sub(r"\D", "", _component_text(components, ("postal_code",)))
    if len(from_component) >= 6:
        return from_component[:6]

    match = re.search(r"\b(\d{6})\b", str(result.get("formatted_address") or ""))
    return match.group(1) if match else ""


def _parse_reverse_results(results: list[dict], lng: float, lat: float) -> dict | None:
    if not results:
        return None

    primary = next(
        (
            result
            for result in results
            if any(
                result_type in {"street_address", "premise", "subpremise", "point_of_interest", "establishment"}
                for result_type in result.get("types", [])
            )
        ),
        results[0],
    )

    components = primary.get("address_components")
    if not isinstance(components, list):
        components = []

    place_name = str(primary.get("formatted_address") or "").strip()
    street_number = _component_text(components, ("street_number",))
    route = _component_text(components, ("route",))
    premise = _component_text(components, ("premise", "point_of_interest", "establishment"))
    street_line = " ".join(part for part in (street_number, route) if part).strip() or premise
    locality = _component_text(
        components,
        ("sublocality_level_2", "sublocality_level_1", "sublocality", "neighborhood"),
    )
    city = _component_text(
        components,
        ("locality", "administrative_area_level_3", "administrative_area_level_2"),
    )

    return {
        "street_line": street_line or (place_name.split(",")[0].strip() if place_name else ""),
        "locality": locality,
        "city": city,
        "state": _component_text(components, ("administrative_area_level_1",)),
        "postal_code": _postal_code(primary),
        "place_name": place_name,
        "longitude": lng,
        "latitude": lat,
    }


@router.get("/payment")
def get_payment_config():
    """
    Return Razorpay checkout settings for the active RAZORPAY_MODE (test | live).
    Never exposes secret keys or webhook secrets.
    """
    return {
        "status": "success",
        "data": get_razorpay_public_config(),
    }


@router.get("/reverse-geocode")
def reverse_geocode(
    lng: float = Query(..., ge=-180, le=180),
    lat: float = Query(..., ge=-90, le=90),
    language: str = Query("en", min_length=2, max_length=12),
):
    """
    Reverse-geocode coordinates through the backend for map-based address autofill.
    """
    token = _google_maps_key()
    if not token:
        raise HTTPException(status_code=503, detail="Google Maps API key is not configured")

    try:
        response = requests.get(
            GOOGLE_GEOCODE_BASE,
            params={"latlng": f"{lat:.8f},{lng:.8f}", "key": token, "language": language},
            timeout=10,
        )
    except requests.exceptions.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Google geocoding request failed: {exc}") from exc

    if response.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Google geocoding returned {response.status_code}")

    data = response.json()
    status = str(data.get("status") or "") if isinstance(data, dict) else ""
    if status and status not in {"OK", "ZERO_RESULTS"}:
        message = str(data.get("error_message") or status)
        raise HTTPException(status_code=502, detail=f"Google geocoding failed: {message}")

    results = data.get("results") if isinstance(data, dict) else None
    parsed = _parse_reverse_results(results if isinstance(results, list) else [], lng, lat)
    if not parsed:
        raise HTTPException(status_code=404, detail="Could not detect address from coordinates")

    return {
        "status": "success",
        "data": parsed,
    }
