"""
Signed download URL generator for secure file access.

Creates time-limited, cryptographically signed URLs for downloading
exported report files. Uses JWT-style HMAC-SHA256 signing.
"""

import hashlib
import hmac
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple

import jwt

from app.reports.constants import SIGNED_URL_ALGORITHM, SIGNED_URL_EXPIRY_SECONDS


class SignedUrlGenerator:
    """
    Generates signed, time-limited download URLs.

    Uses JWT tokens with HMAC-SHA256 signing. The token embeds
    the file path, expiry timestamp, and a nonce for replay protection.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = secret_key or os.environ.get(
            "EXPORT_SIGN_SECRET",
            os.environ.get("SECRET_KEY", "default-export-secret-key-change-me"),
        )

    def generate(
        self,
        file_path: str,
        file_name: str,
        mime_type: str,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[str, datetime]:
        """
        Generate a signed download URL.

        Args:
            file_path: Storage path of the exported file.
            file_name: Human-readable file name for download.
            mime_type: MIME type of the file.
            expiry_seconds: URL validity duration.
            company_id: Optional company scope.
            user_id: Optional user scope.

        Returns:
            Tuple of (signed_url, expires_at).
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expiry_seconds)

        # Build minimal JWT payload
        payload: Dict[str, Any] = {
            "sub": file_path,
            "fn": file_name,
            "mime": mime_type,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
            "jti": secrets.token_hex(8),  # nonce for replay protection
        }

        if company_id is not None:
            payload["cid"] = company_id
        if user_id is not None:
            payload["uid"] = user_id

        token = jwt.encode(payload, self.secret_key, algorithm=SIGNED_URL_ALGORITHM)

        # Build URL (the consumer app will mount the download endpoint)
        signed_url = f"/api/v1/exports/download?token={token}"

        return signed_url, expires_at

    def verify(self, token: str) -> Optional[Dict[str, Any]]:
        """
        Verify a signed download token.

        Args:
            token: JWT token from the URL.

        Returns:
            Decoded payload dict if valid, None if invalid/expired.
        """
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[SIGNED_URL_ALGORITHM],
                options={"require": ["exp", "sub", "fn"]},
            )
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None

    def generate_external_url(
        self,
        base_url: str,
        file_path: str,
        file_name: str,
        mime_type: str,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
        company_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> Tuple[str, datetime]:
        """
        Generate a full external signed URL with base URL.

        Args:
            base_url: Application base URL (e.g., https://app.example.com).
            file_path: Storage path.
            file_name: Download file name.
            mime_type: MIME type.
            expiry_seconds: Validity duration.
            company_id: Company scope.
            user_id: User scope.

        Returns:
            Tuple of (full_signed_url, expires_at).
        """
        path, expires = self.generate(
            file_path=file_path,
            file_name=file_name,
            mime_type=mime_type,
            expiry_seconds=expiry_seconds,
            company_id=company_id,
            user_id=user_id,
        )

        # Ensure base_url has no trailing slash
        base_url = base_url.rstrip("/")

        full_url = f"{base_url}{path}"
        return full_url, expires


class SimpleSignedUrlGenerator:
    """
    Lightweight signed URL generator using HMAC-SHA256 without JWT dependency.

    Suitable for simpler deployments where JWT is not required.
    """

    def __init__(self, secret_key: Optional[str] = None):
        self.secret_key = (secret_key or os.environ.get(
            "EXPORT_SIGN_SECRET",
            os.environ.get("SECRET_KEY", "default-export-secret"),
        )).encode("utf-8")

    def generate(
        self,
        file_path: str,
        file_name: str,
        expiry_seconds: int = SIGNED_URL_EXPIRY_SECONDS,
    ) -> Tuple[str, int]:
        """
        Generate HMAC-signed URL parameters.

        Returns:
            Tuple of (token, expiry_timestamp).
        """
        expiry = int(time.time()) + expiry_seconds
        message = f"{file_path}:{file_name}:{expiry}".encode("utf-8")
        signature = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()[:32]
        token = f"{signature}.{expiry}.{file_path}"
        return token, expiry

    def verify(self, token: str, file_path: str, file_name: str) -> bool:
        """Verify a signed token."""
        try:
            parts = token.split(".")
            if len(parts) != 3:
                return False
            received_sig, expiry_str, recv_path = parts
            expiry = int(expiry_str)

            if time.time() > expiry:
                return False
            if recv_path != file_path:
                return False

            message = f"{file_path}:{file_name}:{expiry}".encode("utf-8")
            expected_sig = hmac.new(self.secret_key, message, hashlib.sha256).hexdigest()[:32]
            return hmac.compare_digest(received_sig, expected_sig)
        except Exception:
            return False
