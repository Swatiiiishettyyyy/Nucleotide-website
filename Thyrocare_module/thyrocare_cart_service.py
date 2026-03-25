from typing import Dict, Any

def extract_payable_amount_from_breakup(breakup: Dict[str, Any]) -> float:
    """
    Extracts the net payable amount from a Thyrocare price breakup response.
    Supports various response structures found in Thyrocare API.
    """
    if not breakup or not isinstance(breakup, dict):
        return 0.0

    # Try common nested keys for price
    rates = breakup.get("rates", {})
    price = breakup.get("price", {})
    
    # Priority 1: netPayableAmount
    payable = rates.get("netPayableAmount") or price.get("netPayableAmount")
    
    # Priority 2: totalSellingPrice (fallback)
    if payable is None:
        payable = rates.get("totalSellingPrice") or price.get("totalSellingPrice")
        
    try:
        return float(payable) if payable is not None else 0.0
    except (ValueError, TypeError):
        return 0.0
