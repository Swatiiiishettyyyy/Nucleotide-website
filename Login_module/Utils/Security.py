from datetime import datetime, timedelta
from typing import Dict, Any
import jwt
from fastapi import HTTPException
from dotenv import load_dotenv
import os
import hashlib

# Load environment variables
load_dotenv()

# Read secret and algorithm from .env
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    raise ValueError("SECRET_KEY is missing in .env file")

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_SECONDS = int(os.getenv("ACCESS_TOKEN_EXPIRE_SECONDS", 86400))


def create_access_token(data: Dict[str, Any], expires_delta: int = None) -> str:
    """
    Creates a JWT access token with expiration timestamp.
    """
    to_encode = data.copy()
    from Login_module.Utils.datetime_utils import now_ist
    expire = now_ist() + timedelta(
        seconds=(expires_delta or ACCESS_TOKEN_EXPIRE_SECONDS)
    )
    to_encode.update({"exp": expire})
    token = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return token


def hash_value(value: str) -> str:
    """
    Returns SHA256 hashed string of a given plain text.
    Used for hashing OTP and user-entered OTP during verification.
    """
    return hashlib.sha256(value.encode()).hexdigest()


def decode_access_token(token: str):
    """
    Decodes and validates JWT access token.
    Raises HTTPException for invalid or expired tokens.
    """
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return decoded
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")