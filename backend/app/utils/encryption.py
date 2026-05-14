"""Encryption utilities for API credential storage (AES-256-GCM)."""

import base64
import json
import os
from typing import Dict

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2

from app.config import settings


# Fernet instance for simple encryption needs
_fernet_instance: Fernet | None = None


def _get_fernet_key_from_secret(secret: str) -> bytes:
    """Derive a Fernet-compatible key from a secret string."""
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ai-marketing-platform-salt",  # In production, use a unique per-deployment salt
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


def encrypt_api_credentials(data: Dict) -> str:
    """Encrypt API credentials using AES-256-GCM.

    Args:
        data: Dictionary containing API credentials (e.g., api_key, api_secret).

    Returns:
        Base64-encoded encrypted string containing: salt + nonce + ciphertext + auth_tag.
    """
    plaintext = json.dumps(data).encode("utf-8")

    # Derive a 256-bit key from the secret key
    kdf = PBKDF2(
        algorithm=hashes.SHA256(),
        length=32,
        salt=b"ai-marketing-aes-salt-v1",
        iterations=100000,
        backend=default_backend(),
    )
    key = kdf.derive(settings.SECRET_KEY.encode())

    # Generate random nonce
    nonce = os.urandom(12)

    # Encrypt with AES-256-GCM
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
    """
    try:
        combined = base64.b64decode(encrypted.encode("utf-8"))

        # Extract nonce (first 12 bytes) and ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]

        # Derive the same key
        kdf = PBKDF2(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b"ai-marketing-aes-salt-v1",
            iterations=100000,
            backend=default_backend(),
        )
        key = kdf.derive(settings.SECRET_KEY.encode())

        # Decrypt
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, None)

        return json.loads(plaintext.decode("utf-8"))
    except Exception as exc:
        raise ValueError(f"Failed to decrypt credentials: {str(exc)}") from exc


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
    """
    f = get_fernet()
    return f.decrypt(token.encode()).decode()
