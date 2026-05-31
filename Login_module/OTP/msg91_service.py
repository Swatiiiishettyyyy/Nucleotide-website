import logging
import os
from pathlib import Path
from typing import Dict, Optional

import requests

from config import settings

logger = logging.getLogger(__name__)


class Msg91SendError(RuntimeError):
    pass


_ENV_CACHE: Optional[Dict[str, str]] = None


def _clean(value: Optional[object]) -> str:
    return str(value or "").strip().strip('"').strip("'")


def _load_project_env() -> Dict[str, str]:
    """
    Best-effort fallback for local runs where an empty process env var shadows
    the value from Nucleotide-website/.env.
    """
    global _ENV_CACHE
    if _ENV_CACHE is not None:
        return _ENV_CACHE

    env_path = Path(__file__).resolve().parents[2] / ".env"
    values: Dict[str, str] = {}
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = _clean(value.split(" #", 1)[0])
    except OSError:
        pass

    _ENV_CACHE = values
    return values


def _config_value(setting_name: str, *aliases: str) -> str:
    candidates = (setting_name, *aliases)

    for name in candidates:
        value = _clean(getattr(settings, name, ""))
        if value:
            return value

    for name in candidates:
        value = _clean(os.getenv(name))
        if value:
            return value

    env_values = _load_project_env()
    for name in candidates:
        value = _clean(env_values.get(name))
        if value:
            return value

    return ""


def _msisdn(country_code: str, mobile: str) -> str:
    # MSG91 expects numeric MSISDN like "91XXXXXXXXXX"
    cc = (country_code or "").strip().lstrip("+")
    return f"{cc}{mobile}".strip()


def send_flow(country_code: str, mobile: str, template_id: str, variables: Optional[dict] = None) -> Optional[str]:
    """
    Send an MSG91 Flow template with optional variables.
    variables are merged into the recipient object (e.g., {"OTP": "1234"}).
    """
    auth_key = _config_value("MSG91_AUTH_KEY")
    flow_url = _config_value("MSG91_FLOW_URL") or settings.MSG91_FLOW_URL

    if not auth_key:
        raise Msg91SendError("MSG91 is not configured (missing MSG91_AUTH_KEY).")
    if not template_id:
        raise Msg91SendError("MSG91 flow template_id is missing.")

    url = flow_url
    headers = {
        "accept": "application/json",
        "authkey": auth_key,
        "content-type": "application/json",
    }

    recipient = {"mobiles": _msisdn(country_code, mobile)}
    if variables:
        recipient.update(variables)

    payload = {
        "template_id": template_id,
        "short_url": str(settings.MSG91_SHORT_URL),
        "realTimeResponse": str(settings.MSG91_REALTIME_RESPONSE),
        "recipients": [recipient],
    }

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=10)
    except Exception as e:
        raise Msg91SendError(f"MSG91 request failed: {e}") from e

    if resp.status_code < 200 or resp.status_code >= 300:
        body_preview = (resp.text or "").strip()
        body_preview = body_preview[:500]
        raise Msg91SendError(f"MSG91 returned {resp.status_code}: {body_preview}")

    try:
        data = resp.json()
    except Exception:
        data = None

    msg = None
    if isinstance(data, dict):
        msg = data.get("message") or data.get("Message") or data.get("request_id")

    logger.info("MSG91 Flow sent successfully to %s (template_id=%s)", _msisdn(country_code, mobile), template_id)
    return msg


def send_otp_via_msg91_flow(country_code: str, mobile: str, otp: str) -> Optional[str]:
    """
    Send OTP using MSG91 Flow API.

    Returns message/id from MSG91 on success (when available).
    Raises Msg91SendError on failure.
    """
    template_id = _config_value(
        "MSG91_OTP_TEMPLATE_ID",
        "MSG91_TEMPLATE_ID_OTP",
        "MSG91_LOGIN_OTP_TEMPLATE_ID",
    )
    if not template_id:
        raise Msg91SendError("MSG91 is not configured (missing MSG91_OTP_TEMPLATE_ID).")
    return send_flow(country_code, mobile, template_id, variables={"OTP": str(otp)})
