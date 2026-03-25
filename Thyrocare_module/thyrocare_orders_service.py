from typing import Dict, Any

def _extract_price_from_breakup(breakup: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extracts pricing details from a Thyrocare breakup response to build a create-order payload.
    Ensures correct keys for discounts and incentive passons.
    """
    if not breakup or not isinstance(breakup, dict):
        return {}

    rates = breakup.get("rates", {})
    
    # If the breakup already contains flattened pricing fields, use them
    if "discounts" in breakup or "incentivePasson" in breakup:
        return {
            "discounts": breakup.get("discounts", []),
            "incentivePasson": breakup.get("incentivePasson", {})
        }
        
    # Otherwise extract from the 'rates' object
    return {
        "discounts": rates.get("discounts", []),
        "incentivePasson": rates.get("incentives", {})
    }
