import requests
import logging
import time
from typing import Optional, Dict, Any
from config import settings

logger = logging.getLogger(__name__)

class ThyrocareService:
    _instance = None
    _token: Optional[str] = None
    _token_expiry: float = 0

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ThyrocareService, cls).__new__(cls)
        return cls._instance

    def _get_headers(self, include_auth: bool = True) -> Dict[str, str]:
        headers = {
            "Partner-Id": settings.THYROCARE_PARTNER_ID,
            "Request-Id": settings.THYROCARE_REQUEST_ID,
            "Client-Type": settings.THYROCARE_CLIENT_TYPE,
            "Entity-Type": settings.THYROCARE_ENTITY_TYPE,
            "Content-Type": "application/json"
        }
        if include_auth and self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        return headers

    def login(self) -> bool:
        """Authenticate with Thyrocare and store the JWT token."""
        url = f"{settings.THYROCARE_BASE_URL}/partners/v1/auth/login"
        payload = {
            "username": settings.THYROCARE_USERNAME,
            "password": settings.THYROCARE_PASSWORD
        }
        
        try:
            logger.info(f"Attempting Thyrocare login for user: {settings.THYROCARE_USERNAME}")
            response = requests.post(url, json=payload, headers=self._get_headers(include_auth=False))
            response.raise_for_status()
            
            data = response.json()
            self._token = data.get("token")
            
            # Simple JWT expiry extraction (fallback to 24h if parsing fails)
            try:
                import jwt
                decoded = jwt.decode(self._token, options={"verify_signature": False})
                self._token_expiry = decoded.get("exp", time.time() + 86400)
            except Exception:
                self._token_expiry = time.time() + 86400 # 24 hour fallback
                
            logger.info("Thyrocare login successful. Token acquired.")
            return True
        except Exception as e:
            logger.error(f"Thyrocare login failed: {str(e)}")
            return False

    def logout(self) -> bool:
        """Logout from Thyrocare session."""
        if not self._token:
            return True
            
        url = f"{settings.THYROCARE_BASE_URL}/partners/v1/auth/logout"
        try:
            response = requests.post(url, headers=self._get_headers())
            response.raise_for_status()
            self._token = None
            self._token_expiry = 0
            logger.info("Thyrocare logout successful.")
            return True
        except Exception as e:
            logger.error(f"Thyrocare logout failed: {str(e)}")
            return False

    def get_token(self) -> Optional[str]:
        """Get a valid token, logging in if necessary."""
        # Refresh if token is missing or expires in less than 5 minutes
        if not self._token or time.time() > (self._token_expiry - 300):
            if not self.login():
                return None
        return self._token

def start_thyrocare_auth_task():
    """
    Initializes Thyrocare authentication and can be used with a scheduler 
    to keep the session alive.
    """
    service = ThyrocareService()
    success = service.login()
    if success:
        logger.info("Thyrocare background auth initialized.")
    else:
        logger.error("Failed to initialize Thyrocare background auth.")

def normalize_thyrocare_errors(response_data: Any) -> Dict[str, Any]:
    """Helper to extract error messages from Thyrocare responses."""
    if isinstance(response_data, dict):
        errors = response_data.get("errors", [])
        if errors and isinstance(errors, list):
            return {"message": errors[0].get("message", "Unknown Thyrocare error"), "raw": response_data}
    return {"message": str(response_data), "raw": response_data}
