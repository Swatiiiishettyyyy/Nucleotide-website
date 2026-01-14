"""
AES-256 encryption utility for phone number encryption/decryption.
"""
import os
from pathlib import Path
from base64 import b64encode, b64decode
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import secrets
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# Try multiple common locations
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_CANDIDATES = [
    BASE_DIR / ".env",         # Project root
    BASE_DIR.parent / ".env",  # Parent directory
]

for env_path in ENV_CANDIDATES:
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
        break
else:
    # Fall back to default load (will pick up system env vars if already set)
    load_dotenv()

# Load encryption key from environment variable
ENCRYPTION_KEY = os.getenv("PHONE_ENCRYPTION_KEY")
if not ENCRYPTION_KEY:
    # Generate a default key if not set (for development only)
    # In production, this should be set in environment variables
    ENCRYPTION_KEY = os.urandom(32).hex()  # 32 bytes = 256 bits
    import warnings
    warnings.warn("PHONE_ENCRYPTION_KEY not set in environment. Using generated key (not secure for production)")

# Convert hex string to bytes if needed
if isinstance(ENCRYPTION_KEY, str):
    try:
        ENCRYPTION_KEY = bytes.fromhex(ENCRYPTION_KEY)
    except ValueError:
        # If not hex, use it as-is or derive from it
        if len(ENCRYPTION_KEY.encode()) < 32:
            # Derive 32-byte key using PBKDF2
            salt = b'phone_encryption_salt_fixed'  # Fixed salt for consistent key derivation
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
                backend=default_backend()
            )
            ENCRYPTION_KEY = kdf.derive(ENCRYPTION_KEY.encode())

# Ensure key is 32 bytes (256 bits) for AES-256
if len(ENCRYPTION_KEY) != 32:
    # If key is wrong size, derive a proper one
    salt = b'phone_encryption_salt_fixed'
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
        backend=default_backend()
    )
    key_material = ENCRYPTION_KEY if isinstance(ENCRYPTION_KEY, bytes) else ENCRYPTION_KEY.encode()
    ENCRYPTION_KEY = kdf.derive(key_material)


def encrypt_phone(phone_number: str) -> str:
    """
    Encrypt a phone number using AES-256-GCM with deterministic nonce.
    Uses a deterministic nonce derived from the phone number to ensure
    the same phone number always encrypts to the same value (enables lookup).
    
    Args:
        phone_number: Plain text phone number to encrypt
        
    Returns:
        Base64-encoded encrypted phone number with nonce
    """
    if not phone_number:
        return phone_number
    
    # Generate deterministic nonce from phone number using SHA256 hash
    # This ensures the same phone number always produces the same encrypted value
    # which is necessary for database lookups
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.backends import default_backend
    digest = hashes.Hash(hashes.SHA256(), backend=default_backend())
    digest.update(phone_number.encode('utf-8'))
    digest.update(ENCRYPTION_KEY)  # Include key in hash for additional security
    phone_hash = digest.finalize()
    
    # Use first 12 bytes of hash as nonce (GCM requires 12 bytes)
    nonce = phone_hash[:12]
    
    # Create AESGCM cipher
    aesgcm = AESGCM(ENCRYPTION_KEY)
    
    # Encrypt the phone number
    phone_bytes = phone_number.encode('utf-8')
    ciphertext = aesgcm.encrypt(nonce, phone_bytes, None)
    
    # Combine nonce and ciphertext, then base64 encode
    encrypted_data = nonce + ciphertext
    encrypted_phone = b64encode(encrypted_data).decode('utf-8')
    
    return encrypted_phone


def decrypt_phone(encrypted_phone: str) -> str:
    """
    Decrypt a phone number using AES-256-GCM.
    
    Args:
        encrypted_phone: Base64-encoded encrypted phone number with nonce, or plain text
        
    Returns:
        Plain text phone number
    """
    if not encrypted_phone:
        return encrypted_phone
    
    # Check if it looks like plain text (10 digits, no special characters)
    # If it's already plain text, return as-is
    if encrypted_phone.isdigit() and len(encrypted_phone) == 10:
        return encrypted_phone
    
    try:
        # Decode from base64
        encrypted_data = b64decode(encrypted_phone.encode('utf-8'))
        
        # Extract nonce (first 12 bytes) and ciphertext (rest)
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        # Create AESGCM cipher
        aesgcm = AESGCM(ENCRYPTION_KEY)
        
        # Decrypt the phone number
        phone_bytes = aesgcm.decrypt(nonce, ciphertext, None)
        phone_number = phone_bytes.decode('utf-8')
        
        return phone_number
    except Exception as e:
        # If decryption fails, assume it's plain text and return as-is
        # This allows for backward compatibility with unencrypted phone numbers
        import logging
        logger = logging.getLogger(__name__)
        # Only log if it doesn't look like plain text (to reduce noise)
        if not (encrypted_phone.isdigit() and len(encrypted_phone) == 10):
            logger.debug(f"Failed to decrypt phone number (assuming plain text): {e}")
        return encrypted_phone

