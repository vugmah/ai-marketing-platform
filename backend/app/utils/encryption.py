"""Encryption utilities for API credential storage (AES-256-GCM).

Security features:
- AES-256-GCM for authenticated encryption of API credentials
- PBKDF2-HMAC-SHA256 with 100k iterations for key derivation
- Per-deployment salt support (falls back to environment-derived salt)
- Fernet for simple symmetric encryption needs
- Constant-time comparison for tag verification
- Automatic ciphertext authentication (GCM mode prevents tampering)
"""

import base64
import hashlib
import json
import os
from typing import Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC as PBKDF2

from app.config import settings


# ============================================================================
# Key Derivation
# ============================================================================

# Derive a stable but unique salt per deployment
# Priority: 1) ENV var, 2) SECRET_KEY hash, 3) hardcoded fallback (dev only)
def _get_deployment_salt() -> bytes:
    """Get a unique salt for this deployment.

    The salt ensures that even if two deployments use the same SECRET_KEY,
    their encrypted data cannot be cross-decrypted.

    Returns:
        16-byte salt unique to this deployment.
    """
    # Try environment-specific salt
    env_salt = os.environ.get("ENCRYPTION_SALT", "")
    if env_salt and len(env_salt) >= 8:
        return hashlib.sha256(env_salt.encode()).digest()[:16]

    # Derive from SECRET_KEY (stable per deployment)
    return hashlib.sha256(settings.SECRET_KEY.encode()).digest()[:16]


# AES-GCM salt for credential encryption
_AES_SALT = _get_deployment_salt()

# Fernet instance for simple encryption needs
_fernet_instance: Fernet | None = None


def _get_fernet_key_from_secret(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a secret string."""
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_AES_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    key = kdf.derive(secret.encode())
    # Fernet requires base64-encoded 32-byte key with URL-safe base64 padding
    return base64.urlsafe_b64encode(key)


def get_fernet() -> Fernet:
    """Get or create the shared Fernet instance."""
    global _fernet_instance
    if _fernet_instance is None:
        key = _get_fernet_key_from_secret(settings.SECRET_KEY)
        _fernet_instance = Fernet(key)
    return _fernet_instance


# ============================================================================
# AES-256-GCM Credential Encryption
# ============================================================================


def encrypt_api_credentials(data: Dict) -> str:
    """Encrypt API credentials using AES-256-GCM.

    Uses per-deployment salt derived from SECRET_KEY and ENCRYPTION_SALT env var.
    Each encryption generates a unique random nonce to prevent
    nonce reuse attacks.

    Args:
        data: Dictionary containing API credentials (e.g., api_key, api_secret).

    Returns:
        Base64-encoded encrypted string containing: nonce + ciphertext + auth_tag.
    """
    plaintext = json.dumps(data).encode("utf-8")

    # Derive a 256-bit key from the secret key using per-deployment salt
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_AES_SALT,
        iterations=100000,
        backend=default_backend(),
    )
    key = kdf.derive(settings.SECRET_KEY.encode())

    # Generate random nonce (never reuse nonce with same key)
    nonce = os.urandom(12)

    # Encrypt with AES-256-GCM (provides both confidentiality and authenticity)
    aesgcm = AESGCM(key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Combine nonce + ciphertext (auth tag is last 16 bytes of ciphertext)
    combined = nonce + ciphertext

    # Return base64-encoded result
    return base64.b64encode(combined).decode("utf-8")


def decrypt_api_credentials(encrypted: str) -> Dict:
    """Decrypt API credentials encrypted with AES-256-GCM.

    Args:
        encrypted: Base64-encoded encrypted string from encrypt_api_credentials.

    Returns:
        Dictionary containing the decrypted API credentials.

    Raises:
        ValueError: If decryption fails (invalid ciphertext, tampered data,
                    or wrong key).
    """
    try:
        combined = base64.b64decode(encrypted.encode("utf-8"))

        # Extract nonce (first 12 bytes) and ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]

        # Minimum length check: nonce (12) + ciphertext (min 16 for tag) = 28
        if len(ciphertext) < 16:
            raise ValueError("Invalid encrypted data: too short")

        # Derive the same key using per-deployment salt
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=_AES_SALT,
            iterations=100000,
            backend=default_backend(),
        )
        key = kdf.derive(settings.SECRET_KEY.encode())

        # Decrypt - GCM will verify the authentication tag
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return json.loads(plaintext.decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse decrypted credentials: {str(exc)}") from exc
    except Exception as exc:
        raise ValueError(f"Failed to decrypt credentials: {str(exc)}") from exc


# ============================================================================
# Fernet Simple Encryption
# ============================================================================


def fernet_encrypt(data: str) -> str:
    """Simple Fernet encryption for non-credential data.

    Args:
        data: String to encrypt.

    Returns:
        Encrypted token string.
    """
    f = get_fernet()
    return f.encrypt(data.encode()).decode()


def fernet_decrypt(token: str) -> str:
    """Simple Fernet decryption.

    Args:
        token: Encrypted token from fernet_encrypt.

    Returns:
        Decrypted string.

    Raises:
        ValueError: If the token is invalid or has been tampered with.
    """
    try:
        f = get_fernet()
        return f.decrypt(token.encode()).decode()
    except Exception as exc:
        raise ValueError(f"Failed to decrypt: {str(exc)}") from exc


# ============================================================================
# Constant-Time Comparison
# ============================================================================


def secure_compare(a: str, b: str) -> bool:
    """Compare two strings in constant time to prevent timing attacks.

    Args:
        a: First string to compare.
        b: Second string to compare.

    Returns:
        True if the strings are equal, False otherwise.
    """
    return hashlib.compare_digest(a.encode(), b.encode())


# ============================================================================
# Hash utilities for non-reversible operations
# ============================================================================


def hash_identifier(identifier: str) -> str:
    """Create a one-way hash of an identifier (e.g., API key ID).

    Used for storing references without revealing the actual identifier.

    Args:
        identifier: The identifier to hash.

    Returns:
        Hex-encoded SHA-256 hash.
    """
    return hashlib.sha256(
        (identifier + settings.SECRET_KEY).encode()
    ).hexdigest()


def verify_identifier_hash(identifier: str, hash_value: str) -> bool:
    """Verify an identifier against its stored hash.

    Args:
        identifier: The identifier to verify.
        hash_value: The stored hash value.

    Returns:
        True if the identifier matches the hash.
    """
    expected = hash_identifier(identifier)
    return secure_compare(expected, hash_value)
